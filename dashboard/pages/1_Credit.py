"""Credit pillar: benchmark spreads over time and issuer debt terms."""

import os
import sys

import pandas as pd
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.chdir(ROOT)

import brief_data as bd  # noqa: E402

st.set_page_config(page_title="Credit", layout="wide")
st.title("Credit")


@st.cache_data(ttl=600)
def credit():
    return pd.DataFrame(bd._rows("data/scorecard/credit.csv"))


df = credit()
if df.empty:
    st.warning("No credit data yet.")
    st.stop()

fred = df[df["source"] == "FRED"].copy()
fred["value"] = pd.to_numeric(fred["value"], errors="coerce")

st.subheader("Benchmark spreads")
st.caption(
    "FRED serves these series on a rolling three-year window and drops "
    "older observations permanently, so this repo's copy is the only "
    "surviving record of anything that falls off the back. Basis points.")

spreads = [m for m in bd.FRED_LABELS if m.endswith("_oas")]
picked = st.multiselect("Series", spreads,
                        default=["ig_oas", "hy_oas", "hy_ccc_oas"],
                        format_func=lambda m: bd.FRED_LABELS[m])
if picked:
    wide = (fred[fred["metric"].isin(picked)]
            .pivot_table(index="date", columns="metric", values="value")
            .rename(columns=bd.FRED_LABELS))
    st.line_chart(wide)

st.subheader("Issuer debt terms")
st.caption(
    "Read from each filing's XBRL instance document, so every figure stays "
    "attached to its own instrument rather than to a position in a "
    "flattened table. Stated and effective rates are separate metrics and "
    "are never converted between: mixing them is what produced the "
    "withdrawn DDTL ladder finding. See docs/methodology.md.")

sec = df[df["source"].str.startswith("SEC")].copy()
if sec.empty:
    st.info("No issuer data yet.")
else:
    sec["value"] = pd.to_numeric(sec["value"], errors="coerce")
    issuers = sorted({e.split(":")[0] for e in sec["entity"]})
    who = st.selectbox("Issuer", issuers)
    sub = sec[sec["entity"].str.startswith(who)]
    metric = st.selectbox("Metric", sorted(sub["metric"].unique()))
    show = sub[sub["metric"] == metric][
        ["entity", "date", "value", "unit", "notes"]]
    st.dataframe(show.sort_values(["entity", "date"]),
                 hide_index=True, use_container_width=True)
