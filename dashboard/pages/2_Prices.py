"""Elasticity pillar: capability against price, on all three price bases."""

import os
import sys

import pandas as pd
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.chdir(ROOT)

import brief_data as bd  # noqa: E402

st.set_page_config(page_title="Prices", layout="wide")
st.title("Token prices and capability")


@st.cache_data(ttl=600)
def bases():
    return pd.DataFrame(bd._rows("data/price_bases.csv"))


df = bases()
if df.empty:
    st.warning("No price data yet.")
    st.stop()

dates = sorted(df["date"].unique())
date = st.selectbox("Collection date", dates, index=len(dates) - 1)
snap = df[df["date"] == date].copy()
for col in ("intelligence_index", "cheapest_fp8_output",
            "cheapest_any_output", "author_output"):
    snap[col] = pd.to_numeric(snap[col], errors="coerce")

st.caption(
    "Three price bases, because there is no single right price for a model. "
    "Cheapest endpoint at any precision is the lower bound, cheapest at fp8 "
    "or better is the base case, and the model author's own list price is "
    "the upper bound. Any published figure has to name which it used.")

basis = st.radio("Price basis",
                 ["cheapest_fp8_output", "cheapest_any_output",
                  "author_output"],
                 horizontal=True,
                 format_func=lambda c: {
                     "cheapest_fp8_output": "fp8 or better (base case)",
                     "cheapest_any_output": "any precision (lower bound)",
                     "author_output": "author list (upper bound)"}[c])

scored = snap.dropna(subset=["intelligence_index", basis])
scored = scored[scored["weight_class"].isin(
    ["open_weights", "closed_weights"])]

if scored.empty:
    st.info("Nothing scored on this basis for %s." % date)
else:
    chart = scored.pivot_table(index="intelligence_index",
                               columns="weight_class", values=basis)
    st.scatter_chart(chart)
    st.caption(
        "Output price per million tokens against the Artificial Analysis "
        "intelligence index. That index exists for only a minority of "
        "priced models and can lag recent releases.")

    best = bd.mid_tier_cheapest(date)
    if len(best) == 2:
        cols = st.columns(3)
        cols[0].metric("Cheapest open at mid tier",
                       "$%.2f" % best["open_weights"][0],
                       help=best["open_weights"][1])
        cols[1].metric("Cheapest closed at mid tier",
                       "$%.2f" % best["closed_weights"][0],
                       help=best["closed_weights"][1])
        cols[2].metric("Open advantage",
                       "%.2fx" % (best["closed_weights"][0]
                                  / best["open_weights"][0]))
        st.caption(
            "Output tokens only. The headline comparison in methodology "
            "uses a blended input and output price and gives a different "
            "multiple for the same week. Two multiples that disagree are "
            "two measurements, not an error.")

st.subheader("All models")
st.dataframe(
    snap[["model_id", "org", "weight_class", "tier", "intelligence_index",
          "cheapest_fp8_output", "cheapest_any_output", "author_output",
          "provider_count", "output_price_spread_ratio"]]
    .sort_values("intelligence_index", ascending=False),
    hide_index=True, use_container_width=True)
