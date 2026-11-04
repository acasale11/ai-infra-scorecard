"""Post-collection checks for the weekly run. Writes an issue body or nothing.

Three kinds of check, from config/alert_thresholds.json:

1. A benchmark moved more than its threshold week over week.
2. A series has stopped updating, which usually means the collector broke
   quietly rather than that the market closed.
3. A collector that was supposed to add rows added none, which is the
   failure that otherwise goes unnoticed for weeks because nothing errors.

An alert is not a finding. It says the week is worth a look, which is the
only thing an automated threshold can honestly claim. Nothing here
interprets a move or writes it up, and that is deliberate: interpretation is
the owner's job and the repo's whole point.

Exit code is 0 whether or not anything fired. The workflow reads the output
file to decide about opening an issue, so a quiet week is not a build
failure.

Usage:
    python scripts/check_alerts.py --out alerts.md
"""

import argparse
import csv
import datetime as dt
import json
import os

CONFIG = "config/alert_thresholds.json"
CREDIT = "data/scorecard/credit.csv"
ELASTICITY = "data/scorecard/elasticity.csv"
PRICE_BASES = "data/price_bases.csv"
MID_TIER_FLOOR = 25.0


def fred_series(path):
    """{metric: {date: value}} for the FRED rows only."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r.get("source") != "FRED":
                continue
            try:
                out.setdefault(r["metric"], {})[r["date"]] = float(r["value"])
            except ValueError:
                continue
    return out


def mid_tier_gap(path, date):
    """Cheapest open vs cheapest closed output price at the mid-tier floor.

    Returns the ratio closed/open, or None when either side is missing.
    This is the elasticity pillar's headline number, recomputed here rather
    than imported so a change to the chart script cannot silently change
    what gets alerted on.
    """
    if not os.path.exists(path):
        return None
    best = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["date"] != date or not r.get("cheapest_fp8_output"):
                continue
            try:
                index = float(r["intelligence_index"] or "")
                price = float(r["cheapest_fp8_output"])
            except ValueError:
                continue
            if index < MID_TIER_FLOOR:
                continue
            cls = r["weight_class"]
            if cls not in ("open_weights", "closed_weights"):
                continue
            if cls not in best or price < best[cls]:
                best[cls] = price
    if len(best) != 2 or not best.get("open_weights"):
        return None
    return best["closed_weights"] / best["open_weights"]


def rows_added(path, date, source_prefix=None):
    """How many rows carry this collection date."""
    if not os.path.exists(path):
        return 0
    n = 0
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if source_prefix and not r.get("source", "").startswith(
                    source_prefix):
                continue
            if r["date"] == date or ("collected %s" % date) in r.get(
                    "notes", ""):
                n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--out", default="alerts.md")
    args = ap.parse_args()

    with open(CONFIG, encoding="utf-8") as fh:
        cfg = json.load(fh)

    today = dt.date.fromisoformat(args.date)
    alerts = []

    series = fred_series(CREDIT)
    for metric, threshold in cfg["fred_move"].items():
        if metric.startswith("_"):
            continue
        obs = series.get(metric)
        if not obs:
            alerts.append("- **%s** has no observations at all." % metric)
            continue
        dates = sorted(obs)
        latest = dates[-1]
        age = (today - dt.date.fromisoformat(latest)).days
        if age > cfg["staleness_days"]:
            alerts.append(
                "- **%s** has not updated since %s, %d days ago. The source "
                "may have changed or the collector may be failing quietly."
                % (metric, latest, age))
            continue
        # Most recent observation at least 7 days older than the latest.
        cutoff = dt.date.fromisoformat(latest) - dt.timedelta(days=7)
        earlier = [d for d in dates
                   if dt.date.fromisoformat(d) <= cutoff
                   and (dt.date.fromisoformat(latest)
                        - dt.date.fromisoformat(d)).days
                   <= cfg["lookback_days"]]
        if not earlier:
            continue
        prior = earlier[-1]
        move = obs[latest] - obs[prior]
        if abs(move) >= threshold:
            alerts.append(
                "- **%s** moved %+.2f from %s to %s (%s to %s), against a "
                "threshold of %s."
                % (metric, move, prior, latest, obs[prior], obs[latest],
                   threshold))

    gap_now = mid_tier_gap(PRICE_BASES, args.date)
    prior_dates = set()
    if os.path.exists(PRICE_BASES):
        with open(PRICE_BASES, newline="", encoding="utf-8") as fh:
            prior_dates = {r["date"] for r in csv.DictReader(fh)
                           if r["date"] < args.date}
    if gap_now is not None and prior_dates:
        gap_prev = mid_tier_gap(PRICE_BASES, max(prior_dates))
        if gap_prev:
            change = 100.0 * (gap_now - gap_prev) / gap_prev
            limit = cfg["price_gap_move_pct"]["threshold"]
            if abs(change) >= limit:
                alerts.append(
                    "- **open vs closed price advantage at the mid-tier "
                    "floor** moved %+.1f%%, from %.2fx to %.2fx since %s, "
                    "against a threshold of %s%%."
                    % (change, gap_prev, gap_now, max(prior_dates), limit))

    for key, spec in cfg["expected_rows"].items():
        if key.startswith("_"):
            continue
        # An entry is either a bare minimum (file is the pillar CSV) or an
        # object naming an explicit path, for collectors writing outside
        # data/scorecard/.
        if isinstance(spec, dict):
            path, minimum = spec["path"], spec["min"]
        else:
            path, minimum = "data/scorecard/%s.csv" % key, spec
        n = rows_added(path, args.date)
        if n < minimum:
            alerts.append(
                "- **%s** gained %d rows this run, below the %d expected. "
                "A collector that runs without error and writes nothing is "
                "the failure this check exists for."
                % (key, n, minimum))

    body = ""
    if alerts:
        body = ("The weekly run on %s crossed one or more thresholds. These "
                "are flags, not findings: nothing here has been "
                "interpreted.\n\n%s\n\nThresholds live in "
                "`config/alert_thresholds.json`. The run itself succeeded; "
                "see `notes/weekly/%s.md` for what was collected.\n"
                % (args.date, "\n".join(alerts), args.date))
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(body)
        print("%d alert(s) written to %s\n" % (len(alerts), args.out))
        print(body)
    else:
        if os.path.exists(args.out):
            os.remove(args.out)
        print("no thresholds crossed")


if __name__ == "__main__":
    main()
