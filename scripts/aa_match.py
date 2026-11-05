"""Match OpenRouter model ids to Artificial Analysis intelligence scores.

This is the join between two catalogues that name models differently.
Artificial Analysis scores each reasoning configuration separately, for example
"GPT-6 Sol (Low)" and "GPT-6 Sol (High)", while an OpenRouter id such as
"openai/gpt-6-sol" names no configuration. The approved rule is to attach the
highest-scoring variant per base model, recording which one.

Matching is conservative, in the spirit of the weight classifier: a model is
scored only on an unambiguous normalized match or an explicit entry in
config/aa_model_map.json. Anything else is left unscored with a reason, never
guessed, because a wrong score is worse than a missing one.

Pure functions, so the behaviour is unit tested without a network or files.
"""

import csv
import json
import os
import re

MAP_PATH = "config/aa_model_map.json"

# Trailing parenthetical on an AA name is the reasoning configuration.
_VARIANT_RE = re.compile(r"\s*\([^)]*\)\s*$")


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def base_name(aa_name):
    """An AA model name with the trailing reasoning variant removed."""
    return _VARIANT_RE.sub("", aa_name or "").strip()


def family_of(model_id):
    """OpenRouter id reduced to the model name: no org prefix, no SKU suffix."""
    return model_id.split("/", 1)[-1].split(":", 1)[0]


def build_lookup(aa_rows):
    """Normalized key -> best record for the base model it belongs to.

    Rows are grouped by base model name. Each group's best is the
    highest-scoring variant. Every group is then reachable by its base name and
    by any of its variants' slugs, all pointing at that single best record, so a
    lookup by any variant returns the model's ceiling.
    """
    groups = {}
    for r in aa_rows:
        try:
            idx = float(r["intelligence_index"])
        except (TypeError, ValueError, KeyError):
            continue
        key = norm(base_name(r.get("aa_name")))
        if not key:
            continue
        groups.setdefault(key, []).append((idx, r))

    lookup = {}
    for base_key, recs in groups.items():
        idx, best = max(recs, key=lambda t: t[0])
        rec = {"index": idx, "slug": best.get("aa_slug", ""),
               "variant": best.get("reasoning_variant", ""),
               "name": best.get("aa_name", ""), "base_key": base_key}
        keys = {base_key}
        for _, r in recs:
            keys.add(norm(r.get("aa_slug")))
            keys.add(norm(base_name(r.get("aa_name"))))
        for k in keys:
            if not k:
                continue
            # On a rare collision across different base models, keep the higher
            # score; both are ceilings, so this never understates.
            if k not in lookup or rec["index"] > lookup[k]["index"]:
                lookup[k] = rec
    return lookup


def match_model(model_id, lookup, override=None):
    """(index, evidence) for a model, or (None, reason) when unmatched."""
    override = override or {}
    family = family_of(model_id)

    target = override.get(model_id) or override.get(family)
    if target:
        rec = lookup.get(norm(target))
        if rec:
            return rec["index"], "override %s to AA %s (%s)" % (
                target, rec["slug"], rec["variant"] or "base")
        return None, "override %s has no AA match" % target

    for key in (norm(family), norm(model_id.split("/")[-1]),
                norm(model_id.replace("/", "-"))):
        rec = lookup.get(key)
        if rec:
            return rec["index"], "AA %s (variant %s)" % (
                rec["slug"], rec["variant"] or "base")
    return None, "no AA match for '%s'" % family


def load_aa_rows(path, date):
    """AA index rows for one collection date."""
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh) if r.get("date") == date]


def load_override(path=MAP_PATH):
    """The manual map, ignoring comment keys that start with underscore."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    return {k: v for k, v in raw.items() if not k.startswith("_")}
