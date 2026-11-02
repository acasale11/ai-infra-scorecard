"""The question box: ask Claude about what is in the scorecard.

A reading aid over the committed data, not a research assistant. It is given
a compact snapshot of the repo and told to answer from that and say so when
the answer is not there. It is explicitly told not to write notes, theses or
recommendations, because those are the owner's and the whole project exists
to show his judgement rather than a model's.

The key is read from Streamlit secrets and never from the repo. Without it
the box renders a short explanation instead of an input, so a fresh clone
and a local run do not break.

Context is sent as a cached prefix, so repeated questions in one session
re-read it at a tenth of the price rather than paying full rate each time.
"""

import datetime as dt
import os
import sys

import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import brief_data as bd  # noqa: E402

MODEL = "claude-opus-5-5"
MAX_TOKENS = 4000
SECRET = "ANTHROPIC_API_KEY"

SYSTEM = """You answer questions about a research repository called the AI \
infrastructure scorecard. It tracks one investment thesis: that AI \
infrastructure wins when the model layer is competitive and low margin, and \
loses if a few frontier labs dominate compute buying.

You are given a snapshot of the repository's data below. Answer from that \
snapshot.

Rules, in order of importance.

1. If the snapshot does not contain the answer, say so plainly and say what \
would be needed. Never fill a gap with general knowledge and never present \
recalled facts about these companies as if they came from the data. The \
owner relies on being able to trust that every number you quote is in his \
files.

2. Do not write his notes, theses, pitches or market commentary, and do not \
offer investment advice or recommendations. If asked for any of those, say \
that the writing and the judgements are his and offer the relevant numbers \
instead. This is a hard rule, not a preference: the project's value is that \
the analysis is his own.

3. Quote the basis of any figure you give. Prices have three bases and rates \
have two, stated and effective, and mixing the two bases is a mistake this \
project has already made and corrected once. If a comparison would mix \
them, say so rather than making it.

4. Be brief. A few sentences, or a short list. This renders in a dashboard \
panel, not a document.

5. Distinguish the two signals. Data health, green/amber/red, says whether \
evidence is arriving. The thesis view, strengthening/mixed/weakening, is the \
owner's own monthly read. Never infer or invent a thesis view."""


def _fmt_signals():
    today = dt.date.today()
    lines = ["PILLAR SIGNALS (data health, computed) and THESIS VIEW "
             "(the owner's own, never computed):"]
    for s in bd.pillar_signals(today, record=False):
        view = ("%s, set %s, reason: %s"
                % (s["view"], s["view_date"], s["view_reason"])
                if s["view"] else "not set by the owner")
        lines.append("- %s: data health %s (%s); thesis view %s"
                     % (s["pillar"], s["signal"], s["reason"], view))
    return "\n".join(lines)


def _fmt_credit():
    series = {}
    for r in bd._rows(bd.CREDIT):
        if r.get("source") != "FRED":
            continue
        try:
            series.setdefault(r["metric"], {})[r["date"]] = float(r["value"])
        except ValueError:
            continue
    lines = ["CREDIT BENCHMARKS from FRED. Spreads in basis points, yields "
             "in percent. Only a rolling three years is available.",
             "metric | latest date | latest | 3y min | 3y max | 3y median"]
    for metric, obs in sorted(series.items()):
        if not obs:
            continue
        dates = sorted(obs)
        vals = sorted(obs.values())
        lines.append("%s | %s | %.2f | %.2f | %.2f | %.2f"
                     % (metric, dates[-1], obs[dates[-1]], vals[0], vals[-1],
                        vals[len(vals) // 2]))
    return "\n".join(lines)


def _fmt_issuers(limit=140):
    rows = [r for r in bd._rows(bd.CREDIT)
            if r.get("source", "").startswith("SEC")]
    lines = ["ISSUER DEBT TERMS from SEC XBRL instance documents. "
             "instrument_rate_stated and instrument_rate_effective are "
             "different measurements and must not be mixed.",
             "entity | metric | value | unit | period"]
    keep = [r for r in rows
            if r["metric"] in ("instrument_rate_stated",
                               "instrument_rate_effective",
                               "instrument_carrying_amount",
                               "total_debt", "recourse_debt_noncurrent",
                               "nonrecourse_debt_noncurrent",
                               "ppe_useful_life_years",
                               "facility_capacity")]
    for r in keep[:limit]:
        lines.append("%s | %s | %s | %s | %s"
                     % (r["entity"], r["metric"], r["value"], r["unit"],
                        r["date"]))
    if len(keep) > limit:
        lines.append("... %d more rows not shown" % (len(keep) - limit))
    return "\n".join(lines)


def _fmt_prices():
    dates = sorted({r["date"] for r in bd._rows(bd.PRICE_BASES)})
    if not dates:
        return "No price data."
    lines = ["TOKEN PRICES. Three bases exist: cheapest endpoint at any "
             "precision (lower bound), cheapest at fp8 or better (base "
             "case), and the model author's list price (upper bound). Any "
             "figure must name its basis.",
             "Cheapest model clearing the mid-tier capability floor, "
             "output price per million tokens, fp8 base case:"]
    for date in dates[-4:]:
        best = bd.mid_tier_cheapest(date)
        if len(best) == 2:
            lines.append("%s: open $%.2f (%s), closed $%.2f (%s), open "
                         "advantage %.2fx"
                         % (date, best["open_weights"][0],
                            best["open_weights"][1],
                            best["closed_weights"][0],
                            best["closed_weights"][1],
                            best["closed_weights"][0]
                            / best["open_weights"][0]))
    return "\n".join(lines)


def _fmt_claims():
    lines = ["CLAIMS LEDGER. Claims are scored at their horizon and not "
             "before.",
             "id | pillar | horizon | status | claim | resolution test"]
    for r in bd._rows(bd.CLAIMS):
        lines.append("%s | %s | %s | %s | %s | %s"
                     % (r["claim_id"], r["pillar"], r["horizon_date"],
                        r["status"], r["claim_text"],
                        r.get("resolution_criterion", "")))
    return "\n".join(lines)


def _fmt_calls():
    calls = bd.open_calls()
    if not calls:
        return ("OPEN CALLS: none. data/open_calls.csv is empty. The owner "
                "has not written any calls yet.")
    lines = ["OPEN CALLS:"]
    for c in calls:
        lines.append("%s | %s %s | entry %s | current %s | exit %s"
                     % (c["call_id"], c.get("direction", ""),
                        c.get("entity", ""), c.get("entry_level", ""),
                        c.get("current", "not priced"),
                        c.get("exit_condition", "")))
    return "\n".join(lines)


CAVEATS = """KNOWN LIMITS AND CORRECTIONS, which matter when answering:
- A reported finding that CoreWeave's six GPU-backed facilities showed a two
  thirds decline in borrowing cost was WITHDRAWN. It mixed stated and
  effective rates. On the effective basis the ladder is 15, 11, 9, 9, 7, 9
  percent, the 7 percent facility is the only non-recourse one, and the
  newest is back at 9. What survives is that the rate fell from 15 to 9
  across three generations and has been flat since.
- The capability index exists for only a minority of priced models and can
  lag recent releases.
- FRED serves the ICE BofA spread series on a rolling three-year window, so
  no history older than that exists here. The window starts mid-cycle, with
  no quiet period and no prior stress episode, which makes any percentile
  quoted off it a weaker statement than it sounds.
- The CCC index covers every weak borrower in the country and has no known
  AI weighting, so none of its moves can be attributed to this sector.
- There is no secondary bond pricing for any issuer. That needs FINRA TRACE,
  which needs an account that does not exist.
- compute_pricing and buyer_concentration have no collectors and no data.
- 419 facts in the filings are not yet extracted, listed in
  data/credit_unmapped.csv."""


@st.cache_data(ttl=600)
def build_context():
    """The snapshot handed to the model. Cached so it is built once."""
    return "\n\n".join([
        _fmt_signals(), _fmt_credit(), _fmt_prices(), _fmt_issuers(),
        _fmt_claims(), _fmt_calls(), CAVEATS,
    ])


# Streamlit renders its own error into the page when st.secrets is touched
# and no secrets file exists, and that error names the absolute paths it
# searched. On a deployed app those are server paths. So check for a file
# before reading secrets rather than catching the failure afterwards: by
# then the message has already been drawn.
SECRET_PATHS = (
    os.path.join(os.getcwd(), ".streamlit", "secrets.toml"),
    os.path.join(os.path.expanduser("~"), ".streamlit", "secrets.toml"),
)


def _key():
    """The API key from the environment or Streamlit secrets, or None."""
    from_env = (os.environ.get(SECRET) or "").strip()
    if from_env:
        return from_env
    if not any(os.path.exists(p) for p in SECRET_PATHS):
        return None
    try:
        return (st.secrets[SECRET] or "").strip() or None
    except Exception:
        return None


def _client():
    key = _key()
    if not key:
        return None
    try:
        import anthropic
    except ImportError:
        return "missing-package"
    return anthropic.Anthropic(api_key=key)


def render():
    st.header("Ask about the data")

    client = _client()
    if client is None:
        st.info(
            "Not configured. Add `%s` to the app's Streamlit secrets to "
            "enable this box. It is never read from the repository. "
            "Everything else on this dashboard works without it." % SECRET)
        return
    if client == "missing-package":
        st.warning("The `anthropic` package is not installed. It is in "
                   "`requirements.txt`; reinstall and reload.")
        return

    st.caption(
        "Answers come from a snapshot of the committed data and nothing "
        "else. It will say when something is not in the files rather than "
        "filling the gap. It does not write notes or give recommendations, "
        "because the writing and the judgements here are yours.")

    question = st.text_input(
        "Question",
        placeholder="Which issuer has the highest effective rate, and on "
                    "what basis?")
    if not question:
        return

    context = build_context()
    try:
        with st.spinner("Reading the data"):
            with client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                output_config={"effort": "medium"},
                system=[
                    {"type": "text", "text": SYSTEM},
                    # The snapshot is identical across questions in a
                    # session, so cache it rather than paying full rate
                    # for it on every question.
                    {"type": "text",
                     "text": "REPOSITORY SNAPSHOT\n\n" + context,
                     "cache_control": {"type": "ephemeral"}},
                ],
                messages=[{"role": "user", "content": question}],
            ) as stream:
                st.write_stream(stream.text_stream)
    except Exception as exc:
        st.error("The question could not be answered: %s" % exc)
        return

    st.caption("Check anything you intend to use against the underlying "
               "files. This is a reading aid, not a source.")
