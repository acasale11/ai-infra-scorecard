"""Collector: Artificial Analysis intelligence index, the direct source.

The capability tiers used to read whatever intelligence index OpenRouter
happened to embed in its payload, which covered about an eighth of the catalogue
and carried no version. This pulls the index straight from Artificial Analysis,
one versioned source, so the capability scale rests on real coverage.

Writes two things on every run:

1. The raw API response, unmodified, to
   data/raw/artificial_analysis/<date>.json. The provenance record.
2. Appended rows on data/aa_intelligence_index.csv, one per scored model, with
   the reasoning variant parsed from the model name so the matcher can pick the
   highest variant per base model.

Free tier of the Artificial Analysis data API. Attribution is required for use
of the free API: https://artificialanalysis.ai. The key lives in .env as
ARTIFICIAL_ANALYSIS_API_KEY and is never committed.

The script only ever appends and refuses to run twice for the same date.

Usage:
    python scripts/collect_aa_index.py
    python scripts/collect_aa_index.py --dry-run
"""

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import urllib.request
import urllib.error

API = "https://artificialanalysis.ai/api/v2/language/models/free"
RAW_DIR = "data/raw/artificial_analysis"
DEST = "data/aa_intelligence_index.csv"
SOURCE_URL = "https://artificialanalysis.ai"
USER_AGENT = "ai-infra-scorecard research collector"
ENV_KEY = "ARTIFICIAL_ANALYSIS_API_KEY"

FIELDS = ["date", "aa_slug", "aa_name", "model_creator", "reasoning_variant",
          "intelligence_index", "index_version", "collected_at"]

# Trailing parenthetical on an AA model name marks the reasoning configuration,
# for example "GPT-6 Sol (High)". Captured so the matcher can choose a variant;
# a name with no parenthetical is the base configuration.
VARIANT_RE = re.compile(r"\(([^)]+)\)\s*$")


def read_key():
    """The API key from the environment, falling back to a .env line.

    Stdlib only, so the collectors still need nothing installed. The workflow
    passes the key through the environment; a local run reads it from .env.
    """
    key = os.environ.get(ENV_KEY, "").strip()
    if key:
        return key
    if os.path.exists(".env"):
        with open(".env", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith(ENV_KEY + "="):
                    return line.split("=", 1)[1].strip()
    return ""


def creator_name(model):
    c = model.get("model_creator")
    if isinstance(c, dict):
        return c.get("name") or c.get("slug") or ""
    return c or ""


def variant_of(name):
    m = VARIANT_RE.search(name or "")
    return m.group(1).strip() if m else ""


def fetch_all(key):
    """Every page of the free models endpoint, as one list, plus the version."""
    headers = {"x-api-key": key, "User-Agent": USER_AGENT,
               "Accept": "application/json"}
    models, version, page = [], None, 1
    while True:
        req = urllib.request.Request("%s?page=%d" % (API, page), headers=headers)
        with urllib.request.urlopen(req, timeout=60) as fh:
            payload = json.loads(fh.read().decode("utf-8"))
        if version is None:
            version = payload.get("intelligence_index_version")
        rows = payload.get("data", [])
        if not rows:
            break
        models.extend(rows)
        pag = payload.get("pagination") or {}
        if not pag.get("has_more"):
            break
        page += 1
    return models, version


def build_rows(models, version, date, collected_at):
    rows, scored = [], 0
    for m in models:
        idx = (m.get("evaluations") or {}).get(
            "artificial_analysis_intelligence_index")
        if idx is None:
            continue
        scored += 1
        rows.append({
            "date": date,
            "aa_slug": m.get("slug") or "",
            "aa_name": m.get("name") or "",
            "model_creator": creator_name(m),
            "reasoning_variant": variant_of(m.get("name")),
            "intelligence_index": idx,
            "index_version": "" if version is None else version,
            "collected_at": collected_at,
        })
    return rows, scored


def existing_dates(path):
    if not os.path.exists(path):
        return set()
    with open(path, newline="", encoding="utf-8") as fh:
        rdr = csv.DictReader(fh)
        if not rdr.fieldnames or "date" not in rdr.fieldnames:
            return set()
        return {r["date"] for r in rdr}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="fetch and report, write nothing")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    args = ap.parse_args()

    key = read_key()
    if not key:
        sys.exit("no %s in the environment or .env" % ENV_KEY)

    if not args.dry_run and args.date in existing_dates(DEST):
        sys.exit("%s already has rows for %s. Refusing to append a second set. "
                 "Existing rows are never modified." % (DEST, args.date))

    collected_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        models, version = fetch_all(key)
    except urllib.error.HTTPError as exc:
        sys.exit("Artificial Analysis API returned %s: %s"
                 % (exc.code, exc.read().decode("utf-8", "replace")[:200]))

    rows, scored = build_rows(models, version, args.date, collected_at)
    print("fetched         %d models from Artificial Analysis" % len(models))
    print("index version   %s" % version)
    print("with an index   %d" % scored)
    print("rows to append  %d" % len(rows))

    if args.dry_run:
        print("\ndry run, nothing written")
        return

    os.makedirs(RAW_DIR, exist_ok=True)
    raw_path = os.path.join(RAW_DIR, "%s.json" % args.date)
    with open(raw_path, "w", encoding="utf-8") as fh:
        json.dump({"intelligence_index_version": version, "data": models},
                  fh, indent=2, sort_keys=True)
    print("\nwrote raw response  %s" % raw_path)

    exists = os.path.exists(DEST)
    with open(DEST, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if not exists or os.path.getsize(DEST) == 0:
            w.writeheader()
        w.writerows(rows)
    print("appended %d rows to %s" % (len(rows), DEST))


if __name__ == "__main__":
    main()
