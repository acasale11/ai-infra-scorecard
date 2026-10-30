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

## What is not built yet

- Four of five pillars are empty: `compute_pricing`, `buyer_concentration`,
  `credit` and most of `open_source_share`. `credit` is the owner's
  differentiated angle and has nothing in it.
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

Build the routing experiment, because it is the only thing that tests B003,
and start on `credit`, because it is the angle nobody else is covering and
it is currently empty.
