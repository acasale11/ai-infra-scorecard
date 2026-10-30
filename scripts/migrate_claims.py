"""One-time migration of the original 16 Baker claims into the ledger schema.

Reads the flat claims_ledger.csv from the original repo upload and writes
data/claims_ledger.csv. Kept in the repo so the transform is auditable: every
resolution criterion below was written on 2026-10-30, before any of these
claims resolved.

Usage:
    python scripts/migrate_claims.py --call-date 2026-10-21
    python scripts/migrate_claims.py --call-date 2026-10-21 --dry-run
"""

import argparse
import csv
import datetime as dt
import sys

SOURCE = "claims_ledger.csv"
DEST = "data/claims_ledger.csv"

FIELDS = [
    "claim_id", "date_said", "date_entered", "speaker", "source_type",
    "source_name", "source_url", "claim_text", "pillar", "claim_type",
    "verification_source", "resolution_criterion", "horizon_label",
    "horizon_date", "status", "status_updated", "evidence_url", "notes",
]

# Fixed horizon labels map to fixed dates. See docs/methodology.md.
FIXED_HORIZONS = {
    "Q3 2026": "2026-12-31",
    "point in time": "2026-12-31",
    "Oct 2026": "2026-10-31",
    "ongoing": "2027-10-31",
    "multi-year": "2028-10-31",
}

CRITERIA = {
    "B001": "Correct if OpenRouter open-weight token volume for Q3 2026 is at least 1.8x the Q2 2026 figure and combined OpenAI plus Anthropic volume growth over the same period falls between 40 and 60 percent. Partly correct if open-weight growth is 1.4x to 1.8x. Wrong below 1.4x.",
    "B002": "Correct if Anthropic filings show quarter-on-quarter revenue growth within 10 points of 125 percent in Q2 2026 and 49 percent in Q3 2026, and OpenAI Q3 growth exceeds its Q2 rate. Unverifiable if OpenAI quarterly revenue is never disclosed or credibly reported.",
    "B003": "Scored against experiments/routing using its pre-registered task set. Correct if the routed stack reaches at least 95 percent of the frontier model score at 20 to 35 percent of its cost. Partly correct if cost lands between 35 and 60 percent at that quality. Wrong above 60 percent cost or below 90 percent quality.",
    "B004": "Correct if, for models of comparable active parameter count, measured inference cost per token differs by less than 25 percent between open-weight and closed models. Wrong if closed providers sustain a cost per token more than 2x below open-weight at equal active parameters. This is a claim about cost, not about price.",
    "B005": "Correct if, over the review period, the percentage rise in tokens served exceeds the percentage fall in price per million tokens at fixed capability, so implied total spend rises. Wrong if price falls and implied total spend falls with it. Needs at least four quarters of both series in data/scorecard/elasticity.csv.",
    "B006": "Correct if compute cost as a share of revenue lands within 10 points of each of the three figures (30, 10, 70). Partly correct if the ranking holds, Kimi highest and Anthropic lowest, but magnitudes miss. Unverifiable if the OpenAI and Kimi figures cannot be sourced.",
    "B007": "Correct if aggregate lab compute spend over lab revenue rises from 0.20 to 0.30 in 2024 and reaches 0.45 to 0.55 in 2026. Partly correct if the direction holds but an endpoint falls outside those bands. Unverifiable if private lab compute spend cannot be estimated from public sources.",
    "B008": "Correct if an Oracle earnings call or filing states that renewal pricing on roughly four-year-old GPUs carries a premium of 15 to 25 percent to the prior contract rate. Wrong if renewals are disclosed at a discount. Unverifiable if Oracle never quantifies renewal pricing.",
    "B009": "Correct if a daily GPU rental price index shows 17 or more consecutive up days within October 2026 while the coverage universe infra names fell over the same stretch. Unverifiable if no daily index covering October 2026 can be sourced, since this figure cannot be reconstructed after the fact.",
    "B010": "Correct if coverage universe semis outperform the S and P 500 over the 12 months from the call date. Records separately whether the semi index forward P/E at the call date sat in the bottom decile of its own five-year range, which is the checkable half of the claim.",
    "B011": "Checked against Anthropic S-1/A amendments filed with the SEC on or before 2026-11-28. Correct if an amendment filed by that date reports an October 2026 ARR figure above the prior disclosed figure. Wrong if it reports a figure below the prior disclosed figure, or a figure unchanged from it, since an update that is flat is not a positive one. Unverifiable if no October ARR figure is filed by that date.",
    "B012": "Correct if the S-1 shows positive free cash flow for H1 2026 and operating margin improving in every quarter it presents. Partly correct if FCF is positive but at least one quarter shows margin deterioration. Wrong if H1 2026 FCF is negative.",
    "B013": "Correct if Anthropic disclosed 2027 purchase commitments over consensus 2027 revenue for each counterparty land within 2 points of 5, 4, 10 and 27 percent. Partly correct if the ranking holds and no figure is off by more than 5 points. The revenue estimate used must be recorded, since the denominator drives the answer.",
    "B014": "Correct if at the horizon Anthropic accounts for less than 10 percent of tracked neocloud and hyperscaler AI backlog in data/scorecard/buyer_concentration.csv. Wrong if above 20 percent. Between the two, partly correct.",
    "B015": "Correct if at the horizon open-weight models hold at least 25 percent of tracked served tokens and at least four distinct providers each hold at least 10 percent of frontier-tier tokens. Wrong if two providers together hold more than 70 percent. Between, partly correct.",
    "B016": "Conditional, so the antecedent is scored first. If at the horizon the top two labs account for more than 60 percent of tracked compute purchasing, score the consequent on whether the six named companies show gross margin or multiple compression against the horizon start. If the antecedent never fires the status is unverifiable, not correct, because the condition was never tested.",
}


def horizon_date(label, call_date):
    if label in FIXED_HORIZONS:
        return FIXED_HORIZONS[label]
    if label == "30 days":
        return (call_date + dt.timedelta(days=30)).isoformat()
    if label == "12 months":
        return call_date.replace(year=call_date.year + 1).isoformat()
    raise ValueError("unmapped horizon label: %r" % label)


def build_rows(old, call_date, entry_date):
    rows = []
    for r in old:
        note = (
            "Migrated from the original flat claims_ledger.csv on %s. "
            "Original date_said was month precision (%s); the day comes from "
            "the call date confirmed by the owner."
            % (entry_date, r["date_said"])
        )
        rows.append({
            "claim_id": r["id"],
            "date_said": call_date.isoformat(),
            "date_entered": entry_date,
            "speaker": r["speaker"],
            "source_type": "call",
            "source_name": r["source"],
            "source_url": "",
            "claim_text": r["claim"],
            "pillar": r["pillar"],
            "claim_type": r["type"],
            "verification_source": r["how_to_verify"],
            "resolution_criterion": CRITERIA[r["id"]],
            "horizon_label": r["horizon"],
            "horizon_date": horizon_date(r["horizon"], call_date),
            "status": r["status"],
            "status_updated": "",
            "evidence_url": "",
            "notes": note,
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--call-date", required=True,
                    help="ISO date of the Atreides Q3 2026 update call")
    ap.add_argument("--entry-date", default=dt.date.today().isoformat())
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    call_date = dt.date.fromisoformat(args.call_date)

    with open(SOURCE, newline="", encoding="utf-8") as fh:
        old = list(csv.DictReader(fh))

    missing = [r["id"] for r in old if r["id"] not in CRITERIA]
    if missing:
        sys.exit("no resolution criterion written for: %s" % ", ".join(missing))

    rows = build_rows(old, call_date, args.entry_date)

    if args.dry_run:
        for row in rows:
            print("%s  %s  %-13s -> %s  %-11s %s" % (
                row["claim_id"], row["date_said"], row["horizon_label"],
                row["horizon_date"], row["claim_type"], row["pillar"]))
        print("\n%d claims, no file written" % len(rows))
        return

    with open(DEST, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print("wrote %d claims to %s" % (len(rows), DEST))


if __name__ == "__main__":
    main()
