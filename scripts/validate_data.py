"""Check the data record's integrity before anyone trusts it.

The project's integrity rules are documented and, until now, enforced only by
hand. This script enforces them. It reports facts and nothing else: it never
interprets a number, only checks that the number is well formed, is not a
duplicate, is not dated in the future, and that the core KPIs the project
commits to are present and current.

Checks, every one a hard failure that exits non-zero:

1. Schema. Every scorecard file and the raw price file carry the expected
   nine-column header.
2. Well-formed rows. Each row has a date, a metric, a value and a source.
   value parses as a number, or as a date when the unit is `date`. source_url
   is present unless the source is derived (computed from other rows, so it
   has no URL).
3. No duplicates. No two rows in a file share (date, entity, metric). This is
   the append-only guarantee: a collector that ran twice would show here.
4. No future dates. No row carries an observation date after the run date,
   which is how an accidental forward-backfill would look.
5. Unit consistency. A metric never carries two different units in one file.
6. Stated and effective rates stay separate. The merged metric name
   `instrument_rate` must never appear; mixing the two produced a withdrawn
   finding and the rule exists to stop it recurring.
7. Core KPIs. Every weekly KPI in config/core_kpis.json has an observation
   newer than its staleness window. Every quarterly KPI is present at all.

Usage:
    python scripts/validate_data.py
    python scripts/validate_data.py --date 2026-11-02
"""

import argparse
import csv
import datetime as dt
import json
import os

CORE_KPIS = "config/core_kpis.json"

SCORECARD_FILES = [
    "data/scorecard/credit.csv",
    "data/scorecard/elasticity.csv",
    "data/scorecard/open_source_share.csv",
    "data/scorecard/compute_pricing.csv",
    "data/scorecard/buyer_concentration.csv",
]
RAW_FILES = ["data/elasticity_prices.csv"]
SCORECARD_HEADER = ["date", "entity", "entity_class", "metric", "value",
                    "unit", "source", "source_url", "notes"]


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        rdr = csv.DictReader(fh)
        return rdr.fieldnames or [], list(rdr)


def is_iso_date(s):
    try:
        dt.date.fromisoformat(s)
        return True
    except (ValueError, TypeError):
        return False


def is_number(s):
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def check_file(path, run_date, fails):
    """All per-file checks: schema, rows, duplicates, future dates, units."""
    if not os.path.exists(path):
        fails.append("%s: missing" % path)
        return
    header, rows = read_rows(path)
    if header != SCORECARD_HEADER:
        fails.append("%s: header is %s, expected %s"
                     % (path, header, SCORECARD_HEADER))
        return
    if not rows:
        return  # an empty pillar file is allowed; emptiness is not an error

    # credit.csv mixes two record kinds with different uniqueness rules. The
    # FRED benchmarks are unique on (date, metric). The SEC issuer facts are
    # not: one instrument's rate can repeat across filings, keyed by accession
    # in the notes, and the XBRL flattening can also emit the same fact more
    # than once. So for SEC facts the only hard rule is that this run did not
    # write a byte-identical row twice, checked on rows collected this run.
    # Everything else is unique on (date, entity, metric).
    is_credit = os.path.basename(path) == "credit.csv"
    collected_tag = "collected %s" % run_date

    seen = {}        # (date, entity, metric) for the strict files
    fred_seen = {}   # (date, metric) for credit FRED rows
    exact_seen = {}  # full row, for credit SEC rows collected this run
    units = {}
    for i, r in enumerate(rows, 2):  # row 1 is the header
        where = "%s line %d" % (path, i)
        date, metric = r.get("date", ""), r.get("metric", "")
        value, unit = r.get("value", ""), r.get("unit", "")
        source, url = r.get("source", ""), r.get("source_url", "")

        if not is_iso_date(date):
            fails.append("%s: bad or missing date %r" % (where, date))
        elif date > run_date:
            fails.append("%s: date %s is after the run date %s (future-dated)"
                         % (where, date, run_date))
        if not metric:
            fails.append("%s: empty metric" % where)
        if not value.strip():
            fails.append("%s: empty value for %s" % (where, metric))
        elif unit == "date":
            if not is_iso_date(value):
                fails.append("%s: unit is date but value %r is not a date"
                             % (where, value))
        elif not is_number(value):
            fails.append("%s: value %r for %s is not a number"
                         % (where, value, metric))
        if not source.strip():
            fails.append("%s: empty source" % where)
        elif not source.startswith("derived") and not url.strip():
            fails.append("%s: empty source_url for non-derived source %r"
                         % (where, source))

        if not is_credit:
            key = (date, r.get("entity", ""), metric)
            if key in seen:
                fails.append("%s: duplicate (date, entity, metric) %s, first "
                             "seen line %d" % (where, key, seen[key]))
            else:
                seen[key] = i
        elif source == "FRED":
            key = (date, metric)
            if key in fred_seen:
                fails.append("%s: duplicate FRED (date, metric) %s, first seen "
                             "line %d" % (where, key, fred_seen[key]))
            else:
                fred_seen[key] = i
        elif collected_tag in r.get("notes", ""):
            key = tuple(r.get(c, "") for c in SCORECARD_HEADER)
            if key in exact_seen:
                fails.append("%s: byte-identical row collected this run, first "
                             "seen line %d (a collector ran twice)"
                             % (where, exact_seen[key]))
            else:
                exact_seen[key] = i

        if metric and unit:
            if metric in units and units[metric] != unit:
                fails.append("%s: metric %s has unit %r here but %r earlier"
                             % (where, metric, unit, units[metric]))
            units.setdefault(metric, unit)

    if "instrument_rate" in units:
        fails.append("%s: metric 'instrument_rate' present; stated and "
                     "effective rates must stay separate" % path)


def check_core_kpis(run_date, fails, check_freshness=True):
    """Presence always, freshness only when asked.

    The weekly run checks freshness, because the data was just collected and
    a stale core KPI means a collector failed. A push-triggered CI run checks
    presence only, because the committed data it sees can legitimately be a
    few days old without anything being wrong, and coupling the test suite to
    the age of the committed data would make it fail for the wrong reason.
    """
    with open(CORE_KPIS, encoding="utf-8") as fh:
        cfg = json.load(fh)
    today = dt.date.fromisoformat(run_date)

    # Newest date per (file, metric), read once per file.
    newest = {}
    files = {spec["source_file"]
             for pillar in cfg["pillars"].values()
             for group in ("weekly", "quarterly")
             for spec in pillar.get(group, [])}
    for path in files:
        if not os.path.exists(path):
            continue
        _, rows = read_rows(path)
        for r in rows:
            k = (path, r.get("metric"))
            d = r.get("date", "")
            if is_iso_date(d) and (k not in newest or d > newest[k]):
                newest[k] = d

    for pillar, groups in cfg["pillars"].items():
        for spec in groups.get("weekly", []):
            k = (spec["source_file"], spec["metric"])
            latest = newest.get(k)
            if latest is None:
                fails.append("core KPI %s/%s is missing entirely"
                             % (pillar, spec["metric"]))
                continue
            if not check_freshness:
                continue
            age = (today - dt.date.fromisoformat(latest)).days
            if age > spec["staleness_days"]:
                fails.append("core KPI %s/%s is stale: newest %s, %d days old "
                             "(limit %d)" % (pillar, spec["metric"], latest,
                                             age, spec["staleness_days"]))
        for spec in groups.get("quarterly", []):
            k = (spec["source_file"], spec["metric"])
            if k not in newest:
                fails.append("core KPI %s/%s (quarterly) is missing entirely"
                             % (pillar, spec["metric"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--no-freshness", action="store_true",
                    help="check core KPI presence but not staleness; for "
                         "push CI, where committed data can be a few days old")
    args = ap.parse_args()

    fails = []
    for path in SCORECARD_FILES + RAW_FILES:
        check_file(path, args.date, fails)
    check_core_kpis(args.date, fails, check_freshness=not args.no_freshness)

    if fails:
        print("FAIL: %d problem(s)\n" % len(fails))
        for f in fails:
            print("  - %s" % f)
        raise SystemExit(1)
    print("OK: all integrity checks and core KPIs passed as of %s" % args.date)


if __name__ == "__main__":
    main()
