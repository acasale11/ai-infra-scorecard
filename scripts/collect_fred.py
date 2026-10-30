"""Collector: FRED credit benchmarks, the denominator for every issuer spread.

An issuer spread on its own says nothing. CoreWeave paying 9.75% is a fact
about the bond market in 2026 as much as it is a fact about CoreWeave. These
nine series are what any AI infrastructure borrowing cost has to be measured
against: investment grade and high yield option-adjusted spreads, the BB, B
and CCC buckets underneath them, two effective yields and the 10-year
Treasury.

Writes two things on every run:

1. The raw CSV for each series, unmodified, to
   data/raw/fred/<collection date>/<series id>.csv. Full history as returned,
   not the trimmed window. If the parsing below is wrong the original is there
   to re-derive from.
2. Appended rows on data/scorecard/credit.csv, one per series per observation
   date.

The date column holds the OBSERVATION date, not the collection date.

That is a deliberate departure from the other collectors, where the date
column holds the day the data was pulled. A model's price has no date of its
own, so the collection date is the only honest stamp. A published index level
does have a date of its own, and it is the one that matters: a spread on
2026-03-14 belongs on 2026-03-14 whether it was pulled that evening or three
years later. Storing the pull date instead would stack a decade of market
history onto a single day and make the series unusable. The collection date
is kept per row in the notes column, so nothing is lost. See
docs/decisions.md.

This is not backfilling in the sense the integrity rules forbid. Nothing here
claims to have been collected earlier than it was, and no measurement is
reconstructed after the fact; FRED is publishing a dated historical record and
the dates are part of the record.

Append only. On each run the script finds the newest observation already
stored for each series and appends only what comes after it, so a second run
on the same day writes nothing and a run next month writes next month. It also
re-reads the overlap and reports any value that has changed since it was
stored, without rewriting it. FRED does revise, rarely. A revision is a new
fact and belongs in a new dated commit with an explanation, not in a silent
overwrite.

Usage:
    python scripts/collect_fred.py
    python scripts/collect_fred.py --dry-run
    python scripts/collect_fred.py --series DGS10
"""

import argparse
import csv
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request

CONFIG = "config/credit_series.json"
RAW_DIR = "data/raw/fred/%s"
DEST = "data/scorecard/credit.csv"
API = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s"
SOURCE_NAME = "FRED"

# FRED dropped the connection on the first request of the session and served
# the same URL without complaint three seconds later. Retry rather than treat
# a dropped connection as a missing series.
USER_AGENT = ("ai-infra-scorecard research collector "
              "(tonycresearch.substack.com)")
ATTEMPTS = 4

FIELDS = ["date", "entity", "entity_class", "metric", "value", "unit",
          "source", "source_url", "notes"]

ENTITY_CLASS = "index"


def fetch(series_id):
    """Full history CSV for one series, as text."""
    req = urllib.request.Request(API % series_id,
                                 headers={"User-Agent": USER_AGENT})
    last = None
    for attempt in range(ATTEMPTS):
        try:
            with urllib.request.urlopen(req, timeout=60) as fh:
                return fh.read().decode("utf-8")
        except Exception as exc:
            last = exc
            if attempt < ATTEMPTS - 1:
                time.sleep(3 * (attempt + 1))
    raise RuntimeError("%s failed after %d attempts: %s"
                       % (series_id, ATTEMPTS, last))


def parse(text, series_id):
    """[(observation date, float)], skipping FRED's '.' for no observation."""
    rows = list(csv.reader(text.splitlines()))
    if not rows:
        raise RuntimeError("%s returned nothing" % series_id)
    header = [h.strip() for h in rows[0]]
    if len(header) != 2:
        raise RuntimeError("%s: unexpected header %r" % (series_id, header))
    out = []
    for r in rows[1:]:
        if len(r) != 2:
            continue
        date, raw = r[0].strip(), r[1].strip()
        if raw in (".", ""):
            continue
        try:
            out.append((date, float(raw)))
        except ValueError:
            continue
    return out


def existing(path):
    """{series id: {observation date: stored value}} already in the file."""
    seen = {}
    if not os.path.exists(path):
        return seen
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r.get("source") != SOURCE_NAME:
                continue
            seen.setdefault(r["entity"], {})[r["date"]] = r["value"]
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat(),
                    help="collection date, recorded in notes and raw path")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--series", action="append",
                    help="limit to one series id, repeatable")
    args = ap.parse_args()
    collected = args.date

    with open(CONFIG, encoding="utf-8") as fh:
        cfg = json.load(fh)
    start = cfg["history_start"]
    series = [s for s in cfg["series"]
              if not args.series or s["id"] in args.series]
    if not series:
        sys.exit("no series matched")

    stored = existing(DEST)
    raw_dir = RAW_DIR % collected
    if not args.dry_run:
        os.makedirs(raw_dir, exist_ok=True)

    new_rows, revisions, summary = [], [], []
    for s in series:
        sid, scale = s["id"], s["scale"]
        text = fetch(sid)
        if not args.dry_run:
            with open(os.path.join(raw_dir, "%s.csv" % sid), "w",
                      encoding="utf-8", newline="") as fh:
                fh.write(text)
        obs = parse(text, sid)
        have = stored.get(sid, {})
        newest = max(have) if have else None

        # Revisions: compare the overlap, report, never rewrite.
        for date, value in obs:
            if date in have:
                was, now = have[date], "%.4f" % (value * scale)
                if float(was) != float(now):
                    revisions.append((sid, date, was, now))

        window = [(d, v) for d, v in obs
                  if d >= start and (newest is None or d > newest)]
        for date, value in window:
            new_rows.append({
                "date": date,
                "entity": sid,
                "entity_class": ENTITY_CLASS,
                "metric": s["metric"],
                "value": "%.4f" % (value * scale),
                "unit": s["unit"],
                "source": SOURCE_NAME,
                "source_url": API % sid,
                "notes": "collected %s" % collected,
            })
        summary.append((sid, s["metric"], len(obs), obs[0][0], obs[-1][0],
                        len(window), obs[-1][1] * scale, s["unit"]))

    print("%-16s %-20s %7s %12s %12s %7s %12s"
          % ("series", "metric", "history", "first", "latest", "new",
             "latest value"))
    for sid, metric, n, first, last, new, val, unit in summary:
        print("%-16s %-20s %7d %12s %12s %7d %9.2f %s"
              % (sid, metric, n, first, last, new, val, unit))

    # Eight of the nine series serve a rolling three-year window and ignore
    # the date parameters, so history older than that is already gone and
    # what is here now will be gone later. Say so on every run.
    capped = [(sid, first) for sid, _, _, first, _, _, _, _ in summary
              if first > start]
    if capped:
        print("\n%d series start later than the requested %s. The ICE BofA "
              "series serve a rolling window and ignore the date parameters, "
              "so this is their whole available history and it moves."
              % (len(capped), start))
        for sid, first in capped:
            print("  %-16s earliest available %s" % (sid, first))

    if revisions:
        print("\n%d stored values have changed at FRED. Not rewritten."
              % len(revisions))
        for sid, date, was, now in revisions[:20]:
            print("  %s %s  stored %s  now %s" % (sid, date, was, now))
        if len(revisions) > 20:
            print("  ... %d more" % (len(revisions) - 20))
    else:
        print("\nno revisions to stored values")

    if args.dry_run:
        print("\ndry run, nothing written. %d rows would be appended."
              % len(new_rows))
        return
    if not new_rows:
        print("\nnothing new to append. %s is already current." % DEST)
        return

    new_rows.sort(key=lambda r: (r["date"], r["entity"]))
    exists = os.path.exists(DEST) and os.path.getsize(DEST) > 0
    with open(DEST, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if not exists:
            w.writeheader()
        w.writerows(new_rows)
    print("\nwrote %s (+%d rows, %s to %s)"
          % (DEST, len(new_rows), new_rows[0]["date"], new_rows[-1]["date"]))
    print("wrote %s (%d series)" % (raw_dir, len(series)))


if __name__ == "__main__":
    main()
