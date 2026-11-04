"""One-time migration: split the raw per-model prices off the elasticity pillar.

Before this ran, data/scorecard/elasticity.csv held two rows per model per run
(input and output price), about 856 rows a week. That is raw collected data,
not a pillar series, and it buried the one number the pillar exists to report:
the open vs closed price advantage at the mid-tier floor.

This script relocates, it does not rewrite. Every per-model row is copied
byte-for-byte, with its date, value and unit untouched, into
data/elasticity_prices.csv. The pillar file is then replaced with the mid-tier
aggregate alone, derived from data/price_bases.csv for the same dates the raw
prices were collected. No measurement is altered, deleted or re-dated, and the
old pillar file stays in git history. See docs/decisions.md, 2026-11-03.

The derived aggregate rows carry the collection date of the prices they come
from and record, in their notes, when they were computed. That is derivation
from already-collected data, not backfill.

Refuses to run once data/elasticity_prices.csv exists, so it cannot run twice.

Usage:
    python scripts/migrate_elasticity.py
    python scripts/migrate_elasticity.py --dry-run
"""

import argparse
import csv
import datetime as dt
import os
import sys

from price_bases import midtier_aggregate, elasticity_pillar_rows

PILLAR = "data/scorecard/elasticity.csv"
RAW_DEST = "data/elasticity_prices.csv"
PRICE_BASES = "data/price_bases.csv"

FIELDS = ["date", "entity", "entity_class", "metric", "value", "unit",
          "source", "source_url", "notes"]


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, rows):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would move, write nothing")
    args = ap.parse_args()

    if os.path.exists(RAW_DEST):
        sys.exit("%s already exists. Migration has already run; refusing to "
                 "run a second time." % RAW_DEST)

    pillar = read_csv(PILLAR)
    raw_rows = [r for r in pillar if r["metric"].startswith("openrouter_price_")]
    kept = [r for r in pillar if not r["metric"].startswith("openrouter_price_")]

    if not raw_rows:
        sys.exit("%s has no openrouter_price_ rows to move. Nothing to do."
                 % PILLAR)

    # Mid-tier aggregate for every date the raw prices cover, from the bases.
    bases = read_csv(PRICE_BASES)
    computed_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dates = sorted({r["date"] for r in raw_rows})
    agg_rows, missing = [], []
    for date in dates:
        agg = midtier_aggregate(bases, date)
        if not agg:
            missing.append(date)
            continue
        for row in elasticity_pillar_rows(
                agg, date, source="derived from data/price_bases.csv"):
            row["notes"] += "; computed at migration %s" % computed_at
            agg_rows.append(row)

    new_pillar = sorted(kept + agg_rows, key=lambda r: (r["date"], r["metric"]))

    print("per-model rows to relocate to %s: %d" % (RAW_DEST, len(raw_rows)))
    print("dates covered: %s" % ", ".join(dates))
    print("aggregate rows for new pillar file: %d" % len(agg_rows))
    for r in agg_rows:
        if r["metric"] == "price_advantage_midtier_fp8":
            print("  %s advantage %sx" % (r["date"], r["value"]))
    if kept:
        print("non-price rows kept in pillar file: %d" % len(kept))
    if missing:
        print("WARNING no mid-tier aggregate for: %s" % ", ".join(missing))

    # Reconcile: nothing lost.
    if len(raw_rows) + len(kept) != len(pillar):
        sys.exit("row accounting does not reconcile; aborting")

    if args.dry_run:
        print("\ndry run, nothing written")
        return

    write_csv(RAW_DEST, raw_rows)
    write_csv(PILLAR, new_pillar)
    print("\nwrote %s (%d rows)" % (RAW_DEST, len(raw_rows)))
    print("rewrote %s (%d rows: %d aggregate, %d other)"
          % (PILLAR, len(new_pillar), len(agg_rows), len(kept)))


if __name__ == "__main__":
    main()
