"""Estimate the next SEC filing date for each public coverage name.

A caveat that has to come first, because the column heading would otherwise
mislead. SEC does not publish a forward earnings calendar. What EDGAR gives
is the date each past filing arrived. This script reads that history and
projects the next one from the issuer's own cadence.

So these are estimated next FILING dates, not announced earnings dates. A
company announces results before it files, usually by a few days to a few
weeks, and it can move its date without telling EDGAR anything. Treat a row
here as "roughly when this issuer next reports", never as a date to diary.

Where a real date is known, put it in config/earnings_overrides.json and it
wins. That file is the place for dates read off an investor relations page.

Method: take the last six 10-Q and 10-K filings, take the median gap
between consecutive ones, add it to the most recent. Median rather than
mean because one late filing should not drag the estimate. Fewer than three
filings means no estimate rather than a bad one.

Writes data/earnings_calendar.csv, replacing it each run. This file is a
projection, not a measurement, so it is not append-only: there is nothing
historical in it to preserve. Every other data file in this repo is
append-only and this is the deliberate exception.

Usage:
    python scripts/earnings_calendar.py
"""

import argparse
import csv
import datetime as dt
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sec_client import SecClient  # noqa: E402

COVERAGE = "data/coverage_universe.csv"
OVERRIDES = "config/earnings_overrides.json"
DEST = "data/earnings_calendar.csv"
TICKER_MAP = "https://www.sec.gov/files/company_tickers.json"
FORMS = {"10-Q", "10-K", "20-F", "6-K"}
MIN_FILINGS = 3
LOOKBACK = 6

FIELDS = ["ticker", "company", "cik", "last_form", "last_filed",
          "median_gap_days", "next_filing_estimate", "basis"]


def ticker_to_cik(sec):
    """{TICKER: zero-padded CIK} from SEC's own mapping file."""
    data = sec.json(TICKER_MAP)
    out = {}
    for row in data.values():
        out[row["ticker"].upper()] = str(row["cik_str"]).zfill(10)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    args = ap.parse_args()
    today = dt.date.fromisoformat(args.date)

    overrides = {}
    if os.path.exists(OVERRIDES):
        with open(OVERRIDES, encoding="utf-8") as fh:
            overrides = {k.upper(): v for k, v in json.load(fh).items()
                         if not k.startswith("_")}

    with open(COVERAGE, newline="", encoding="utf-8") as fh:
        coverage = [r for r in csv.DictReader(fh) if r["listed"] == "public"]

    sec = SecClient()
    try:
        cik_of = ticker_to_cik(sec)
    except Exception as exc:
        sys.exit("could not fetch SEC's ticker map: %s" % exc)

    rows, missing = [], []
    for company in coverage:
        ticker = company["ticker"].upper()
        cik = cik_of.get(ticker)
        if not cik:
            missing.append(ticker)
            continue
        try:
            sub = sec.json("https://data.sec.gov/submissions/CIK%s.json" % cik)
        except Exception:
            missing.append(ticker)
            continue
        rec = sub["filings"]["recent"]
        filed = sorted({d for f, d in zip(rec["form"], rec["filingDate"])
                        if f in FORMS}, reverse=True)[:LOOKBACK]
        if len(filed) < MIN_FILINGS:
            missing.append(ticker)
            continue
        dates = [dt.date.fromisoformat(d) for d in filed]
        gaps = [(dates[i] - dates[i + 1]).days for i in range(len(dates) - 1)]
        gap = int(statistics.median(gaps))
        last = dates[0]
        nxt = last + dt.timedelta(days=gap)
        # Roll forward if the cadence already puts the estimate in the past.
        while nxt < today:
            nxt += dt.timedelta(days=gap)
        last_form = next(f for f, d in zip(rec["form"], rec["filingDate"])
                         if d == filed[0] and f in FORMS)

        override = overrides.get(ticker)
        rows.append({
            "ticker": ticker,
            "company": company["company"],
            "cik": cik,
            "last_form": last_form,
            "last_filed": filed[0],
            "median_gap_days": gap,
            "next_filing_estimate": override or nxt.isoformat(),
            "basis": ("announced date from config/earnings_overrides.json"
                      if override
                      else "estimated from the last %d filings" % len(filed)),
        })

    rows.sort(key=lambda r: r["next_filing_estimate"])
    with open(DEST, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    print("wrote %s (%d companies)" % (DEST, len(rows)))
    if missing:
        print("no estimate for %d: %s" % (len(missing), ", ".join(missing)))
    print("\nnext six:")
    for r in rows[:6]:
        print("  %-6s %s  %s" % (r["ticker"], r["next_filing_estimate"],
                                 r["basis"]))


if __name__ == "__main__":
    main()
