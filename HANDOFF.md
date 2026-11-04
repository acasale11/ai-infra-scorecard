# Handoff

Written 2026-11-03, after four days of build. Where the project is, what
runs by itself, what is waiting on the owner, and the decisions that would
be expensive to reverse without knowing why they were made.

For the rules see [docs/methodology.md](docs/methodology.md). For the
reasoning behind every choice see [docs/decisions.md](docs/decisions.md).
For plain-English status see [STATUS.md](STATUS.md). This file is the
orientation layer above all three.

## In three sentences

The collection machinery is built, running on a schedule, and has already
caught a real filing without anyone watching. One pillar of five has data
worth reading, two have none at all, and the parts that depend on the
owner's judgement are built and empty by design. Nothing has been published,
and one of the sixteen claims has been scored.

## What runs without anyone touching it

A GitHub Actions workflow, `.github/workflows/weekly.yml`, every Monday at
11:00 UTC.

It collects FRED credit benchmarks, OpenRouter token prices, weight
classifications and provider competition, re-reads SEC filings only when a
borrower has filed something new, estimates the next filing dates for the
coverage universe, rebuilds the database, checks alert thresholds, writes
the weekly brief, and commits. A collector that fails does not stop the
others; the run opens a GitHub issue naming what broke.

The brief is posted as a GitHub issue titled `Weekly brief: <date>`,
assigned to the owner so GitHub emails it, and the previous week's is
closed. It is also committed to `notes/weekly/`.

It has run twice. Both worked. The second run caught a new Cipher 10-Q and
extracted it while skipping the six unchanged issuers, which is the
deduplication behaving as intended rather than a lucky result.

## Where the data stands

| pillar | rows | state |
| --- | --- | --- |
| `credit` | 8,995 | Benchmarks daily, issuer debt terms for seven borrowers. No secondary bond pricing. |
| `elasticity` | 1,712 | Token prices, two weekly snapshots. |
| `open_source_share` | 1,304 | Provider competition metrics. |
| `compute_pricing` | 0 | No collector. |
| `buyer_concentration` | 0 | No collector. |

Claims ledger: 15 pending, 1 scored. B009 is `unverifiable`, scored
2026-11-02 at its horizon. The next to come due is B011 on 2026-11-28.

## What the data actually says so far

Three findings, with their limits attached. None has been published.

**Open weights are cheaper at mid-tier capability, and how much depends
entirely on the price basis.** On the 2026-10-30 snapshot, at the mid-tier
capability floor, on blended input and output prices at the documented 5:1
token mix: 4.34x at the cheapest provider serving fp8 or better, which is
the base case; 1.48x at the model author's list price; 6.4x at the cheapest
provider at any precision.

Those are blended figures. The weekly brief reports the same comparison on
output tokens only, which gives a different multiple for the same week, and
says so where it prints it. Two multiples that disagree here are two
measurements rather than an error, and any published figure has to name
which it used.

**No open-weight model reaches the frontier tier.** The best scores 31.7
against a frontier floor of 45. Above about index 30 a closed model is
cheaper than every open model that scores higher, so the open price
advantage ends before the capability range does. This holds under all three
price bases and every traffic mix tested, because it is driven by open
models running out of capability rather than by price.

**Credit is picky rather than frightened.** CCC spreads sit near the top of
their three-year range while BB and investment grade sit mid-range. All-in
yields are high mostly because the risk-free rate is high, not because
spreads are wide, which matters when reading any 2026 coupon.

A caution that applies to all three: two weekly snapshots is not a trend,
and the credit percentiles cover three mid-cycle years with no quiet period
and no prior stress episode.

## Waiting on the owner

**The Streamlit dashboard is not deployed.** The last build ran half an hour
on a stale `pandas` pin that forced a source compile; `requirements.txt` now
uses version floors and the fix is pushed. The app needs a reboot or a fresh
deploy to pick it up. Steps and troubleshooting are in
[docs/dashboard.md](docs/dashboard.md). Once deployed, put its URL in
`config/dashboard.json` so every brief links to it.

**Two files ship empty on purpose and stay empty until he writes in them.**

- `data/thesis_view.csv`: the monthly strengthening / mixed / weakening read
  per pillar, with one line of reasoning. See
  [docs/thesis_view.md](docs/thesis_view.md).
- `data/open_calls.csv`: live calls, with a required invalidation column.
  See [docs/open_calls.md](docs/open_calls.md).

Both are wired into the brief and the dashboard and both read "not set"
until filled. Their display paths were exercised with throwaway rows that
were then removed, so they work but have never carried real content.

**The question box has never made a live API call.** The SDK surface, key
handling and the no-key path are verified; the call itself is not. It needs
`ANTHROPIC_API_KEY` in Streamlit secrets.

## Blocked, and on what

**FINRA TRACE** needs a free account that does not exist. Without it there
is no secondary bond pricing, which is the number that would say whether the
market charges AI infrastructure borrowers more or less than comparable
credits. This is the largest single gap in the credit pillar.

**`compute_pricing` and `buyer_concentration`** have no collectors and no
source map. They are not blocked by anything external.

**419 facts** in the filings are extracted but unmapped, listed in
`data/credit_unmapped.csv`.

**The routing experiment** in `experiments/routing` has a design brief and
no code. It is the only thing that can test Baker's routing claim B003,
which the token price work cannot.

## Decisions that would be expensive to reverse

Each of these is recorded with its reasoning and its cost in
[docs/decisions.md](docs/decisions.md). The short version:

**CSVs are canonical, the database is disposable.** `data/research.db` is
rebuilt from the CSVs and gitignored. Nothing is ever written back.

**Append only, everywhere, with two documented exceptions.** Corrections are
new rows or new dated commits. The exceptions are `data/earnings_calendar.csv`
and `data/thesis_view.csv` handling, both of which hold projections or
latest-wins reads rather than measurements, and both say so.

**Stated and effective rates are separate metrics and are never converted
between.** Mixing them produced a finding that had to be withdrawn. Any
sequence of numbers described as a trend must state the basis of every point
first.

**Three price bases, not one.** Cheapest endpoint at any precision is the
lower bound, cheapest at fp8 or better is the base case, the author's list
price is the upper bound. Multi-provider competition on open weights is a
real purchasable advantage; the problem with the headline price was
quantization, not resellers.

**Two signals per pillar, and only one is computed.** Data health, green /
amber / red, says whether evidence is arriving. The thesis view says what it
means and only the owner sets it. A green pillar is not a pillar whose data
supports the thesis, and a red pillar is a statement about this project
rather than about AI infrastructure.

**Claude does not write the published notes.** It builds data, code,
analysis and outlines. The weekly brief is a digest that reports numbers and
states no conclusions. The question box answers from the data and refuses to
write notes or recommendations. This is in CLAUDE.md and is the point of the
project.

**Sessions end with a summary, not a proposal.** Recorded in CLAUDE.md on
2026-11-02. Options go in the open questions section of the decision log;
the end of a session is not where the research agenda gets set.

**The pseudonym is a presentation layer.** No legal name, employer or school
on charts, notes, posts or repo prose. Git metadata is deliberately out of
scope and traceable, and that is accepted rather than overlooked.

## Mistakes made, and what they cost

Recorded because the pattern matters more than any one of them.

**The DDTL ladder finding was withdrawn.** CoreWeave's six GPU-backed
facilities were reported at 15, 11, 9, 9, SOFR plus 2.25 and 4.50 percent,
read as a two thirds decline in the cost of borrowing against GPUs. The
sequence mixed stated and effective rates. On one basis it is 15, 11, 9, 9,
7, 9, the 7 percent facility is the only non-recourse one, and the newest is
back at 9. What survives is that the rate fell once, early, and has been
flat since. The wrong paragraph is kept in methodology with a correction
attached rather than deleted.

**Interpretation ran ahead of the data three times, always toward a cleaner
story.** The frontier gap read as evidence against B003 when it was
consistent with it. The author list price was adopted as the honest basis
when it understated the thing the thesis is about. And a rate ladder was
read as a trend when two of its six points were measured differently. Each
was caught by the owner asking what the numbers measured.

**Two version pins were recalled rather than checked.** `anthropic==1.2.0`
and `pandas==2.2.3` were both roughly two years stale. The second cost half
an hour of Streamlit build time compiling pandas from source. Requirements
now use floors.

**A first draft of the public outputs rule named the school and both
employers** in a file that is itself a public output. Caught by a leak scan
before committing. A rule that forbids naming something cannot be written by
naming it.

## Where to start reading the code

| file | what it does |
| --- | --- |
| `scripts/brief_data.py` | Every number the brief and the dashboard both report. One module, two renderers, so they cannot disagree. |
| `scripts/weekly_brief.py` | Renders the brief. Three sections, phone-readable. |
| `scripts/sec_client.py` | EDGAR access. Run `python scripts/sec_client.py --check` to re-test every endpoint. |
| `scripts/extract_filings.py` | Issuer debt terms from XBRL instance documents, deduplicated by accession. |
| `scripts/collect_fred.py` | Credit benchmarks. The date column holds the observation date, not the collection date, and the docstring says why. |
| `dashboard/app.py` | Home page, mirroring the brief's three sections. |
| `config/*.json` | Every tunable input, each with a comment explaining what it means and what it costs. |

Every collector refuses to run twice for the same date, and every one of
them can be run by hand with `--dry-run` first.
