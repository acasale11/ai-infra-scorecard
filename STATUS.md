# Status

Last updated: 2026-10-30

Plain English summary of where this project actually is. For the rules, see
[docs/methodology.md](docs/methodology.md). For why things were done a
particular way, see [docs/decisions.md](docs/decisions.md).

## In one paragraph

The repo exists, the structure is built, and one of the five pillars has real
data in it. Baker's 16 claims from the October 2026 Atreides call are logged
with a scoring test written for each one. The first data collection ran on
2026-10-30 and produced token prices for 430 models, which have been sorted
into open and closed weights and matched to a capability score. Nothing has
been published yet, and no claim has been scored, because none of the
horizons have arrived.

## What works

**The claims ledger.** All 16 claims are in `data/claims_ledger.csv` with a
horizon date and a written test for how each one gets marked right or wrong.
The tests were written before any outcome was known, which is the thing that
makes the exercise honest. All 16 are still `pending`. The earliest one to
come due is B011 on 2026-11-28.

**The data layer.** CSVs are the record. `scripts/build_db.py` rebuilds a
SQLite database from them for querying. The database is disposable and not
in git. Nothing is ever written back to the CSVs.

**The OpenRouter collector.** Runs on demand, saves the raw response, and
appends price rows without ever touching rows already there. It refuses to
run twice for the same day.

**Weight classification.** Each model is tagged open or closed by checking
Hugging Face for published weights, not by what anyone remembers. 185 open,
203 closed, 42 unclassified, and every row says what evidence put it where.

**Capability tiers.** Models are grouped into frontier, mid and entry using a
third-party intelligence score. The band boundaries were fixed before the
comparison was run and are not adjusted afterwards.

**Price verification.** Prices are checked against the providers' own pricing
pages and recorded three ways, because there is no single right price for a
model.

## What the first run found

Two things, and the second matters more than the first.

**Open-weight models are cheaper at mid-tier capability.** How much cheaper
depends entirely on what price you use. At the cheapest provider serving full
precision, which is the base case, open weights are about 4.3x cheaper. At
the model maker's own list price, 1.5x. At the cheapest provider at any
precision, 6.4x. These are not rounding differences and any published number
has to say which basis it used.

**No open-weight model reaches the frontier tier.** The best open model
scores 31.7 against a frontier floor of 45. Above a score of about 30,
Claude Haiku 5.5 is cheaper than every open model that scores higher, so the
open price advantage ends before the capability range does. This holds under
all three price bases and every traffic mix tested, because it is driven by
open models running out of capability rather than by price.

A third, smaller finding: competition between providers is concentrated.
The median open model has 2 providers and almost no price spread. A handful
of popular models have up to 40 providers and a 14x spread. So "open weights
attract competition" is true of the models people actually use, not of open
weights in general.

## What this does not tell you

The comparison covers off-the-shelf models at published API prices on a
general capability score. Baker's routing claim (B003) is about a fine-tuned
open model behind a router, which is a system rather than a model you can
look up in a price list. This data cannot confirm or refute it. That needs
the routing experiment, which is specified but not built.

The capability score exists for only 54 of the 430 priced models, and it can
lag recent releases. One score in this snapshot looks stale.

## The credit pillar

Mapped on 2026-10-30. No data collected, no collector built, waiting on
approval before anything gets written.

**What the filings show.** Four borrowers were read in detail. CoreWeave
carries about $35.6bn of debt, split between $31.4bn that the parent is on
the hook for and $3.7bn that it is not. The most interesting thing in the
whole pillar is sitting in that filing: CoreWeave has raised six successive
GPU-backed loan facilities, and the interest rate on them has gone 15%, 11%,
9%, 9%, SOFR plus 2.25%, and 4.5%. If that sequence means what it looks like,
the cost of borrowing against GPUs has fallen by roughly two thirds in the
space of six deals. That is close to a direct measurement of whether lenders
are getting more comfortable with GPUs as collateral, which is the question
this pillar exists to answer.

Applied Digital has about $6.7bn, mostly senior secured notes at 6.75% to
9.25%. TeraWulf has $3.2bn of 7.75% secured notes. Cipher has about $6.0bn
and does something different from the others: its secured notes are issued by
named project companies rather than by the parent, and they price at 6.00% to
7.125%, inside CoreWeave's parent-level notes at 9.00% to 9.75%. Lenders
appear to pay up for a ring-fenced data center with a contract attached,
relative to corporate risk at a larger borrower. That is a testable claim and
a good candidate for the ledger.

Oracle, Nebius and IREN have not been read yet. Oracle's quarterly filing has
no debt section, so that one needs the annual report.

**What can be tracked for free, and what cannot.** Spread benchmarks from
FRED work today: daily history, no API key, decades of data for investment
grade, high yield, and the BB, B and CCC buckets. Those are the yardstick
every issuer spread gets measured against.

Individual bond prices are harder. FINRA has the trade data but the fixed
income part of its API refused the request without credentials, so that needs
a free account before it can be used.

**Two things are blocking collection.** Automated requests to the SEC website
were refused from this machine, with several attempts, while the same pages
loaded fine through a browser. Until that is sorted, reading filings is a
manual job. And FINRA needs registering for. Neither is hard, but neither is
done, and a collector that cannot reach its source is not worth writing yet.

**Proposed metrics** are listed in methodology, in three groups: market
benchmarks from FRED, issuer structure from filings (total debt, how much is
recourse, GPU facility size and drawdown, the rate on the newest facility,
and the GPU depreciation assumption), and bond pricing from FINRA once
available. The suggested order is FRED first, because it has no blockers at
all, then fix SEC access, then the filings, then bond prices.

## What is not built yet

- Three of five pillars are empty: `compute_pricing`, `buyer_concentration`
  and `credit`. `credit` now has a source map but no data.
- The routing experiment in `experiments/routing` has a design brief and no
  code.
- Collection is manual. Nothing is scheduled.
- No monthly note has been written. No chart has been published.

## Open questions

Carried in [docs/decisions.md](docs/decisions.md). The live ones: which
holding is "United" in the Atreides top 10; whether 25 organisations can be
mapped to Hugging Face namespaces to shrink the unclassified bucket; whether
a second capability source is needed; and whether OpenRouter alone can
support the `open_source_share` pillar given it cannot see direct API
traffic.

## Next

Waiting on approval of the credit source map before building any collector.
Once approved, the FRED benchmark collector is the obvious first build: free,
no key, daily, decades of history, nothing blocking it.

After that, the routing experiment, because it is the only thing that can
actually test Baker's routing claim and the token price work cannot.
