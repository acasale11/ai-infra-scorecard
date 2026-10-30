"""Write the weekly run's plain-English summary to notes/weekly/<date>.md.

This is a record of what the machine did and what the numbers are. It is
not a note. It reports levels, moves and row counts, and it does not say
what any of it means, which claim it supports, or what anyone should think
about it. The project exists to show the owner's judgement, so the
judgement is not written here.

That restraint is the hard part of this file and it is the reason it exists
as a template rather than as prose generated from the data.

Usage:
    python scripts/weekly_summary.py --date 2026-10-30
"""

import argparse
import csv
import datetime as dt
import json
import os

CREDIT = "data/scorecard/credit.csv"
ELASTICITY = "data/scorecard/elasticity.csv"
OPEN_SHARE = "data/scorecard/open_source_share.csv"
PRICE_BASES = "data/price_bases.csv"
UNMAPPED = "data/credit_unmapped.csv"
OUT_DIR = "notes/weekly"
SERIES_CONFIG = "config/credit_series.json"

LABELS = {
    "ig_oas": "Investment grade spread",
    "bbb_oas": "BBB spread",
    "hy_oas": "High yield spread",
    "hy_bb_oas": "BB spread",
    "hy_b_oas": "B spread",
    "hy_ccc_oas": "CCC spread",
    "ig_effective_yield": "Investment grade yield",
    "hy_effective_yield": "High yield yield",
    "ust_10y": "10-year Treasury",
}


def fred_table(path, today):
    """Rows of (label, latest, unit, move, prior date) for the benchmarks."""
    obs = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r.get("source") != "FRED":
                continue
            try:
                obs.setdefault(r["metric"], {})[r["date"]] = (
                    float(r["value"]), r["unit"])
            except ValueError:
                continue
    out = []
    for metric in LABELS:
        if metric not in obs:
            continue
        dates = sorted(obs[metric])
        latest = dates[-1]
        value, unit = obs[metric][latest]
        cutoff = dt.date.fromisoformat(latest) - dt.timedelta(days=7)
        earlier = [d for d in dates if dt.date.fromisoformat(d) <= cutoff]
        move = None
        prior = earlier[-1] if earlier else None
        if prior:
            move = value - obs[metric][prior][0]
        out.append((LABELS[metric], latest, value, unit, move, prior))
    return out


def count_rows(path, date):
    if not os.path.exists(path):
        return 0
    with open(path, newline="", encoding="utf-8") as fh:
        return sum(1 for r in csv.DictReader(fh)
                   if r["date"] == date
                   or ("collected %s" % date) in r.get("notes", ""))


def mid_tier_prices(path, date):
    """(cheapest open, cheapest closed) output price at the mid-tier floor."""
    best = {}
    if not os.path.exists(path):
        return best
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["date"] != date or not r.get("cheapest_fp8_output"):
                continue
            try:
                index = float(r["intelligence_index"] or "")
                price = float(r["cheapest_fp8_output"])
            except ValueError:
                continue
            if index < 25.0 or r["weight_class"] not in (
                    "open_weights", "closed_weights"):
                continue
            cur = best.get(r["weight_class"])
            if cur is None or price < cur[0]:
                best[r["weight_class"]] = (price, r["model_id"])
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--alerts", default="alerts.md")
    args = ap.parse_args()
    date = args.date

    lines = ["# Weekly run, %s" % date, ""]
    lines.append("Written automatically by `scripts/weekly_summary.py`. It "
                 "records what was collected and what the numbers are. It "
                 "does not interpret them, score any claim, or say what "
                 "follows from them.")
    lines.append("")

    added = {
        "credit": count_rows(CREDIT, date),
        "elasticity": count_rows(ELASTICITY, date),
        "open_source_share": count_rows(OPEN_SHARE, date),
    }
    lines.append("## What was collected")
    lines.append("")
    total = sum(added.values())
    if total:
        lines.append("%d new rows this run." % total)
    else:
        lines.append("No new rows this run, which is worth a look.")
    lines.append("")
    for pillar, n in added.items():
        lines.append("- `%s`: %d rows" % (pillar, n))
    lines.append("")

    if os.path.exists(CREDIT):
        table = fred_table(CREDIT, date)
        if table:
            lines.append("## Credit benchmarks")
            lines.append("")
            lines.append("Where the credit market is, and how it moved over "
                         "the week. Spreads in basis points, yields in "
                         "percent.")
            lines.append("")
            lines.append("| series | as of | level | week |")
            lines.append("| --- | --- | --- | --- |")
            for label, latest, value, unit, move, prior in table:
                shown = ("%.0f bps" % value if unit == "bps"
                         else "%.2f%%" % value)
                delta = "unchanged" if move is None else (
                    "%+.0f bps" % move if unit == "bps" else "%+.2f pts"
                    % move)
                lines.append("| %s | %s | %s | %s |"
                             % (label, latest, shown, delta))
            lines.append("")

    best = mid_tier_prices(PRICE_BASES, date)
    if best:
        lines.append("## Token prices at mid-tier capability")
        lines.append("")
        lines.append("The cheapest model of each kind that clears the "
                     "mid-tier capability floor, priced per million output "
                     "tokens at the cheapest provider running full "
                     "precision.")
        lines.append("")
        for cls, name in (("open_weights", "Open weights"),
                          ("closed_weights", "Closed weights")):
            if cls in best:
                price, model = best[cls]
                lines.append("- %s: $%.2f, %s" % (name, price, model))
        if len(best) == 2:
            ratio = best["closed_weights"][0] / best["open_weights"][0]
            lines.append("")
            lines.append("Open weights are %.2fx cheaper on this basis."
                         % ratio)
            lines.append("")
            lines.append("That multiple is output tokens only. The repo's "
                         "headline comparison uses a blended input and "
                         "output price and gives a different number for the "
                         "same week; see the price basis section in "
                         "`docs/methodology.md`. Two multiples that disagree "
                         "are two different measurements, not an error.")
        lines.append("")

    lines.append("## Flags")
    lines.append("")
    if os.path.exists(args.alerts):
        with open(args.alerts, encoding="utf-8") as fh:
            lines.append(fh.read().strip())
    else:
        lines.append("No thresholds were crossed. Thresholds are in "
                     "`config/alert_thresholds.json`.")
    lines.append("")

    if os.path.exists(UNMAPPED):
        with open(UNMAPPED, newline="", encoding="utf-8") as fh:
            n = sum(1 for _ in csv.DictReader(fh))
        lines.append("## Still not extracted")
        lines.append("")
        lines.append("%d facts in filings that the extractor does not yet "
                     "map, listed in `data/credit_unmapped.csv`." % n)
        lines.append("")

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "%s.md" % date)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines).rstrip() + "\n")
    print("wrote %s" % path)


if __name__ == "__main__":
    main()
