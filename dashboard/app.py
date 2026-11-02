"""Private dashboard. Home page mirrors the weekly brief's three sections.

Deliberately the same three sections in the same order as the brief, with
the same numbers from scripts/brief_data.py. The brief is what arrives by
email; this is the same week with room to click into it. Someone reading
one and then the other should never have to work out which is right.

Run locally:
    streamlit run dashboard/app.py

Deployment is in docs/dashboard.md.
"""

import datetime as dt
import os
import sys

import pandas as pd
import streamlit as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.chdir(ROOT)

import brief_data as bd  # noqa: E402

st.set_page_config(page_title="AI infra scorecard", page_icon="chart",
                   layout="wide")

COLOUR = {bd.GREEN: "#1baf7a", bd.AMBER: "#eb6834", bd.RED: "#d1344a"}


@st.cache_data(ttl=600)
def load(date_iso):
    today = dt.date.fromisoformat(date_iso)
    return {
        "signals": bd.pillar_signals(today, record=False),
        "moves": bd.biggest_moves(today),
        "financing": bd.financing_changes(),
        "calls": bd.open_calls(),
        "upcoming": bd.upcoming(today),
    }


def latest_data_date():
    """Newest date across the pillar files, so the page says how fresh it is."""
    newest = ""
    for pillar in ("elasticity", "credit", "open_source_share"):
        for r in bd._rows("data/scorecard/%s.csv" % pillar):
            if r.get("date", "") > newest:
                newest = r["date"]
    return newest


st.title("AI infrastructure scorecard")

today = dt.date.today()
data = load(today.isoformat())
signals = data["signals"]
claims, reporting = data["upcoming"]

green = sum(1 for s in signals if s["signal"] == bd.GREEN)
amber = sum(1 for s in signals if s["signal"] == bd.AMBER)
red = sum(1 for s in signals if s["signal"] == bd.RED)

st.caption(
    "%d green, %d amber, %d not built. Newest data point %s. "
    "This page reports what was collected and what the numbers are. It does "
    "not interpret them."
    % (green, amber, red, latest_data_date() or "none"))

# ------------------------------------------------- 1. Where things stand

st.header("1. Where things stand")

cols = st.columns(len(signals))
for col, s in zip(cols, signals):
    with col:
        st.markdown(
            "<div style='border-left:6px solid %s;padding-left:10px'>"
            "<strong>%s</strong><br><span style='color:#666;font-size:0.85em'>"
            "%s</span></div>" % (COLOUR[s["signal"]], s["pillar"],
                                 s["reason"]),
            unsafe_allow_html=True)
        if s["changed"]:
            st.caption("changed from %s" % s["previous"])

st.caption(
    "Signals describe the evidence, not the thesis. Green means the pillar "
    "is collecting and current. Red means this project is not measuring it "
    "yet, which is a fact about the project rather than about AI "
    "infrastructure. A thesis-facing signal would have to be driven by "
    "scored claims, and no claim can be scored before its horizon.")

# -------------------------------------------------------- 2. What moved

st.header("2. What moved")

left, right = st.columns([3, 2])

with left:
    st.subheader("Biggest moves")
    if data["moves"]:
        st.dataframe(
            pd.DataFrame([{
                "series": m["label"],
                "level": m["level"],
                "unit": m["unit"],
                "week": round(m["move"], 3),
                "as of": m["as_of"],
            } for m in data["moves"]]),
            hide_index=True, use_container_width=True)
        st.caption("Ranked by size against each series' own alert threshold, "
                   "so basis points and a price ratio sit on one scale.")
    else:
        st.write("Nothing moved enough to report.")

    st.subheader("Financing")
    if data["financing"]:
        for f in data["financing"]:
            st.write("- " + f["text"])
    else:
        st.write("No new instruments or rate changes. Filings are quarterly, "
                 "so most weeks look like this.")

with right:
    st.subheader("Open calls")
    if not data["calls"]:
        st.info("None open. `data/open_calls.csv` is empty until you write "
                "one. Calls are judgements, and the judgements here are "
                "yours.")
    else:
        for c in data["calls"]:
            box = st.warning if c.get("near_exit") else st.container
            with (box("") if c.get("near_exit") else st.container()):
                st.markdown("**%s** %s %s" % (c["call_id"],
                                              c.get("direction", ""),
                                              c.get("entity", "")))
                if c.get("current") is not None:
                    st.write("%s now %s, entry %s"
                             % (c.get("benchmark_metric", ""),
                                c["current"], c.get("entry_level", "")))
                    if c.get("distance_pct") is not None:
                        st.progress(
                            max(0.0, min(1.0,
                                         1 - c["distance_pct"] / 100.0)),
                            text="%.0f%% of the way to exit"
                                 % (100 - c["distance_pct"]))
                if c.get("near_exit"):
                    st.write("**Near exit.** %s"
                             % c.get("exit_condition", "not stated"))

# ------------------------------------------------- 3. What needs attention

st.header("3. What needs attention")

a, b = st.columns(2)

with a:
    st.subheader("Claims coming due")
    if claims:
        for c in claims:
            label = ("overdue by %d days" % abs(c["days"]) if c["overdue"]
                     else "in %d days" % c["days"])
            with st.expander("%s  %s  %s" % (c["claim_id"],
                                             c["horizon_date"], label),
                             expanded=c["overdue"]):
                st.write(c["claim_text"])
                st.caption("Resolution test: %s"
                           % (c["resolution_criterion"] or "not written"))
    else:
        st.write("Nothing due in the next 45 days.")

with b:
    st.subheader("Reporting soon")
    if reporting:
        st.dataframe(
            pd.DataFrame([{
                "ticker": r["ticker"],
                "company": r["company"],
                "date": r["date"],
                "estimated": "yes" if r["estimated"] else "announced",
            } for r in reporting]),
            hide_index=True, use_container_width=True)
        st.caption("Estimated dates are projected from past filing cadence, "
                   "not announced. They will be wrong by days. Announced "
                   "dates go in `config/earnings_overrides.json`.")
    else:
        st.write("Nothing in the next 14 days.")

st.divider()
st.caption("Use the pages in the sidebar for the underlying series. "
           "Everything here is public information; see `docs/methodology.md` "
           "for how each number is produced and `docs/decisions.md` for why.")
