"""Everything the weekly brief and the dashboard both say.

One module, two renderers. The brief writes markdown for a GitHub issue and
the dashboard draws the same numbers in Streamlit, and both import from
here, so the two cannot drift into quoting different figures for the same
week. That drift is the normal failure of a dashboard that sits beside a
report, and the only reliable fix is to not compute anything twice.

Nothing in this module interprets. It reports levels, moves, states and
dates. What any of it means is the owner's to write.

Used by scripts/weekly_brief.py and dashboard/app.py.
"""

import csv
import datetime as dt
import json
import os

CONFIG_SIGNALS = "config/pillar_signals.json"
CONFIG_ALERTS = "config/alert_thresholds.json"
CONFIG_DASHBOARD = "config/dashboard.json"
SIGNAL_HISTORY = "data/pillar_signals.csv"
CLAIMS = "data/claims_ledger.csv"
CALLS = "data/open_calls.csv"
EARNINGS = "data/earnings_calendar.csv"
CREDIT = "data/scorecard/credit.csv"
PRICE_BASES = "data/price_bases.csv"

SIGNAL_FIELDS = ["date", "pillar", "signal", "reason"]
MID_TIER_FLOOR = 25.0

GREEN, AMBER, RED = "green", "amber", "red"
DOT = {GREEN: "\U0001F7E2", AMBER: "\U0001F7E1", RED: "\U0001F534"}

THESIS_VIEW = "data/thesis_view.csv"
VIEWS = ("strengthening", "mixed", "weakening")
VIEW_MARK = {"strengthening": "↗", "mixed": "→",
             "weakening": "↘"}

FRED_LABELS = {
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


def _json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _rows(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def dashboard_url():
    return (_json(CONFIG_DASHBOARD).get("url") or "").strip()


# ---------------------------------------------------------------- signals

def _pillar_state(pillar, spec, today, stale_days):
    """(signal, reason) for one pillar, from the evidence only."""
    if spec.get("status") == "not_built":
        return RED, "no collector yet"

    rows = []
    for path in spec["files"]:
        rows.extend(_rows(path))
    if not rows:
        return RED, "no data"

    dates = sorted({r["date"] for r in rows if r.get("date")})
    newest = dates[-1]
    age = (today - dt.date.fromisoformat(newest)).days
    if age > stale_days:
        return AMBER, "newest data point is %d days old" % age

    if spec.get("incomplete_because"):
        return AMBER, spec["incomplete_because"]
    return GREEN, "collecting, newest data %s" % newest


def thesis_view():
    """{pillar: {view, reason, date}} from the owner's latest entry.

    Never computed, never inferred, never defaulted to a value. A pillar
    with no row is absent from this dict and shows as not set. The data
    health signal answers whether evidence is arriving; this answers what
    the owner thinks the evidence means, and only he writes it. See
    docs/thesis_view.md.
    """
    latest = {}
    for r in _rows(THESIS_VIEW):
        pillar = (r.get("pillar") or "").strip()
        view = (r.get("view") or "").strip().lower()
        date = (r.get("date") or "").strip()
        if not pillar or view not in VIEWS:
            continue
        if pillar not in latest or date > latest[pillar]["date"]:
            latest[pillar] = {"view": view, "date": date,
                              "reason": (r.get("reason") or "").strip()}
    return latest


def pillar_signals(today, record=False):
    """[{pillar, signal, reason, changed, previous}] plus history append."""
    cfg = _json(CONFIG_SIGNALS)
    stale = cfg.get("stale_days", 10)
    history = _rows(SIGNAL_HISTORY)

    previous = {}
    past = sorted({r["date"] for r in history if r["date"] < today.isoformat()})
    if past:
        last = past[-1]
        previous = {r["pillar"]: r["signal"] for r in history
                    if r["date"] == last}

    views = thesis_view()

    out, new_rows = [], []
    for pillar, spec in cfg["pillars"].items():
        signal, reason = _pillar_state(pillar, spec, today, stale)
        prior = previous.get(pillar)
        view = views.get(pillar)
        out.append({
            "pillar": pillar,
            "signal": signal,
            "reason": reason,
            "previous": prior,
            "changed": bool(prior) and prior != signal,
            "note": spec.get("note", ""),
            # The owner's monthly read. Absent means not set, and nothing
            # is inferred from its absence.
            "view": view["view"] if view else None,
            "view_reason": view["reason"] if view else "",
            "view_date": view["date"] if view else "",
        })
        new_rows.append({"date": today.isoformat(), "pillar": pillar,
                         "signal": signal, "reason": reason})

    if record:
        already = {(r["date"], r["pillar"]) for r in history}
        fresh = [r for r in new_rows
                 if (r["date"], r["pillar"]) not in already]
        if fresh:
            exists = os.path.exists(SIGNAL_HISTORY)
            with open(SIGNAL_HISTORY, "a", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=SIGNAL_FIELDS)
                if not exists or os.path.getsize(SIGNAL_HISTORY) == 0:
                    w.writeheader()
                w.writerows(fresh)
    return out


# ------------------------------------------------------------------ moves

def _fred_series():
    out = {}
    for r in _rows(CREDIT):
        if r.get("source") != "FRED":
            continue
        try:
            out.setdefault(r["metric"], {})[r["date"]] = (
                float(r["value"]), r["unit"])
        except ValueError:
            continue
    return out


def mid_tier_cheapest(date):
    """{weight_class: (price, model_id)} at the mid-tier capability floor."""
    best = {}
    for r in _rows(PRICE_BASES):
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
        if cls not in best or price < best[cls][0]:
            best[cls] = (price, r["model_id"])
    return best


def biggest_moves(today, limit=4):
    """The week's largest moves, ranked by size against their own threshold.

    Ranking on raw size would always return whichever series is quoted in
    the largest unit. Ranking on multiples of each series' own alert
    threshold puts basis points, percentage points and a price ratio on one
    scale, which is the only way a single list of four can be honest.
    """
    thresholds = _json(CONFIG_ALERTS).get("fred_move", {})
    series = _fred_series()
    found = []

    for metric, obs in series.items():
        limit_for = thresholds.get(metric)
        if not limit_for or not obs:
            continue
        dates = sorted(obs)
        latest = dates[-1]
        cutoff = dt.date.fromisoformat(latest) - dt.timedelta(days=7)
        earlier = [d for d in dates if dt.date.fromisoformat(d) <= cutoff]
        if not earlier:
            continue
        prior = earlier[-1]
        move = obs[latest][0] - obs[prior][0]
        unit = obs[latest][1]
        if not move:
            continue
        found.append({
            "label": FRED_LABELS.get(metric, metric),
            "metric": metric,
            "level": obs[latest][0],
            "unit": unit,
            "move": move,
            "as_of": latest,
            "since": prior,
            "severity": abs(move) / limit_for,
            "text": "%s %s, %s on the week" % (
                FRED_LABELS.get(metric, metric),
                ("%.0f bps" % obs[latest][0] if unit == "bps"
                 else "%.2f%%" % obs[latest][0]),
                ("%+.0f bps" % move if unit == "bps" else "%+.2f pts" % move)),
        })

    # The elasticity pillar's headline number, on the same severity scale.
    dates = sorted({r["date"] for r in _rows(PRICE_BASES)})
    if len(dates) >= 2:
        now, before = mid_tier_cheapest(dates[-1]), mid_tier_cheapest(dates[-2])
        if len(now) == 2 and len(before) == 2:
            r_now = now["closed_weights"][0] / now["open_weights"][0]
            r_before = before["closed_weights"][0] / before["open_weights"][0]
            if r_before:
                pct = 100.0 * (r_now - r_before) / r_before
                cap = _json(CONFIG_ALERTS).get(
                    "price_gap_move_pct", {}).get("threshold", 25)
                swapped = now["open_weights"][1] != before["open_weights"][1]
                text = ("Open weights price advantage %.2fx, from %.2fx"
                        % (r_now, r_before))
                if swapped:
                    text += (", because the cheapest open model changed to %s"
                             % now["open_weights"][1])
                found.append({
                    "label": "Open vs closed price advantage",
                    "metric": "mid_tier_price_advantage",
                    "level": r_now, "unit": "x", "move": r_now - r_before,
                    "as_of": dates[-1], "since": dates[-2],
                    "severity": abs(pct) / cap, "text": text})

    found.sort(key=lambda m: -m["severity"])
    return found[:limit]


# -------------------------------------------------------------- financing

def financing_changes():
    """Rate changes and new instruments BETWEEN filings, never within one.

    The within-a-filing comparison was tried first and produced nonsense.
    A filer tags facts against many context dates inside one filing, not
    only the balance sheet date: an issuance date, a redemption test date,
    an amendment date. Comparing an instrument's rate across those dates
    lines up facts that are not the same measurement. It reported IREN's
    2032 convertible moving from 25.000% to 0.250%, which is a 0.25% coupon
    sitting next to some other percentage that the filer tagged with the
    same element on the issuance date.

    So a change here means the same instrument carried a different rate at
    the period end of two different filings. Each filing is identified by
    its accession number, and only its primary period end, the newest date
    among its facts, is compared.

    With one filing per issuer there is nothing to compare and this returns
    nothing, which is correct rather than a gap. Filings are quarterly and
    this runs weekly, so most weeks will look the same.
    """
    import re
    accession = re.compile(r"\b(\d{10}-\d{2}-\d{6})\b")

    # (ticker, accession) -> {(entity, metric): {date: value}}
    by_filing = {}
    for r in _rows(CREDIT):
        if not r.get("source", "").startswith("SEC"):
            continue
        if not r["metric"].startswith("instrument_rate"):
            continue
        m = accession.search(r.get("notes", ""))
        if not m:
            continue
        try:
            value = float(r["value"])
        except ValueError:
            continue
        ticker = r["entity"].split(":")[0]
        key = (ticker, m.group(1))
        by_filing.setdefault(key, {}).setdefault(
            (r["entity"], r["metric"]), {})[r["date"]] = value

    # Per issuer, the filings in the order they were seen.
    per_issuer = {}
    for (ticker, acc), facts in by_filing.items():
        period_end = max((d for f in facts.values() for d in f), default="")
        per_issuer.setdefault(ticker, []).append((period_end, acc, facts))

    changes = []
    for ticker, filings in sorted(per_issuer.items()):
        if len(filings) < 2:
            continue
        filings.sort()
        (prev_end, _, prev_facts) = filings[-2]
        (curr_end, _, curr_facts) = filings[-1]

        for key, obs in sorted(curr_facts.items()):
            entity, metric = key
            if curr_end not in obs:
                continue
            now = obs[curr_end]
            before = prev_facts.get(key, {}).get(prev_end)
            if before is None:
                changes.append({
                    "entity": entity, "metric": metric, "from": None,
                    "to": now, "as_of": curr_end,
                    "text": "%s is new at %.3f%% (%s)"
                            % (entity, now,
                               metric.replace("instrument_rate_", ""))})
            elif before != now:
                changes.append({
                    "entity": entity, "metric": metric, "from": before,
                    "to": now, "as_of": curr_end,
                    "text": "%s %s moved from %.3f%% to %.3f%% between the "
                            "%s and %s filings"
                            % (entity, metric.replace("instrument_rate_", ""),
                               before, now, prev_end, curr_end)})
    return changes


# ------------------------------------------------------------------ calls

def _latest_metric_value(metric):
    """Newest value of a scorecard metric, across every pillar file."""
    best = None
    for pillar in ("credit", "elasticity", "open_source_share",
                   "compute_pricing", "buyer_concentration"):
        for r in _rows("data/scorecard/%s.csv" % pillar):
            if r["metric"] != metric:
                continue
            try:
                value = float(r["value"])
            except ValueError:
                continue
            if best is None or r["date"] > best[0]:
                best = (r["date"], value, r["unit"])
    return best


def open_calls():
    """[{...call, current, change, distance_to_exit, near_exit}]."""
    out = []
    for call in _rows(CALLS):
        if call.get("status", "").strip() not in ("open", ""):
            continue
        if not call.get("call_id"):
            continue
        row = dict(call)
        row["current"] = None
        row["change"] = None
        row["near_exit"] = False
        row["distance_pct"] = None

        metric = (call.get("benchmark_metric") or "").strip()
        if metric:
            found = _latest_metric_value(metric)
            if found:
                as_of, value, unit = found
                row["current"] = value
                row["as_of"] = as_of
                row["current_unit"] = unit
                try:
                    entry = float(call["entry_level"])
                    row["change"] = value - entry
                except (ValueError, KeyError):
                    pass
                try:
                    exit_level = float(call["exit_level"])
                    entry = float(call["entry_level"])
                    span = abs(exit_level - entry)
                    if span:
                        travelled = abs(value - entry) / span
                        row["distance_pct"] = 100.0 * (1 - travelled)
                        row["near_exit"] = travelled >= 0.8
                except (ValueError, KeyError):
                    pass
        out.append(row)
    return out


# -------------------------------------------------------------- deadlines

def upcoming(today, claim_days=45, earnings_days=14):
    """(claims due, companies reporting) inside their windows."""
    claims = []
    for r in _rows(CLAIMS):
        horizon = (r.get("horizon_date") or "").strip()
        if not horizon or r.get("status") != "pending":
            continue
        try:
            due = dt.date.fromisoformat(horizon)
        except ValueError:
            continue
        days = (due - today).days
        if days <= claim_days:
            claims.append({
                "claim_id": r["claim_id"], "pillar": r["pillar"],
                "horizon_date": horizon, "days": days,
                "overdue": days < 0,
                "claim_text": r["claim_text"],
                "resolution_criterion": r.get("resolution_criterion", "")})
    claims.sort(key=lambda c: c["horizon_date"])

    reporting = []
    for r in _rows(EARNINGS):
        try:
            when = dt.date.fromisoformat(r["next_filing_estimate"])
        except (ValueError, KeyError):
            continue
        days = (when - today).days
        if 0 <= days <= earnings_days:
            reporting.append({
                "ticker": r["ticker"], "company": r["company"],
                "date": r["next_filing_estimate"], "days": days,
                "estimated": r["basis"].startswith("estimated")})
    reporting.sort(key=lambda r: r["date"])
    return claims, reporting


# ----------------------------------------------------------------- alerts

def alerts_text(path="alerts.md"):
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as fh:
        return fh.read().strip()
