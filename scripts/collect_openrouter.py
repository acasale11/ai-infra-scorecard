"""Collector: OpenRouter public models API, per-token prices by model.

Writes two things on every run:

1. The raw API response, unmodified, to data/raw/openrouter/<date>.json. This
   is the provenance record. If the parsing below turns out to be wrong, the
   original is still there to re-derive from.
2. Appended rows on data/elasticity_prices.csv, two per model (input and
   output price), tagged open or closed weights. These raw per-model prices
   feed the elasticity pillar's aggregate but are not the pillar series
   themselves: the pillar file data/scorecard/elasticity.csv holds only the
   mid-tier advantage aggregate, written by scripts/price_bases.py. See
   docs/decisions.md, 2026-11-03.

The script only ever appends. It refuses to run twice for the same date
rather than risk writing a second set of rows for a day that already has one.

Usage:
    python scripts/collect_openrouter.py
    python scripts/collect_openrouter.py --dry-run
"""

import argparse
import csv
import datetime as dt
import json
import os
import sys
import urllib.request

API_URL = "https://openrouter.ai/api/v1/models"
RAW_DIR = "data/raw/openrouter"
DEST = "data/elasticity_prices.csv"
SOURCE_NAME = "OpenRouter models API"
USER_AGENT = "ai-infra-scorecard research collector"

FIELDS = ["date", "entity", "entity_class", "metric", "value", "unit",
          "source", "source_url", "notes"]

METRIC_INPUT = "openrouter_price_input"
METRIC_OUTPUT = "openrouter_price_output"

# Step 2 of the classification rule. See docs/methodology.md.
#
# These organisations serve their flagship models without publishing weights.
# The list is deliberately short. An organisation only belongs here if its
# unpublished models are unambiguously closed. Anything not caught by step 1
# or step 2 is left unclassified rather than guessed at, which is why the
# unclassified count is expected to stay large.
CLOSED_WEIGHT_ORGS = {
    "anthropic",
    "openai",
    "google",
    "x-ai",
    "amazon",
    "perplexity",
}

OPEN = "open_weights"
CLOSED = "closed_weights"
UNKNOWN = "unclassified"


def classify(model):
    """Return (entity_class, reason). Never guesses."""
    if model.get("hugging_face_id"):
        return OPEN, "hugging_face_id=%s" % model["hugging_face_id"]
    org = model["id"].split("/")[0].lstrip("~")
    if org in CLOSED_WEIGHT_ORGS:
        return CLOSED, "closed-weight org %s, no hugging_face_id" % org
    return UNKNOWN, "no hugging_face_id and %s not on the closed-weight list" % org


def fetch():
    req = urllib.request.Request(API_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.loads(fh.read().decode("utf-8"))


def existing_dates(path):
    """Dates that already carry OpenRouter price rows."""
    if not os.path.exists(path):
        return set()
    with open(path, newline="", encoding="utf-8") as fh:
        rdr = csv.DictReader(fh)
        if not rdr.fieldnames or "metric" not in rdr.fieldnames:
            return set()
        return {r["date"] for r in rdr
                if r.get("metric", "").startswith("openrouter_price_")}


def build_rows(payload, date, collected_at, raw_path):
    models = payload["data"]
    rows = []
    skipped = {"alias": [], "variable_price": []}
    counts = {OPEN: 0, CLOSED: 0, UNKNOWN: 0}
    unclassified = []

    for m in sorted(models, key=lambda x: x["id"]):
        mid = m["id"]

        # Aliases point at another model in the same payload. Keeping them
        # would count the same model twice.
        if m.get("alias_target") or mid.startswith("~"):
            skipped["alias"].append(mid)
            continue

        pricing = m.get("pricing") or {}
        prompt, completion = pricing.get("prompt"), pricing.get("completion")
        if prompt is None or completion is None:
            skipped["variable_price"].append(mid)
            continue
        try:
            p_in, p_out = float(prompt), float(completion)
        except (TypeError, ValueError):
            skipped["variable_price"].append(mid)
            continue
        # -1 means the price varies per request (router and auto models).
        if p_in < 0 or p_out < 0:
            skipped["variable_price"].append(mid)
            continue

        cls, reason = classify(m)
        counts[cls] += 1
        if cls == UNKNOWN:
            unclassified.append(mid)

        note = "collected_at=%s; raw=%s; classification: %s" % (
            collected_at, raw_path, reason)
        if mid.endswith(":free"):
            note += ("; zero-priced promotional endpoint, exclude from price "
                     "averages")

        for metric, value in ((METRIC_INPUT, p_in), (METRIC_OUTPUT, p_out)):
            rows.append({
                "date": date,
                "entity": mid,
                "entity_class": cls,
                "metric": metric,
                # API quotes USD per token. Stored as USD per million tokens.
                "value": "%.6f" % (value * 1_000_000),
                "unit": "usd_per_mtok",
                "source": SOURCE_NAME,
                "source_url": API_URL,
                "notes": note,
            })

    return rows, skipped, counts, unclassified


def append_rows(path, rows):
    exists = os.path.exists(path)
    if exists:
        with open(path, newline="", encoding="utf-8") as fh:
            header = next(csv.reader(fh), None)
        if header != FIELDS:
            sys.exit("%s header is %s, expected %s" % (path, header, FIELDS))
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if not exists:
            w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="fetch and report, write nothing")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    args = ap.parse_args()

    date = args.date
    if not args.dry_run and date in existing_dates(DEST):
        sys.exit("%s already has OpenRouter price rows for %s. Refusing to "
                 "append a second set. Existing rows are never modified." %
                 (DEST, date))

    collected_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = fetch()
    raw_path = "%s/%s.json" % (RAW_DIR, date)

    rows, skipped, counts, unclassified = build_rows(
        payload, date, collected_at, raw_path)

    total = len(payload["data"])
    print("fetched           %d models from %s" % (total, API_URL))
    print("collected_at      %s" % collected_at)
    print("skipped aliases   %d" % len(skipped["alias"]))
    print("skipped variable  %d  %s" % (len(skipped["variable_price"]),
                                        ", ".join(skipped["variable_price"])))
    print("priced models     %d" % (len(rows) // 2))
    print("  open_weights    %d" % counts[OPEN])
    print("  closed_weights  %d" % counts[CLOSED])
    print("  unclassified    %d" % counts[UNKNOWN])
    print("rows to append    %d" % len(rows))

    if counts[UNKNOWN]:
        print("\nunclassified models (flagged, not guessed):")
        for mid in unclassified:
            print("  %s" % mid)

    if args.dry_run:
        print("\ndry run, nothing written")
        return

    os.makedirs(RAW_DIR, exist_ok=True)
    with open(raw_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
    print("\nwrote raw response  %s" % raw_path)

    append_rows(DEST, rows)
    print("appended %d rows to %s" % (len(rows), DEST))


if __name__ == "__main__":
    main()
