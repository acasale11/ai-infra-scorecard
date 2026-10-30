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
dropped, currently 419 items. It re-reads a borrower only when that borrower
files something new.

**Weekly automation.** A GitHub Actions workflow runs every collector each
Monday, appends what is new, regenerates the chart, writes a plain-English
summary to `notes/weekly/`, and commits. A collector that fails does not
stop the others; the run opens a GitHub issue listing whatever broke. A
second issue opens if a benchmark moves more than its threshold, if a
series stops updating, or if a collector runs cleanly and writes nothing.
Thresholds are in `config/alert_thresholds.json`.

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

This is the differentiated angle: whether lenders are getting more or less
comfortable financing AI infrastructure, and on what terms. Written here for
someone who reads credit, not code.

### Where the data comes from

Two sources, both free, both now collecting on their own.

**The market backdrop** comes from FRED: daily investment grade and high
yield spreads, the BB, B and CCC buckets underneath them, two effective
yields and the 10-year Treasury. These are the denominator. An issuer paying
9.75% means nothing until you know what comparable credit costs that week.

**The issuer terms** come from SEC filings for seven borrowers: CoreWeave,
Applied Digital, TeraWulf, Cipher, IREN, Nebius and Oracle.

### What the filings extractor does, in plain terms

Every public filing ships in two forms. There is the document a person
reads, and there is a machine-readable version underneath it where each
number is tagged with what it is, which period it belongs to, and which
instrument it describes. The tagged version is what regulators and data
vendors actually consume.

The first pass at this pillar read the human version, by hand. The problem
with that is alignment: once a table of facilities and rates is flattened
into plain text, it is easy for a rate to end up read against the wrong
facility, and there is no way to tell from the result that it happened.

The extractor reads the tagged version instead. Each figure arrives already
attached to its instrument and its period, so a rate on one facility cannot
be read as a rate on another. It pulled 1,118 figures across the seven
borrowers: debt balances, facility sizes, drawn amounts, coupons, all-in
rates, commitment fees, maturities, issue dates and depreciation
assumptions. Anything it cannot confidently identify, currently 419 items,
goes on a list of known gaps rather than being quietly dropped, so the
coverage is visible instead of assumed.

It runs weekly, but it only re-reads a borrower when that borrower has filed
something new. Filings are quarterly, so most weeks it finds nothing and
writes nothing, which is correct.

### The headline finding, and why it was withdrawn

The first pass found what looked like the best result in the whole project.
CoreWeave has raised six successive GPU-backed facilities, and the rates
read 15%, 11%, 9%, 9%, SOFR plus 2.25%, and 4.5%. On its face that is the
cost of borrowing against GPUs falling by roughly two thirds in six deals,
which is close to a direct measurement of lender appetite for the
collateral.

It does not survive checking, for a reason that will be familiar to anyone
who has priced a loan: those six numbers are not the same kind of number.

A facility has a stated rate and an all-in effective rate, and the two
differ by the amortisation of fees and original issue discount. The sequence
took the effective rate for some facilities and the stated rate for others.
The 4.5% that made the story is DDTL 5.0's stated rate. Its effective rate
is 9.00%.

Put every facility on the effective basis:

| facility | stated | effective | drawn, $mm | recourse |
| --- | --- | --- | --- | --- |
| DDTL 1.0 | not disclosed | 15.00% | 1,300 | recourse |
| DDTL 2.0 | not disclosed | 11.00% | 3,190 | recourse |
| DDTL 2.1 | not disclosed | 9.00% | 3,000 | recourse |
| DDTL 3.0 | not disclosed | 9.00% | 2,215 | recourse |
| DDTL 4.0 | SOFR + 2.25% | 7.00% | 2,837 | non-recourse |
| DDTL 5.0 | 4.50% | 9.00% | 1,101 | recourse |

There is a second problem on top of the first. DDTL 4.0, the one facility
that prices below the rest at 7.00%, is also the only non-recourse facility
in the set. It is cheaper because the lender's claim is structured
differently, not because it was raised later.

What is left is narrower and still worth something. Across the four
comparable recourse facilities the effective rate fell from 15% to 11% to
9%, and it has stayed at 9% for every facility since, including the most
recent one. GPU-backed credit at this borrower repriced once, early, and has
not moved since. That is a real observation about lender appetite. It is not
a trend, and the question of whether these six facilities were ever
comparable is now answered: they were not.

The original claim is left standing in the methodology with a correction
attached, rather than deleted. A record that quietly edits its own mistakes
is worth less than one that shows them.

### What does hold up

**The recourse split, exactly.** CoreWeave carries about $35.6bn of debt:
$31.4bn where the parent is on the hook and $3.7bn where it is not. The
machine-readable figures match the hand-read ones to the million. How much
risk sits outside the parent is usually the first question a lender asks,
and CoreWeave is unusual in disclosing the split at all.

**Cipher's project-level pricing, on a like-for-like basis.** Cipher issues
its secured notes out of named project companies rather than the parent:
Cipher Compute at 7.125%, Black Pearl Compute at 6.125%, Stingray Compute at
6.00%. CoreWeave's parent-level senior notes carry 9.00% to 9.75%.

The important point is that this comparison was checked against the trap
that caught the facility ladder, and it passes: both sets are stated rates,
so they are being measured the same way. A ring-fenced data center with a
contract attached funds roughly 250 to 350 basis points inside corporate
risk at a borrower five times the size. That is a testable claim and a
reasonable candidate for the ledger, which is the owner's to write.

One figure from the same table is worth keeping in view as a caution.
Cipher's 2031 convertible has a stated rate of 0.00% and an effective rate
of 6.89%. The gap between the two bases is not a rounding difference.

**Depreciation assumptions, which decide whether the collateral outlives the
loan.** IREN depreciates GPU hardware over 5 years and older mining hardware
over 4. Nebius uses 4 to 5 years for computer equipment. Applied Digital
discloses a 3 to 5 year range without naming GPUs, alongside 39-year
buildings. CoreWeave discloses no useful life in its quarterly filing at
all, which is itself worth chasing given it is the largest borrower here.

### Where the market sits

From the benchmark data, as of 2026-10-29. Three years of history is all
that exists; FRED serves these series on a rolling three-year window and
drops older observations permanently, which is why the repo keeps its own
copy.

Credit is picky rather than frightened. CCC spreads at 1,325 bps sit at the
99th percentile of that three-year range, close to the worst level in it,
while BB at 194 sits at the 73rd and investment grade at 89 sits at the
62nd. The gap between CCC and BB is 1,131 bps against a three-year median of
719. Lenders are charging hard for weak credit and barely blinking at decent
credit.

Separately, and this matters for reading any 2026 coupon: all-in yields are
high for reasons that are mostly not credit. Investment grade yields are at
the 94th percentile of the range while investment grade spreads are at the
62nd, because the 10-year Treasury is at 5.05%. Borrowing is expensive
because the risk-free rate is expensive. A 9.75% coupon is not evidence of
distress on its own; the spread over the matching index is the number that
carries information, and getting to it needs issuer-level bond pricing.

Two cautions on all of that. Three years with no quiet period and no prior
stress episode makes a 99th percentile a weaker statement than it sounds.
And the CCC index covers every weak borrower in the country with no known AI
weighting, so none of its move can be attributed to this sector from
index data alone.

### What is still missing

Secondary bond pricing. Everything above is either a market-wide index or a
term from a filing. What is absent is where these specific bonds actually
trade, which is the number that would say whether the market charges AI
infrastructure borrowers more or less than comparable credits, and which way
it is moving. That needs FINRA TRACE, which needs a free account that has
not been created.

## What is not built yet

- Two of five pillars are empty: `compute_pricing` and `buyer_concentration`.
  `credit` now has both benchmark and issuer-level data; what it lacks is
  secondary bond pricing, which needs FINRA.
- The routing experiment in `experiments/routing` has a design brief and no
  code.
- No monthly note has been written. No chart has been published.
- Nothing warns if a source silently changes shape rather than failing.
  The weekly checks catch a collector that writes nothing and a series that
  stops updating; they would not catch a source that keeps returning
  plausible but wrong numbers.

## Open questions

Carried in [docs/decisions.md](docs/decisions.md). The live ones: which
holding is "United" in the Atreides top 10; whether 25 organisations can be
mapped to Hugging Face namespaces to shrink the unclassified bucket; whether
a second capability source is needed; and whether OpenRouter alone can
support the `open_source_share` pillar given it cannot see direct API
traffic.

## Next

Nothing is being built. Everything that exists now runs on its own each
Monday and reports what it did.

The candidates that remain, for the owner to pick from rather than for
anyone to start unprompted: registering for FINRA so secondary bond prices
become reachable; working through the 419 unmapped facts; and the routing
experiment, which is the only thing that can actually test Baker's routing
claim and which the token price work cannot.
