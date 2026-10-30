"""Collector: issuer debt terms from SEC XBRL instance documents.

Reads the XBRL instance document attached to each filing, not the R##.htm
rendering pages. That distinction is the whole point of this script.

The rendering pages are HTML tables generated from the XBRL for human
reading. Flattening one to text loses the column alignment, which is how the
first pass at the credit source map produced figures that had to be flagged
as unconfirmed. The instance document carries the same facts with no
flattening at all: every fact has an explicit context naming its period and
its dimensional members, so a 9.00% belonging to DDTL 2.1 cannot be read as
belonging to DDTL 3.0.

What the instance gives that the companyfacts API does not: dimensional
facts. The XBRL frames and companyfacts APIs return consolidated values
only, so `LongTermDebt` for the whole company is there but the rate on an
individual facility is not. Instrument-level detail is the pillar's subject,
so the instance document is the only usable source.

Two rates per instrument, and they are not the same thing. A filer tags
`DebtInstrumentInterestRateStatedPercentage` for the coupon or stated rate
and `DebtInstrumentInterestRateEffectivePercentage` for the rate that
includes discount and issuance cost amortisation. Both are extracted under
separate metric names and neither is converted into the other. Mixing the
two across instruments produces a comparison that looks like a trend and is
not one.

Member names are preserved verbatim from the filing, as `TICKER:MemberName`
in the entity column. No attempt is made to translate `DDTL2.1FacilityMember`
into a friendly name, because the translation would be a guess that later
readers could not check. The one classification applied is whether a member
looks like a GPU-backed facility, driven by the substring list in
config/credit_issuers.json and recorded in the notes column.

Anything this script cannot map is written to data/credit_unmapped.csv with
the tag, the member and the value, rather than dropped. The gap list is the
honest part of the output.

Append only. Refuses to run twice for the same collection date.

Usage:
    python scripts/extract_filings.py
    python scripts/extract_filings.py --dry-run
    python scripts/extract_filings.py --ticker CRWV
"""

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sec_client import SecClient  # noqa: E402

CONFIG = "config/credit_issuers.json"
RAW_DIR = "data/raw/sec/%s"
DEST = "data/scorecard/credit.csv"
UNMAPPED = "data/credit_unmapped.csv"
SOURCE_NAME = "SEC XBRL instance document"

FIELDS = ["date", "entity", "entity_class", "metric", "value", "unit",
          "source", "source_url", "notes"]
UNMAPPED_FIELDS = ["date", "ticker", "tag", "members", "value", "unit",
                   "period", "reason"]

# Tag -> (metric, unit). The unit decides the conversion:
#   usd_mm  divide by 1,000,000
#   pct     multiply by 100, because XBRL carries rates as decimals
#   years   as published
#
# Only tags that mean one unambiguous thing are here. A tag that means
# different things depending on which members are attached is left out and
# lands in the unmapped file instead, where it can be looked at.
TAG_MAP = {
    # Consolidated debt. LongTermDebt is the total carrying amount including
    # the current portion; the two components are kept separately because
    # filers are inconsistent about which they tag.
    "LongTermDebt": ("total_debt", "usd_mm"),
    "LongTermDebtNoncurrent": ("long_term_debt_noncurrent", "usd_mm"),
    "LongTermDebtCurrent": ("long_term_debt_current", "usd_mm"),

    # Recourse split. These are company-specific tags rather than us-gaap,
    # which is why they are matched on local name and not on namespace.
    # CoreWeave tags them; most filers do not, and their absence is the
    # finding rather than an error.
    "RecourseDebtNonCurrent": ("recourse_debt_noncurrent", "usd_mm"),
    "RecourseDebtCurrent": ("recourse_debt_current", "usd_mm"),
    "NonRecourseDebtNonCurrent": ("nonrecourse_debt_noncurrent", "usd_mm"),
    "NonRecourseDebtCurrent": ("nonrecourse_debt_current", "usd_mm"),

    # Instrument level. Carried per member.
    "DebtInstrumentCarryingAmount": ("instrument_carrying_amount", "usd_mm"),
    "DebtInstrumentFaceAmount": ("instrument_face_amount", "usd_mm"),
    "DebtInstrumentInterestRateStatedPercentage":
        ("instrument_rate_stated", "pct"),
    "DebtInstrumentInterestRateEffectivePercentage":
        ("instrument_rate_effective", "pct"),
    "DebtInstrumentBasisSpreadOnVariableRate1":
        ("instrument_spread_over_benchmark", "pct"),
    "DebtInstrumentUnamortizedDiscountPremiumAndDebtIssuanceCostsNet":
        ("instrument_unamortized_discount", "usd_mm"),
    "DebtInstrumentFairValue": ("instrument_fair_value", "usd_mm"),

    # Facilities.
    "LineOfCreditFacilityMaximumBorrowingCapacity":
        ("facility_capacity", "usd_mm"),
    "LineOfCreditFacilityRemainingBorrowingCapacity":
        ("facility_undrawn", "usd_mm"),
    "LineOfCredit": ("facility_drawn", "usd_mm"),
    "LineOfCreditFacilityUnusedCapacityCommitmentFeePercentage":
        ("facility_commitment_fee", "pct"),

    # Convertibles, which several of these issuers lean on heavily.
    "ConvertibleDebt": ("convertible_debt_carrying", "usd_mm"),
    "ConvertibleDebtGross": ("convertible_debt_gross", "usd_mm"),

    # A mark on the debt, where the filer gives one. Most do not, and
    # CoreWeave's fair value note covers securities and a swap but not its
    # own borrowings, so this is expected to be sparse.
    "SeniorDebtFairValueDisclosures": ("senior_debt_fair_value", "usd_mm"),
    "ConvertibleDebtFairValueDisclosures":
        ("convertible_debt_fair_value", "usd_mm"),

    # Dates, carried as ISO strings rather than numbers. Maturity is a key
    # term in its own right and issuance date is what makes a rate ladder a
    # dated sequence rather than a list.
    "DebtInstrumentMaturityDate": ("instrument_maturity_date", "date"),
    "DebtInstrumentIssuanceDate1": ("instrument_issuance_date", "date"),

    # The underwriting assumption that decides whether the collateral
    # outlives the loan. XBRL carries durations as ISO 8601, so a five year
    # life arrives as "P5Y" and has to be parsed rather than cast.
    "PropertyPlantAndEquipmentUsefulLife":
        ("ppe_useful_life_years", "years"),
}

ISO_DURATION = re.compile(
    r"^P(?:(\d+(?:\.\d+)?)Y)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)D)?$")

# Debt-adjacent tags worth listing in the gap file when they appear without
# a mapping, so the next pass knows what was left on the table.
INTERESTING = re.compile(
    r"Debt|LineOfCredit|Collateral|Pledg|Commitment|UsefulLife|Recourse",
    re.IGNORECASE)

# TextBlock tags hold an entire rendered footnote, HTML and all. They are
# disclosure prose rather than facts, and one of them is 130 KB on its own.
# Listing them in the gap file made it 2.3 MB of markup and broke the CSV
# reader in build_db.py. They are skipped, and any other oversized value is
# truncated, because the gap file exists to say what was missed, not to
# hold a second copy of the filing.
TEXT_BLOCK = re.compile(r"TextBlock$")
MAX_GAP_VALUE = 200

XBRL_INSTANT = "{http://www.xbrl.org/2003/instance}instant"
XBRL_END = "{http://www.xbrl.org/2003/instance}endDate"


def local(tag):
    return tag.split("}")[-1]


def load_contexts(root):
    """{context id: (period end, [member names])}."""
    out = {}
    for el in root:
        if local(el.tag) != "context":
            continue
        instants = [e.text for e in el.iter() if e.tag == XBRL_INSTANT]
        ends = [e.text for e in el.iter() if e.tag == XBRL_END]
        period = (instants or ends or [""])[0]
        members = [m.text.split(":")[-1] for m in el.iter()
                   if m.tag.endswith("explicitMember") and m.text]
        out[el.get("id")] = (period, members)
    return out


def load_units(root):
    """{unit id: measure local name}, e.g. 'usd' -> 'USD', 'pure' -> 'pure'."""
    out = {}
    for el in root:
        if local(el.tag) != "unit":
            continue
        measures = [local(m.text or "") for m in el.iter()
                    if local(m.tag) == "measure"]
        out[el.get("id")] = "/".join(measures)
    return out


def find_instance(sec, cik, accession):
    """URL of the XBRL instance document in a filing, or None.

    The instance is the _htm.xml file. The _cal, _def, _lab and _pre files
    are the linkbases and carry no facts.
    """
    base = ("https://www.sec.gov/Archives/edgar/data/%d/%s"
            % (int(cik), accession.replace("-", "")))
    idx = sec.json(base + "/index.json")
    names = [i["name"] for i in idx["directory"]["item"]]
    for name in names:
        if (name.endswith("_htm.xml")
                and not re.search(r"_(cal|def|lab|pre)\.xml$", name)):
            return base + "/" + name
    return None


def latest_filing(sec, cik, forms):
    """(form, accession, filing date): newest filing of the best form.

    Form preference wins over recency, because `forms` is ordered best
    first in the config. Oracle is why: its 10-Q is more recent than its
    10-K and carries no debt disclosure at all, so taking the newest
    filing would return almost nothing.
    """
    sub = sec.json("https://data.sec.gov/submissions/CIK%s.json" % cik)
    rec = sub["filings"]["recent"]
    found = list(zip(rec["form"], rec["accessionNumber"], rec["filingDate"]))
    for form in forms:
        matches = [f for f in found if f[0] == form]
        if matches:
            return max(matches, key=lambda f: f[2])
    return None


def convert(raw, unit_kind, measure):
    """Value in the unit this repo stores, or None if it cannot be trusted.

    Returns a float for numeric kinds and a string for dates, so callers
    format rather than assume.
    """
    raw = (raw or "").strip()
    if not raw:
        return None

    if unit_kind == "date":
        return raw if re.match(r"^\d{4}-\d{2}-\d{2}$", raw) else None

    if unit_kind == "years":
        # ISO 8601 duration, e.g. P5Y, P3Y6M. Months and days are converted
        # on 12 and 365, which is close enough for a depreciation life and
        # wrong enough to say so.
        m = ISO_DURATION.match(raw)
        if m and any(m.groups()):
            y, mo, d = (float(g or 0) for g in m.groups())
            return y + mo / 12.0 + d / 365.0
        try:
            return float(raw)
        except ValueError:
            return None

    try:
        value = float(raw)
    except ValueError:
        return None
    if unit_kind == "usd_mm":
        # Guard against a filer tagging a monetary fact with a non-USD unit.
        if measure and "USD" not in measure.upper():
            return None
        return value / 1e6
    if unit_kind == "pct":
        return value * 100.0
    return value


def extract(sec, issuer, collected, raw_dir, dry_run):
    """(metric rows, unmapped rows, a one-line report)."""
    ticker, cik = issuer["ticker"], issuer["cik"]
    found = latest_filing(sec, cik, issuer["forms"])
    if not found:
        return [], [], "%-6s no filing matched %s" % (ticker, issuer["forms"])
    form, accession, filed = found

    url = find_instance(sec, cik, accession)
    if not url:
        return [], [], ("%-6s %-5s %s  no XBRL instance document"
                        % (ticker, form, filed))

    body = sec.get(url)
    if not dry_run:
        os.makedirs(raw_dir, exist_ok=True)
        path = os.path.join(raw_dir, "%s-%s.xml" % (ticker, accession))
        with open(path, "wb") as fh:
            fh.write(body)

    root = ET.fromstring(body)
    contexts = load_contexts(root)
    units = load_units(root)
    patterns = [p.lower() for p in
                CFG["gpu_backed_members"]["patterns"]]

    rows, unmapped = [], []
    for el in root:
        tag = local(el.tag)
        if tag in ("context", "unit"):
            continue
        cref = el.get("contextRef")
        if cref is None or cref not in contexts:
            continue
        period, members = contexts[cref]
        measure = units.get(el.get("unitRef") or "", "")

        if tag not in TAG_MAP:
            if (INTERESTING.search(tag) and el.text
                    and not TEXT_BLOCK.search(tag)):
                value = " ".join(el.text.split())[:MAX_GAP_VALUE]
                unmapped.append({
                    "date": period, "ticker": ticker, "tag": tag,
                    "members": ";".join(members), "value": value,
                    "unit": measure, "period": period,
                    "reason": "tag not in the extractor's map"})
            continue

        metric, unit_kind = TAG_MAP[tag]
        value = convert(el.text, unit_kind, measure)
        if value is None:
            unmapped.append({
                "date": period, "ticker": ticker, "tag": tag,
                "members": ";".join(members), "value": (el.text or "").strip(),
                "unit": measure, "period": period,
                "reason": "value or unit could not be converted"})
            continue

        # Members carry the instrument identity. Keep them verbatim.
        if members:
            entity = "%s:%s" % (ticker, members[0])
            note = "members %s" % ";".join(members)
            if any(p in members[0].lower() for p in patterns):
                note += "; gpu_backed by member name"
        else:
            entity = ticker
            note = "consolidated, no dimensions"

        rows.append({
            "date": period,
            "entity": entity,
            "entity_class": issuer["entity_class"],
            "metric": metric,
            "value": value if unit_kind == "date" else "%.6f" % value,
            "unit": unit_kind,
            "source": SOURCE_NAME,
            "source_url": url,
            "notes": "%s %s filed %s; %s; collected %s"
                     % (form, accession, filed, note, collected),
        })

    report = ("%-6s %-5s %s  %4d facts, %3d unmapped, %3d instruments"
              % (ticker, form, filed, len(rows), len(unmapped),
                 len({r["entity"] for r in rows if ":" in r["entity"]})))
    return rows, unmapped, report


def main():
    global CFG
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ticker", action="append")
    args = ap.parse_args()
    collected = args.date

    with open(CONFIG, encoding="utf-8") as fh:
        CFG = json.load(fh)
    issuers = [i for i in CFG["issuers"]
               if not args.ticker or i["ticker"] in args.ticker]
    if not issuers:
        sys.exit("no issuer matched")

    if os.path.exists(DEST):
        with open(DEST, newline="", encoding="utf-8") as fh:
            clash = {r["entity"].split(":")[0] for r in csv.DictReader(fh)
                     if r["source"] == SOURCE_NAME
                     and ("collected %s" % collected) in r["notes"]}
        clash &= {i["ticker"] for i in issuers}
        if clash and not args.dry_run:
            sys.exit("%s already has rows collected %s for %s. Existing rows "
                     "are never modified." % (DEST, collected, sorted(clash)))

    sec = SecClient()
    raw_dir = RAW_DIR % collected
    all_rows, all_unmapped = [], []
    print("%-6s %-5s %-11s %s" % ("ticker", "form", "filed", "result"))
    for issuer in issuers:
        try:
            rows, unmapped, report = extract(sec, issuer, collected,
                                             raw_dir, args.dry_run)
        except Exception as exc:
            print("%-6s FAILED %s" % (issuer["ticker"], exc))
            continue
        print("  " + report)
        all_rows.extend(rows)
        all_unmapped.extend(unmapped)

    print("\n%d requests to SEC" % sec.requests)
    print("%d metric rows, %d unmapped facts"
          % (len(all_rows), len(all_unmapped)))

    by_metric = {}
    for r in all_rows:
        by_metric[r["metric"]] = by_metric.get(r["metric"], 0) + 1
    print("\nmetrics extracted:")
    for metric in sorted(by_metric, key=lambda m: -by_metric[m]):
        print("  %-34s %4d" % (metric, by_metric[metric]))

    if args.dry_run:
        print("\ndry run, nothing written.")
        return
    if not all_rows:
        print("\nnothing extracted, nothing written.")
        return

    all_rows.sort(key=lambda r: (r["entity"], r["metric"], r["date"]))
    exists = os.path.exists(DEST) and os.path.getsize(DEST) > 0
    with open(DEST, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if not exists:
            w.writeheader()
        w.writerows(all_rows)
    print("\nwrote %s (+%d rows)" % (DEST, len(all_rows)))

    uexists = os.path.exists(UNMAPPED) and os.path.getsize(UNMAPPED) > 0
    with open(UNMAPPED, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=UNMAPPED_FIELDS)
        if not uexists:
            w.writeheader()
        w.writerows(all_unmapped)
    print("wrote %s (+%d rows)" % (UNMAPPED, len(all_unmapped)))
    print("wrote %s" % raw_dir)


if __name__ == "__main__":
    main()
