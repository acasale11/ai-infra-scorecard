"""The claims ledger: what was predicted, when it resolves, how it scored."""

import os
import sys

import pandas as pd
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.chdir(ROOT)

import brief_data as bd  # noqa: E402

st.set_page_config(page_title="Claims", layout="wide")
st.title("Claims ledger")

st.caption(
    "Every claim carries a resolution test written before the outcome was "
    "known, which is the thing that makes the exercise honest. Claims are "
    "scored at their horizon and not before.")


@st.cache_data(ttl=600)
def claims():
    return pd.DataFrame(bd._rows("data/claims_ledger.csv"))


df = claims()
if df.empty:
    st.warning("No claims yet.")
    st.stop()

cols = st.columns(4)
for col, status in zip(cols, ["pending", "correct", "partly correct",
                              "wrong"]):
    col.metric(status, int((df["status"] == status).sum()))

pillars = st.multiselect("Pillar", sorted(df["pillar"].unique()))
statuses = st.multiselect("Status", sorted(df["status"].unique()))
view = df
if pillars:
    view = view[view["pillar"].isin(pillars)]
if statuses:
    view = view[view["status"].isin(statuses)]

for _, r in view.sort_values("horizon_date").iterrows():
    with st.expander("%s  %s  due %s  [%s]"
                     % (r["claim_id"], r["pillar"], r["horizon_date"],
                        r["status"])):
        st.write(r["claim_text"])
        st.caption("Said by %s on %s" % (r["speaker"], r["date_said"]))
        st.markdown("**Resolution test**")
        st.write(r["resolution_criterion"] or "not written")
        if r.get("verification_source"):
            st.markdown("**How to verify**")
            st.write(r["verification_source"])
