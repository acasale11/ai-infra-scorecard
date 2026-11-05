"""Classify OpenRouter models as open or closed weights, and assign a tier.

Writes data/model_classification.csv, one row per model per run date.

Why this is a separate table rather than an edit to elasticity.csv: the rows
already in elasticity.csv record the classification that was in force when
they were collected, and existing rows are never modified. A classification
that improves is a new dated table, not a rewrite of history. Charts and
queries join prices to the latest classification by model id.

The rule, applied in order, with the basis recorded on every row:

  1. OpenRouter gives the model a hugging_face_id        -> open_weights
  2. The organisation is on the closed-weight list        -> closed_weights
  3. A weights repo for the model exists under the
     organisation's Hugging Face namespace                -> open_weights
  4. The namespace is confirmed to publish weights, but
     holds no repo for this model                         -> closed_weights
  5. Anything else                                        -> unclassified

Step 4 is the only inference, and it is conditional: the namespace must be
proven to publish weights in the same run before a negative result from it
counts for anything. If the namespace is unknown, wrong, or empty, the model
falls to step 5 and stays unclassified with the reason recorded. Nothing is
classified from memory.

Tiers come from the Artificial Analysis intelligence index, collected directly
by scripts/collect_aa_index.py and joined by scripts/aa_match.py, using the
frozen absolute bands in config/weight_classes.json. The bands are unchanged
from when they were frozen on 2026-10-30; only the score source moved, from the
thin slice OpenRouter embedded to the full AA v5 index. Price is never an input,
which matters because the output of all this is a price comparison.

Run scripts/collect_aa_index.py for the same date first, or every model lands
unscored. Usage:
    python scripts/classify_weights.py
    python scripts/classify_weights.py --date 2026-10-30 --offline
"""

import argparse
import csv
import hashlib
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import aa_match

CONFIG = "config/weight_classes.json"
RAW_DIR = "data/raw/openrouter"
HF_CACHE_DIR = "data/raw/huggingface"
DEST = "data/model_classification.csv"
AA_INDEX = "data/aa_intelligence_index.csv"
HF_API = "https://huggingface.co/api/models"
USER_AGENT = "ai-infra-scorecard research collector"

FIELDS = ["date", "model_id", "org", "weight_class", "weight_basis",
          "weight_evidence", "intelligence_index", "tier", "tier_basis"]

OPEN, CLOSED, UNKNOWN = "open_weights", "closed_weights", "unclassified"


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def http_json(url, cache_path=None):
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as fh:
            return json.load(fh)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as fh:
                data = json.loads(fh.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                data = None
                break
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    if cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
    return data


class HFNamespace:
    """One Hugging Face namespace, listed once and matched against locally."""

    def __init__(self, ns, cache_dir, weight_exts, offline=False):
        self.ns = ns
        self.repos = []
        self.publishes_weights = False
        path = os.path.join(cache_dir, "ns-%s.json" % norm(ns))
        if offline and not os.path.exists(path):
            return
        url = "%s?%s" % (HF_API, urllib.parse.urlencode(
            {"author": ns, "limit": 1000}))
        data = http_json(url, path) or []
        self.repos = [r["id"] for r in data if isinstance(r, dict) and "id" in r]
        # A namespace only counts as publishing weights once we have seen a
        # real weight file in one of its repos. Checked lazily, below.
        self._weight_exts = tuple(weight_exts)
        self._cache_dir = cache_dir
        self._offline = offline
        self._checked = {}

    def repo_has_weights(self, repo_id):
        if repo_id in self._checked:
            return self._checked[repo_id]
        # Hashed, not named: the full repo id pushes the path past the
        # Windows 260 character limit. The repo id is inside the file.
        digest = hashlib.sha1(repo_id.encode("utf-8")).hexdigest()[:16]
        path = os.path.join(self._cache_dir, "repo-%s.json" % digest)
        if self._offline and not os.path.exists(path):
            self._checked[repo_id] = False
            return False
        info = http_json("%s/%s" % (HF_API, repo_id), path)
        files = [s.get("rfilename", "") for s in (info or {}).get("siblings", [])]
        ok = any(f.endswith(self._weight_exts) for f in files)
        self._checked[repo_id] = ok
        return ok

    def find(self, family):
        """Match `family` against this namespace's repos.

        Returns (repo_id, kind) where kind is "exact" for a repo that is the
        model, or "variant_base" for a repo that is the model minus its last
        name part. Returns (None, None) for no match.

        Matching compares delimited token SETS, not substrings. Substring
        matching is wrong in both directions here. It misses
        `mistral-large-2512` against `Mistral-Large-3-675B-Instruct-2512`,
        where a size string sits in the middle, and it falsely matches
        `seed-1.6` against `Seed-Coder-8B-Reasoning-bf16`, where the digits
        of "1" and "6" turn up inside "bf16". Tokenising both sides fixes
        both.
        """
        def toks(s):
            return {norm(t) for t in re.split(r"[^A-Za-z0-9.]+", s) if norm(t)}

        want = toks(family)
        if not want:
            return None, None
        # A hosted variant: the repo is the family minus its final part, as
        # with glm-5.3-prime against GLM-5.3. The base weights are published
        # but this SKU is not separately released, so it is ambiguous rather
        # than closed.
        parts = [p for p in re.split(r"[^A-Za-z0-9.]+", family) if p]
        base = toks("-".join(parts[:-1])) if len(parts) > 1 else set()

        exact, variant = [], []
        for repo in self.repos:
            rt = toks(repo.split("/", 1)[-1])
            if want <= rt:
                exact.append((len(rt), repo))
            elif base and base <= rt:
                variant.append((len(rt), repo))
        for _, repo in sorted(exact):
            if self.repo_has_weights(repo):
                self.publishes_weights = True
                return repo, "exact"
        for _, repo in sorted(variant):
            if self.repo_has_weights(repo):
                self.publishes_weights = True
                return repo, "variant_base"
        return None, None

    def prove_publishes_weights(self):
        """Confirm the namespace publishes weights at all, before a miss counts."""
        if self.publishes_weights:
            return True
        for repo in self.repos[:12]:
            if self.repo_has_weights(repo):
                self.publishes_weights = True
                return True
        return False


def family_of(model_id):
    """The model name without org prefix, SKU suffix or speed-variant tail."""
    name = model_id.split("/", 1)[-1].split(":", 1)[0]
    return name


def tier_for(index, bands):
    if index is None:
        return "", "no intelligence_index in the OpenRouter payload"
    for band in bands:
        if index >= band["min"]:
            return band["name"], "intelligence_index %s >= %s" % (
                index, band["min"])
    return "", "below all bands"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--offline", action="store_true",
                    help="use only cached Hugging Face responses")
    args = ap.parse_args()

    with open(CONFIG, encoding="utf-8") as fh:
        cfg = json.load(fh)
    namespaces_cfg = {k: v for k, v in cfg["hf_namespaces"].items()
                      if not k.startswith("_")}
    closed_orgs = set(cfg["closed_weight_orgs"]["orgs"])
    weight_exts = cfg["weight_file_extensions"]
    bands = sorted(cfg["tiers"]["bands"], key=lambda b: -b["min"])

    raw_path = os.path.join(RAW_DIR, "%s.json" % args.date)
    if not os.path.exists(raw_path):
        sys.exit("no raw payload at %s. Run the collector first." % raw_path)
    with open(raw_path, encoding="utf-8") as fh:
        models = json.load(fh)["data"]

    # Capability scores from Artificial Analysis, joined by name. Missing for the
    # date means collect_aa_index did not run, and silently unscoring every model
    # is worse than stopping.
    aa_rows = aa_match.load_aa_rows(AA_INDEX, args.date)
    if not aa_rows:
        sys.exit("no Artificial Analysis index for %s in %s. Run "
                 "collect_aa_index.py first." % (args.date, AA_INDEX))
    aa_lookup = aa_match.build_lookup(aa_rows)
    aa_override = aa_match.load_override()
    index_version = aa_rows[0].get("index_version", "")

    cache_dir = os.path.join(HF_CACHE_DIR, args.date)
    namespaces = {}

    def ns_for(org):
        ns_name = namespaces_cfg.get(org)
        if not ns_name:
            return None
        if ns_name not in namespaces:
            namespaces[ns_name] = HFNamespace(
                ns_name, cache_dir, weight_exts, args.offline)
        return namespaces[ns_name]

    rows, counts = [], {OPEN: 0, CLOSED: 0, UNKNOWN: 0}
    for m in sorted(models, key=lambda x: x["id"]):
        mid = m["id"]
        if m.get("alias_target") or mid.startswith("~"):
            continue
        pricing = m.get("pricing") or {}
        try:
            if float(pricing.get("prompt")) < 0 or \
               float(pricing.get("completion")) < 0:
                continue
        except (TypeError, ValueError):
            continue

        org = mid.split("/")[0].lstrip("~")
        cls = basis = evidence = None

        if m.get("hugging_face_id"):
            cls, basis = OPEN, "openrouter_hugging_face_id"
            evidence = m["hugging_face_id"]
        elif org in closed_orgs:
            cls, basis = CLOSED, "org_on_closed_weight_list"
            evidence = "config/weight_classes.json closed_weight_orgs"
        else:
            ns = ns_for(org)
            if ns is None or not ns.repos:
                cls, basis = UNKNOWN, "no_known_hf_namespace"
                evidence = ("no Hugging Face namespace mapped for org '%s'"
                            % org)
            else:
                hit, kind = ns.find(family_of(mid))
                if hit and kind == "exact":
                    cls, basis = OPEN, "hf_weights_repo_found"
                    evidence = "https://huggingface.co/%s" % hit
                elif hit and kind == "variant_base":
                    cls, basis = UNKNOWN, "hosted_variant_of_open_base"
                    evidence = ("base weights at https://huggingface.co/%s, "
                                "but this SKU is not separately released; the "
                                "served variant may differ from the published "
                                "weights" % hit)
                elif ns.prove_publishes_weights():
                    cls, basis = CLOSED, "hf_namespace_publishes_but_no_repo"
                    evidence = ("searched https://huggingface.co/%s (%d repos), "
                                "no weights repo for '%s'"
                                % (ns.ns, len(ns.repos), family_of(mid)))
                else:
                    cls, basis = UNKNOWN, "hf_namespace_unverified"
                    evidence = ("namespace %s returned no repo with weight "
                                "files, so a miss proves nothing" % ns.ns)

        idx, match_evidence = aa_match.match_model(mid, aa_lookup, aa_override)
        tier, band_reason = tier_for(idx, bands)
        if idx is None:
            tier_basis = match_evidence
        else:
            tier_basis = "%s; %s; AA index v%s" % (
                match_evidence, band_reason, index_version)

        counts[cls] += 1
        rows.append({
            "date": args.date, "model_id": mid, "org": org,
            "weight_class": cls, "weight_basis": basis,
            "weight_evidence": evidence,
            "intelligence_index": "" if idx is None else idx,
            "tier": tier, "tier_basis": tier_basis,
        })

    exists = os.path.exists(DEST)
    if exists:
        with open(DEST, newline="", encoding="utf-8") as fh:
            if args.date in {r["date"] for r in csv.DictReader(fh)}:
                sys.exit("%s already has rows for %s. Existing rows are never "
                         "modified." % (DEST, args.date))
    with open(DEST, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if not exists:
            w.writeheader()
        w.writerows(rows)

    print("classified %d models for %s" % (len(rows), args.date))
    for cls in (OPEN, CLOSED, UNKNOWN):
        print("  %-15s %3d" % (cls, counts[cls]))
    print("\nby basis:")
    by_basis = {}
    for r in rows:
        by_basis.setdefault((r["weight_class"], r["weight_basis"]), 0)
        by_basis[(r["weight_class"], r["weight_basis"])] += 1
    for (cls, basis), n in sorted(by_basis.items(), key=lambda kv: -kv[1]):
        print("  %-15s %-38s %3d" % (cls, basis, n))
    tiers = {}
    for r in rows:
        if r["tier"]:
            tiers.setdefault(r["tier"], 0)
            tiers[r["tier"]] += 1
    print("\ntiers: %s (%d models have an index)"
          % (tiers, sum(tiers.values())))
    print("wrote %s" % DEST)


if __name__ == "__main__":
    main()
