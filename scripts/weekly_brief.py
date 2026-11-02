"""Render the weekly brief: a GitHub issue body and notes/weekly/<date>.md.

Written to be read on a phone in under two minutes. That constraint drives
every formatting choice here: three sections, short lines, no wide tables,
the signal dots first so the whole week has a shape before any detail, and
nothing below the fold that the owner has to scroll for to find out whether
anything needs him.

Three sections, in this order:

  1. Where things stand   the per-pillar signal and what changed
  2. What moved           data moves, financing, open calls
  3. What needs attention alerts, claim deadlines, reporting dates

The dashboard home page mirrors these three, and both read their numbers
from scripts/brief_data.py so they cannot disagree.

This is a digest, not a note. It reports what the numbers are and never
what they mean. The rule that Claude does not write the owner's notes is
not softened by putting the output in an issue instead of a file.

Usage:
    python scripts/weekly_brief.py --date 2026-11-02 --issue issue.md
"""

import argparse
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brief_data as bd  # noqa: E402

OUT_DIR = "notes/weekly"


def section_standing(signals):
    out = ["## 1. Where things stand", ""]
    changed = [s for s in signals if s["changed"]]
    if changed:
        out.append("**Changed this week:** "
                   + ", ".join("%s %s to %s"
                               % (s["pillar"], s["previous"], s["signal"])
                               for s in changed))
    else:
        out.append("No pillar changed signal this week.")
    out.append("")
    for s in signals:
        out.append("%s **%s** %s" % (bd.DOT[s["signal"]], s["pillar"],
                                     s["reason"]))
        # The owner's view sits under the data signal, never merged with it.
        if s["view"]:
            line = "   %s your view: **%s**" % (bd.VIEW_MARK[s["view"]],
                                                s["view"])
            if s["view_reason"]:
                line += " — %s" % _trim(s["view_reason"], 110)
            if s["view_date"]:
                line += " (%s)" % s["view_date"]
            out.append(line)
        else:
            out.append("   your view: not set")
    out.append("")

    dates = {s["view_date"] for s in signals if s["view_date"]}
    if dates:
        out.append("_Your thesis views were last updated %s. Edit "
                   "`data/thesis_view.csv` to change them._" % max(dates))
    else:
        out.append("_No thesis views set yet. They are yours to write, "
                   "monthly, in `data/thesis_view.csv`; nothing sets them "
                   "automatically._")
    out.append("")
    out.append("_The dots describe the evidence, not the thesis. Green means "
               "the pillar is collecting and current. Red means this project "
               "is not measuring it yet, which is a fact about the project "
               "rather than about AI infrastructure. The two signals can "
               "disagree, and that is informative._")
    out.append("")
    return out


def section_moved(moves, financing, calls):
    out = ["## 2. What moved", ""]

    if moves:
        for m in moves:
            out.append("- %s" % m["text"])
    else:
        out.append("- Nothing moved enough to report.")
    out.append("")

    out.append("**Financing**")
    out.append("")
    if financing:
        for f in financing:
            out.append("- %s" % f["text"])
    else:
        out.append("- No new instruments or rate changes. Filings are "
                   "quarterly, so most weeks look like this.")
    out.append("")

    out.append("**Open calls**")
    out.append("")
    if not calls:
        out.append("- None open. `data/open_calls.csv` is empty until you "
                   "write one.")
    else:
        for c in calls:
            line = "- **%s** %s %s" % (c["call_id"], c.get("direction", ""),
                                       c.get("entity", ""))
            if c.get("current") is not None:
                line += (": %s now %s, entry %s"
                         % (c.get("benchmark_metric", ""),
                            _fmt(c["current"], c.get("current_unit", "")),
                            c.get("entry_level", "")))
                if c.get("change") is not None:
                    line += " (%+.2f)" % c["change"]
            else:
                line += ": no benchmark priced"
            if c.get("near_exit"):
                line += "  **near exit**"
            out.append(line)
            if c.get("near_exit"):
                out.append("  - exit condition: %s"
                           % c.get("exit_condition", "not stated"))
    out.append("")
    return out


def _fmt(value, unit):
    if unit == "bps":
        return "%.0f bps" % value
    if unit in ("pct", "percent"):
        return "%.2f%%" % value
    if unit == "x":
        return "%.2fx" % value
    return "%g" % value


def section_attention(alerts, claims, reporting, url):
    out = ["## 3. What needs attention", ""]

    out.append("**Alerts**")
    out.append("")
    if alerts:
        for line in alerts.splitlines():
            line = line.strip()
            if line.startswith("- "):
                out.append(line)
    else:
        out.append("- None. No threshold was crossed.")
    out.append("")

    out.append("**Claims coming due**")
    out.append("")
    if claims:
        for c in claims:
            when = ("**overdue by %d days**" % abs(c["days"]) if c["overdue"]
                    else "in %d days" % c["days"])
            out.append("- `%s` (%s) due %s, %s"
                       % (c["claim_id"], c["pillar"], c["horizon_date"], when))
            out.append("  - %s" % _trim(c["claim_text"], 150))
    else:
        out.append("- Nothing due in the next 45 days.")
    out.append("")

    out.append("**Reporting soon**")
    out.append("")
    if reporting:
        # Capped: a phone brief that lists fifteen tickers gets scrolled
        # past, and the ones furthest out are the least useful.
        shown = reporting[:6]
        for r in shown:
            flag = " (estimated)" if r["estimated"] else ""
            out.append("- %s %s, %s%s"
                       % (r["ticker"], r["company"], r["date"], flag))
        if len(reporting) > len(shown):
            out.append("- and %d more in the next fortnight"
                       % (len(reporting) - len(shown)))
        out.append("")
        out.append("_Estimated dates are projected from past filing cadence, "
                   "not announced. They will be wrong by days._")
    else:
        out.append("- Nothing in the next 14 days.")
    out.append("")

    if url:
        out.append("[Open the dashboard](%s)" % url)
    else:
        out.append("_Dashboard not deployed yet. Set its URL in "
                   "`config/dashboard.json`._")
    out.append("")
    return out


def _trim(text, n):
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def build(date, alerts_path):
    today = dt.date.fromisoformat(date)
    signals = bd.pillar_signals(today, record=True)
    moves = bd.biggest_moves(today)
    financing = bd.financing_changes()
    calls = bd.open_calls()
    claims, reporting = bd.upcoming(today)
    alerts = bd.alerts_text(alerts_path)
    url = bd.dashboard_url()

    reds = [s for s in signals if s["signal"] == bd.RED]
    green = sum(1 for s in signals if s["signal"] == bd.GREEN)
    amber = sum(1 for s in signals if s["signal"] == bd.AMBER)
    headline = "%d green, %d amber, %d not built" % (
        green, amber, len(reds))
    needs = len([c for c in claims if c["days"] <= 14]) + (
        1 if alerts else 0) + len([c for c in calls if c.get("near_exit")])

    lines = ["# Weekly brief: %s" % date, ""]
    lines.append("%s. %s."
                 % (headline,
                    "Nothing needs you this week" if not needs
                    else "%d item%s need%s you"
                    % (needs, "" if needs == 1 else "s",
                       "s" if needs == 1 else "")))
    lines.append("")
    lines.extend(section_standing(signals))
    lines.extend(section_moved(moves, financing, calls))
    lines.extend(section_attention(alerts, claims, reporting, url))
    lines.append("---")
    lines.append("")
    lines.append("_Generated by `scripts/weekly_brief.py`. It records what "
                 "was collected and what the numbers are. It does not "
                 "interpret them or score any claim._")
    return "\n".join(lines).rstrip() + "\n", reds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--alerts", default="alerts.md")
    ap.add_argument("--issue", default=None,
                    help="also write the body here for the GitHub issue")
    args = ap.parse_args()

    body, _ = build(args.date, args.alerts)

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "%s.md" % args.date)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    print("wrote %s" % path)

    if args.issue:
        with open(args.issue, "w", encoding="utf-8") as fh:
            fh.write(body)
        print("wrote %s" % args.issue)

    words = len(body.split())
    print("%d words, about %d seconds to read" % (words, round(words / 3.5)))


if __name__ == "__main__":
    main()
