# Status

Last updated: 2026-10-30

Plain English summary of where this project actually is. For the rules, see
[docs/methodology.md](docs/methodology.md). For why things were done a
particular way, see [docs/decisions.md](docs/decisions.md).

## In one paragraph

The repo exists, the structure is built, and two of the five pillars have
real data in them. Baker's 16 claims from the October 2026 Atreides call are
logged with a scoring test written for each one. Two collections ran on
2026-10-30: token prices for 430 models, sorted into open and closed weights
and matched to a capability score, and three years of daily credit spread
benchmarks. Nothing has been published yet, and no claim has been scored,
because none of the horizons have arrived.

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

**The FRED credit collector.** Pulls nine daily credit benchmarks, needs no
key or account, and appends only what it has not already stored. Run twice on
2026-10-30: the first run wrote 7,742 rows, the second wrote nothing.

**SEC access.** `scripts/sec_client.py` reaches every kind of EDGAR page the
project needs. Run `python scripts/sec_client.py --check` to re-test all six
at any time; all six passed on 2026-10-30.

**The filings extractor.** Pulls debt terms for all seven borrowers straight
from the structured data attached to each filing, rather than from the
human-readable summary pages the first pass used. 1,118 figures on the first
run. Anything it cannot interpret goes to a gap file instead of being
dropped, currently 419 items.

## What the first model-price run found

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

Mapped on 2026-10-30, and the first of the four sources is now collecting.

**What the benchmark collector found.** Three years of daily credit spreads
are in the file. The headline is that the credit market is picky right now
rather than frightened. The riskiest bucket, CCC, is priced at 1,325 basis
points over Treasuries, which is within a whisker of the worst level in the
three years available. One rung up, BB sits at 194, nearer the middle of its
range, and investment grade at 89, also unremarkable. The gap between CCC and
BB is 1,131 basis points against a three-year normal of 719. Lenders are
charging a lot more for weak credit while barely blinking at decent credit.

The second thing is a warning about how to read any coupon on a 2026 bond.
Investment grade borrowers are paying 5.79% all in, which is near the top of
the range, but the spread portion of that is ordinary. The 10-year Treasury
is at 5.05%. Borrowing is expensive mostly because the risk-free rate is
expensive, not because lenders have turned against corporate credit. So a
9.75% CoreWeave coupon cannot be read as evidence of stress on its own; what
matters is the gap between it and the matching index, and measuring that
needs the issuer-level data this pillar does not have yet.

Three reasons not to lean on either finding. The three years available start
after the 2022 drawdown, so there is no calm period and no previous crisis to
compare against, and a "worst in three years" is a much smaller claim than it
sounds. The CCC index covers every weak borrower in America and has no known
AI exposure, so none of its move can be pinned on this sector. And nothing
collected so far is issuer-specific.

**One thing worth knowing about the source.** FRED only serves the last three
years of these spread series, and ignores any request for more. Older data
drops off and cannot be retrieved. So this repo's copy will, in time, be the
only copy of anything past that window, which makes collecting regularly more
important than it looked and makes the never-rewrite rule load-bearing rather
than tidy.

**What the filings show.** All seven borrowers have now been read by script
straight from the structured data in their filings, which is a better source
than the summary pages the first pass used. CoreWeave carries about $35.6bn
of debt, split between $31.4bn that the parent is on the hook for and $3.7bn
that it is not. That split was checked and is exactly right.

**A correction, and it matters.** The first pass reported that CoreWeave's
six successive GPU-backed loan facilities priced at 15%, 11%, 9%, 9%, SOFR
plus 2.25% and 4.5%, and read that as the cost of borrowing against GPUs
falling by about two thirds. That was wrong, and it was the most quotable
thing in this pillar.

The problem is that those six numbers are not all the same kind of number.
A loan has a headline rate and an all-in rate, and the all-in rate includes
fees and discounts amortised over the life of the loan. The sequence mixed
the two. Put every facility on the all-in basis and it reads 15%, 11%, 9%,
9%, 7% and 9%. The 4.5% that made the story was a headline rate whose all-in
equivalent is 9%. The 7% is the one facility in the set the parent is not
liable for, so it is cheaper for a reason that has nothing to do with time.

What is actually true is narrower. Among the facilities that are comparable,
the rate fell from 15% to 9% across three deals and has sat at 9% for the
three deals since, including the newest. Borrowing against GPUs got cheaper
once, then stopped getting cheaper. That is still worth knowing. It is not a
two thirds decline, and the question of whether these six facilities were
ever comparable is now answered: they were not.

Applied Digital has about $6.7bn, mostly senior secured notes at 6.75% to
9.25%. TeraWulf has $3.2bn of 7.75% secured notes. Cipher has about $6.0bn
and does something different from the others: its secured notes are issued by
named project companies rather than by the parent, and they price at 6.00% to
7.125%, inside CoreWeave's parent-level notes at 9.00% to 9.75%. Lenders
appear to pay up for a ring-fenced data center with a contract attached,
relative to corporate risk at a larger borrower.

That one was checked too, and unlike the loan ladder it holds up: both sets
of rates are headline rates, so they are being compared on the same footing.
It is a testable claim and a good candidate for the ledger, which is the
owner's call to write.

Oracle, Nebius and IREN have now been read. Oracle's quarterly filing does
have no debt section, as suspected, so the annual report was used instead
and it is the largest single source in the set at 510 figures.

**The GPU depreciation question now has real numbers**, which is the
underwriting angle this pillar was built for: how long a lender assumes the
collateral lasts. IREN says its GPU hardware lasts 5 years and its older
mining hardware 4. Nebius says computer equipment is 4 to 5 years. Applied
Digital gives a 3 to 5 year range without naming GPUs, next to buildings at
39 years. CoreWeave does not state a figure in its quarterly filing at all,
which is itself worth chasing.

**What can be tracked for free, and what cannot.** Spread benchmarks from
FRED work today: daily history, no API key, decades of data for investment
grade, high yield, and the BB, B and CCC buckets. Those are the yardstick
every issuer spread gets measured against.

Individual bond prices are harder. FINRA has the trade data but the fixed
income part of its API refused the request without credentials, so that needs
a free account before it can be used.

**The SEC blocker is fixed. One blocker is left.** Automated requests to the
SEC website were being refused, which meant reading filings by hand. That is
solved as of 2026-10-30 and every company in this pillar is now reachable by
script, including the three that had not been read at all: IREN, Oracle and
Nebius.

It turned out to be two separate problems sharing one error message, which is
why the first attempts at it failed. The SEC asks that automated requests say
who is making them, and the standard Python library does not, so it gets
turned away. Separately, the part of the SEC site holding the actual filing
documents refuses any request that does not state what file types it will
accept, which almost every browser does automatically and a bare script does
not. Fixing only the first made the data feeds work while the filings kept
failing, which made it look like the first fix had done nothing.

Neither problem was rate limiting, which is the usual reason to be turned
away from a bulk data source, and slowing down would never have helped. The
script paces itself anyway, at half the rate the SEC permits.

What this unlocks is the narrative debt footnotes, not just the summary
tables. Every figure in the issuer tables above came off a machine-generated
summary page where the columns can be ambiguous, and all of them were flagged
as needing checking against the written footnote. Those footnotes can now be
pulled. They have not been yet; that is the next piece of work.

**FINRA is the remaining blocker**, and it needs an account rather than a fix.

**Proposed metrics** are listed in methodology, in three groups: market
benchmarks from FRED, issuer structure from filings (total debt, how much is
recourse, GPU facility size and drawdown, the rate on the newest facility,
and the GPU depreciation assumption), and bond pricing from FINRA once
available. The first two groups are done. The third still waits on a FINRA
account.

## What is not built yet

- Two of five pillars are empty: `compute_pricing` and `buyer_concentration`.
  `credit` now has both benchmark and issuer-level data; what it lacks is
  secondary bond pricing, which needs FINRA.
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

The credit pillar now has benchmarks, issuer debt terms and a reconciliation
that caught one bad finding. What is left in it is registering for FINRA so
secondary bond prices become reachable, and working through the 419 unmapped
facts to see which are worth extracting.

Separately, the routing experiment, because it is the only thing that can
actually test Baker's routing claim and the token price work cannot.
