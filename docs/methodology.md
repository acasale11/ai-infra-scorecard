# Methodology

Last updated: 2026-10-30

## Purpose

This repo is a timestamped record of evidence for and against one thesis: AI
infrastructure is a good place to own capital when the model layer stays
competitive and low margin, and a bad one if a small number of frontier labs
end up dominating compute buying.

The record is only useful if it is honest about when each number was collected
and where it came from. Everything below exists to protect that.

## The five pillars

Use these exact names in file names, the `pillar` column, and commit messages.

| pillar | question it answers |
| --- | --- |
| `elasticity` | When token prices fall, does token volume rise enough to grow total spend? |
| `open_source_share` | What share of tokens actually served comes from open-weight models? |
| `compute_pricing` | What does an hour of GPU time cost, and what does a used or renewed GPU fetch? |
| `buyer_concentration` | How much neocloud and hyperscaler revenue or backlog traces to OpenAI and Anthropic? |
| `credit` | What terms are lenders demanding against GPUs, neocloud cash flows, and data centers? |

## Scorecard files

One CSV per pillar in `data/scorecard/`, appended monthly. All five files
share one header, so they can be stacked into a single table. Columns:

- `date` the date the observation refers to, ISO format `YYYY-MM-DD`
- `entity` what the number is about: a model id, a ticker, a bond, a GPU
  type. Empty where a metric is about the market as a whole.
- `entity_class` how the entity is tagged for grouping, for example
  `open_weights`, `closed_weights`, `neocloud`, `hyperscaler`. Empty where
  `entity` is empty.
- `metric` a stable short name, snake_case, reused month to month
- `value` numeric only, no units, no thousands separators
- `unit` for example `usd_per_mtok`, `usd_per_gpu_hour`, `pct`, `bps`, `usd_mm`
- `source` the publisher, for example `OpenRouter`, `SEC 10-Q`, `Company IR deck`
- `source_url` a direct link, archived if the page is likely to change
- `notes` anything a reader needs in order to reproduce the number

`entity` and `entity_class` are an addition to the seven columns named in
CLAUDE.md. They exist because the pillars are mostly per-entity series. A
price is a price *of a model*, a spread is a spread *on an issuer*. Without
them the entity has to be smuggled into the metric name, which makes the
series unqueryable and breaks the rule that a metric name keeps one
definition forever.

Two rules that matter more than the rest:

1. A metric name, once used, keeps its definition forever. If the definition
   has to change, create a new metric name and leave the old series alone.
2. Record the date you collected the number. If a source publishes a revised
   figure later, add a new row. Do not edit the old one.

### Core KPIs and validation

`config/core_kpis.json` names the metrics the project commits to collecting
reliably: the nine FRED credit benchmarks, the elasticity price advantage, the
four provider-competition metrics, and the quarterly issuer debt facts. It says
which numbers must arrive and stay well formed, not what they mean.

`scripts/validate_data.py` enforces the integrity rules that were previously
kept by hand. It checks that every file carries the nine-column header, that
each row has a date, metric, value and source, that the value parses as a
number or, when the unit is `date`, as a date, that no file holds a duplicate
key, that no observation is dated in the future, that a metric never carries
two units, that stated and effective rates stay separate metrics, and that the
core KPIs are present and, on a fresh run, current. A source url is required
unless the source begins with the word `derived`, which marks a value computed
from other rows rather than fetched.

It runs at the end of the weekly collection, where a failure opens the
collector-failure issue, and on every push through `.github/workflows/tests.yml`
with `--no-freshness`, because committed data can legitimately be a few days
old. The `tests/` suite covers the validator and the collectors' pure logic.

The duplicate rule follows the data. FRED rows are unique on date and metric,
the price files on date, entity and metric. The SEC issuer facts are not: one
instrument's rate repeats across filings, keyed by accession in the notes, so
for those the only hard rule is that a single run did not write a byte-identical
row twice.

### Candidate metrics by pillar

These are starting points, not a fixed list. Add rows to this table as metrics
are adopted.

**elasticity**

- `frontier_input_price_usd_per_mtok` and the matching output price, per named model
- `price_per_mtok_at_fixed_capability` a quality-held-constant price series
- `tokens_served_monthly` where a public aggregator reports it
- `inference_revenue_proxy` price times volume, clearly labelled as derived

**open_source_share**

- `openrouter_open_weight_token_share_pct`
- `openrouter_top_model_token_share_pct`
- `open_weight_share_by_category_pct` for coding, chat, and agents separately

**compute_pricing**

- `h100_sxm_spot_usd_per_gpu_hour` and the same for each later generation
- `h100_reserved_12mo_usd_per_gpu_hour`
- `prior_gen_price_as_pct_of_launch` the resale and renewal decay series
- `cowos_capacity_index` where a credible estimate exists

**buyer_concentration**

- `largest_customer_pct_of_revenue` per company in the coverage universe
- `top_two_customers_pct_of_backlog`
- `rpo_usd_mm` and `rpo_pct_from_named_counterparty`

**credit**

- `bond_spread_bps` per issuer and tranche
- `gpu_backed_loan_advance_rate_pct`
- `gpu_backed_loan_coupon_pct`
- `assumed_gpu_depreciation_life_years` per company
- `datacenter_abs_spread_bps`

## Data layer

The CSVs are the canonical record. `data/research.db` is a SQLite database
built from them by `scripts/build_db.py`, and it is gitignored. It is dropped
and rebuilt from scratch on every run, nothing is ever written back to the
CSVs, and no fact lives in the database that the CSVs do not already hold. If
the two ever disagree, the CSVs are right and the database is stale.

Tables: `claims`, `coverage`, and `scorecard`, the last being all five pillar
files stacked with a `pillar` column. The build refuses to run if the five
files disagree on their header.

## Raw responses

Every collector writes the unmodified API response to
`data/raw/<source>/<collection-date>.json` before it parses anything, and
those files are committed. The parsing in a collector is a judgment that can
turn out to be wrong. The raw response is the thing that lets a number be
re-derived later rather than merely re-collected, which for a price on a
specific past date is impossible.

## Collectors

### OpenRouter models API

`scripts/collect_openrouter.py`, feeding `elasticity`. Free, no key required.

Appends two rows per model, `openrouter_price_input` and
`openrouter_price_output`, in `usd_per_mtok`, to `data/elasticity_prices.csv`.
The API quotes USD per token; the collector multiplies by one million and
records nothing else derived.

These raw per-model prices are not the `elasticity` pillar series. The pillar
file `data/scorecard/elasticity.csv` holds only the pillar's headline, the open
versus closed price advantage at the mid-tier floor, written as three aggregate
rows a run by `scripts/price_bases.py`: `cheapest_fp8_output_open_midtier`,
`cheapest_fp8_output_closed_midtier` and the `price_advantage_midtier_fp8`
ratio. The split happened on 2026-11-03; before then the raw prices sat in the
pillar file. See the decision log for the migration, which relocated every row
without changing a value.

Three groups are excluded from the rows, each counted in the run output:

- Alias entries, which carry an `alias_target` pointing at another model in
  the same response. Keeping them would count a model twice.
- Models priced `-1`, meaning the price varies per request. These are the
  router and auto endpoints. There is no price to record.
- Nothing else. Zero-priced `:free` endpoints are kept, with a note on the
  row saying to exclude them from price averages, because dropping a real
  published price of zero is a bigger distortion than keeping it.

The collector refuses to run twice for the same date. Existing rows are never
rewritten.

### Open weights or closed weights

Produced by `scripts/classify_weights.py` into `data/model_classification.csv`,
one row per model per run date, every row carrying the basis and the evidence
that produced it.

Why a separate table rather than a column on the price rows: the
`entity_class` already written into `elasticity.csv` records what was known
when those rows were collected, and existing rows are never modified. A
better classification is a new dated table, not a rewrite. Charts and queries
join prices to the latest classification by model id.

The rule, applied in order:

| step | test | result |
| --- | --- | --- |
| 1 | OpenRouter gives the model a `hugging_face_id` | `open_weights` |
| 2 | Organisation is on the closed-weight list | `closed_weights` |
| 3 | A weights repo for the model exists in the organisation's Hugging Face namespace | `open_weights` |
| 4 | That namespace is confirmed to publish weights, but holds no repo for this model | `closed_weights` |
| 5 | Anything else | `unclassified`, with the reason recorded |

Step 4 is the only inference in the chain, and it is conditional. The
namespace has to be proven in the same run to publish real weight files
before a miss from it counts as evidence of anything. A namespace that is
unknown, misspelled or empty therefore produces `unclassified`, never a false
`closed_weights`.

Matching in step 3 compares delimited token sets, not substrings. Substring
matching failed in both directions when tried: it missed
`mistral-large-2512` against `Mistral-Large-3-675B-Instruct-2512`, where a
size string sits in the middle of the published name, and it falsely matched
`seed-1.6` against `Seed-Coder-8B-Reasoning-bf16`, where the digits 1 and 6
turn up inside `bf16`. A repo also has to contain an actual weight file,
which is what stops `upstage/solar-pro4` matching a tokenizer-only repo.

One extra outcome exists for a case that is genuinely ambiguous. Where the
published repo matches the model name minus its last part, as with
`glm-5.3-prime` against `GLM-5.3`, the model is a hosted variant of an open
base. The base weights are public but that SKU is not separately released and
the served variant may differ from them. These are recorded as
`unclassified` with basis `hosted_variant_of_open_base` and a link to the
base repo. Calling them open would overstate the open side; calling them
closed would understate it.

On the 2026-10-30 run the rule produced 185 `open_weights`, 203
`closed_weights` and 42 `unclassified`, the last being 25 models whose
organisation has no mapped Hugging Face namespace and 17 hosted variants.
That is down from 80 unclassified under the previous rule.

Inputs live in `config/weight_classes.json`: the organisation to namespace
map, the closed-weight organisation list, and the file extensions that count
as weights. Every entry is checkable by opening a URL. To classify one of the
remaining 25, add its namespace there and rerun; do not tag a row by hand.

Known limits. The classification describes the weights, not the serving: an
open-weight model served only by its author is still `open_weights`. And a
model published somewhere other than Hugging Face reads as unclassified, so
`open_weights` remains a floor rather than a count.

### Capability tiers

So that open and closed are compared like for like. Comparing the median of
every open model against the median of every closed model mixes a tier
effect into what looks like a weights effect, because the two populations sit
at different points on the capability range.

Tiers come from `benchmarks.artificial_analysis.intelligence_index`, carried
in the OpenRouter payload. Price is never an input, which matters because the
output of the exercise is a price comparison.

| tier | index |
| --- | --- |
| `frontier` | 45.0 and above |
| `mid` | 25.0 to 44.9 |
| `entry` | below 25.0 |

The bands are absolute, not percentiles of the current snapshot, so a model's
tier does not move because other models were added or removed. They were set
on 2026-10-30 at the two widest gaps in that day's distribution, nothing
scored between 40.0 and 44.9, and they are frozen in
`config/weight_classes.json`. Re-tuning bands after seeing a result is how a
comparison gets talked into saying what you wanted, so the bands do not get
revisited to accommodate a finding.

Only 54 of 430 priced models carry an index. The tier comparison is therefore
a comparison of the scored subset, not of the catalogue, and the chart says
so. Base SKUs only: `:batch` and `:free` are the same model at a discounted
or promotional price and would double count. Unclassified models are excluded
from both sides rather than folded into either.

What the 2026-10-30 run showed, and the reason this cut matters:

| tier | open | closed | median output, open | median output, closed |
| --- | --- | --- | --- | --- |
| frontier | 0 | 8 | n/a | 10.00 |
| mid | 7 | 6 | 0.87 | 4.19 |
| entry | 12 | 1 | 1.35 | 2.50 |

No open-weight model in the catalogue reaches the frontier band. The highest
scoring open model is GLM-5.3 at 31.7 against a frontier floor of 45. The
headline open discount from the uncontrolled comparison was therefore partly
a mix effect, and the honest statement is narrower: open weights are much
cheaper within the mid tier, roughly matched at entry level on input price,
and absent from the top.

### Reading the tier result against the ledger

This is consistent with B003 and is a watch item for B015. It is not evidence
against either.

B003 is the hybrid routing claim: an open model serves routine work while a
frontier model takes the hard queries. That design assumes a frontier
capability gap, so a frontier band with no open entrant is the condition the
claim operates under, not a refutation of it. Combined with open weights
costing roughly a fifth of closed in the mid tier, where routine traffic is
served, the snapshot is what B003 predicts.

B015 claims the industry is heading toward strong open source alongside
several competitive frontier labs. A multi-year direction is not refuted by
one snapshot. But the gap is the thing to watch: track the distance between
the highest open-weight intelligence index and the frontier floor in each
monthly note. A gap that persists or widens weakens B015 directly.

Neither claim changes status. Both stay pending until their horizons.

### Three price bases

There is no single right price for a model, so the pillar carries three and
reports the distance between them. All come from `scripts/price_bases.py`
into `data/price_bases.csv`.

| basis | what it is | role |
| --- | --- | --- |
| `cheapest_any` | cheapest endpoint at any precision | lower bound |
| `cheapest_fp8` | cheapest endpoint at 8-bit or better | base case, plotted |
| `author` | the model author's own standard tier | upper bound |

Why not just the author's price. Multi-provider competition on an open-weight
model is a real, purchasable advantage, and it is a large part of what the
thesis is about: anyone can serve published weights, so the price falls
towards the cost of compute. Pricing every open model at its author's list
price discards the mechanism being measured. `glm-5.3-flash` is served by 40
providers; that is the point of it being open.

Why not just the cheapest. The cheapest endpoint for an open model is often a
4-bit build, set against a closed model served at full precision. That is a
precision mismatch, not a discount. The problem was never that the cheap
endpoint came from a reseller.

So the base case keeps the competition and drops the precision mismatch.

**Precision rule.** Endpoints declaring `fp4`, `nvfp4`, `mxfp4` or `int4` are
below 8 bits and are excluded from the base case. Endpoints declaring `fp8`,
`fp16` or `bf16` qualify. Endpoints declaring nothing are treated as
qualifying, because closed providers almost never disclose: of 94 closed
endpoints on 2026-10-30, 92 declared nothing, and excluding undeclared
endpoints would empty the closed side of the comparison. The cost is that an
undeclared endpoint may be running a lower-precision build, which would
understate the base case.

Service tiers (`flex`, `priority`, `ultrafast`) are excluded from every
basis: they are speed and latency variants, not the standard product. Batch
is a separate model SKU, excluded upstream.

**Coverage differs by basis**, which matters when comparing them. The base
case drops `moonshotai/kimi-k3.1-pro`, served only at mxfp4. The author basis
drops six open-weight models whose makers do not serve them at all. Those six
all score below 25 and so do not touch any reported floor, but the exclusion
is one-sided.

Author prices were checked against provider pricing pages on 2026-10-30 and
all five checks matched the first-party endpoint exactly: `glm-5.3-flash`
0.15 / 0.50 and `glm-5.3` 1.40 / 4.40 against `docs.z.ai`, and Haiku 5.5,
Sonnet 5.5 and Opus 5.5 against `claude.com/pricing`. The OpenAI page
returned 403 to an automated fetch, so those models rest on endpoint data
alone. The per-model audit is in `data/price_verification.csv`.

### Blended price

A single output price understates what a buyer pays, because most traffic is
input. The blended price is

    blended = (R * input + output) / (R + 1)

a price per million tokens of mixed traffic at R input tokens per output
token. R lives in `config/weight_classes.json`.

There is no public token mix for this catalogue, so R is an assumption rather
than a measurement. The base is 5:1, a mid estimate for chat and agentic
traffic where prompts and retrieved context outweigh generated text. The
sensitivity ratios bracket it: 1:1 for generation-heavy work, 20:1 for
retrieval and long-context agentic work. Any figure published from this must
name both the price basis and the ratio.

### Price-performance frontier

The primary cut. For a capability floor, the cheapest model of each weight
class that clears it. Plotted against the floor it is a step function that
only rises, since raising the bar can only remove candidates.

It replaced median price by tier because a buyer does not purchase the median
model in a tier, they purchase the cheapest one that clears their bar.

Base case, blended 5:1:

| capability floor | cheapest open | cheapest closed | closed vs open |
| --- | --- | --- | --- |
| index 25 (mid floor) | glm-5.3-flash, 0.038 | claude-haiku-5.5, 0.167 | 4.34x dearer |
| index 30 | glm-5.3, 0.380 | claude-haiku-5.5, 0.167 | 2.3x cheaper |
| index 45 (frontier floor) | none | gpt-6.1-terra, 1.667 | no open model |

### How much the answer depends on the price basis

At the mid floor, blended 5:1:

| basis | models | cheapest open | open advantage | crossover |
| --- | --- | --- | --- | --- |
| cheapest, any precision | 35 | 0.026 | 6.37x | 29.9 |
| cheapest at fp8 or better | 34 | 0.038 | 4.34x | 29.9 |
| author list price | 29 | 0.113 | 1.48x | 29.9 |

The size of the open discount is highly sensitive to the basis, ranging from
1.5x to 6.4x. Any published figure has to say which basis it used.

The crossover does not move, under any basis or any token mix tested. That is
not a robustness result about pricing. It is set by open models running out of
capability at index 31.7, so above 29.9 the only open candidates are two
models that `claude-haiku-5.5` beats on every basis. The conclusion is
insensitive to price assumptions because price is not what drives it.

### Sensitivity to the token mix

On the base case, at the mid floor:

| ratio | open advantage | crossover |
| --- | --- | --- |
| output only | 3.57x | 29.9 |
| 1:1 | 3.79x | 29.9 |
| 5:1 (base) | 4.34x | 29.9 |
| 20:1 | 5.00x | 29.9 |

On the base case the open advantage grows as the workload becomes more
input-heavy, because the cheap fp8 open endpoints price input very low. On
the author basis the same test moves the other way, from 1.79x down to 1.39x.
The direction of that effect is itself a function of the basis, which is a
reason to quote a range rather than a number.

### Provider competition as a metric

Recorded under `open_source_share`, since how much competition published
weights actually attract is a direct measure of what open weights are worth.
For every open-weight model `scripts/price_bases.py` writes four metrics:
`provider_competition_count`, `provider_price_spread_ratio`,
`provider_price_min` and `provider_price_max`.

On 2026-10-30, across 165 open-weight models, the median model had 2
providers and a 1.01x spread, while the most contested had a 14.5x spread.
Competition is concentrated in a handful of popular models rather than spread
across the open catalogue, so "open weights attract competition" is true of
the models people actually use and not of open weights generally.

### Tier medians, retained but not the headline

Still computed, still recorded, no longer the chart. Each run writes
`notes/charts/<date>-tier-medians.csv` beside the chart, and the table in the
tier section above is kept. They remain the right summary for a question
about the shape of a tier, and the wrong one for a question about what a
buyer would pay.

### Cautions on the tier medians

Two limits that matter before any of this is quoted.

Sample sizes are small and some medians are unstable. Open mid holds seven
models in two clusters, three speed variants at 0.14 to 0.30 and three dear
models at 2.10 to 3.60, with a single model at 0.87 between them. The median
is that one model. Swapping it moves the median to 0.30 or 2.10. Entry-tier
closed is one model. Report counts beside any median taken from this cut, and
do not read a cross-tier ordering of open-weight medians as signal: on the
2026-10-30 data the open entry median (1.35) sits above the open mid median
(0.87), which is a small-sample artifact rather than an outlier effect.
Dropping the largest entry-tier value moves that median only to 1.20.

Price and capability are close to unrelated within the open-weight set. The
Pearson correlation between the intelligence index and log output price
across the nineteen scored open models is -0.001. Price tracks serving cost,
meaning parameter count, architecture and whether the SKU is speed-optimised.
It does not track capability. This is why tiering by price would have been
circular and useless, and it is also why the usable comparison is open
against closed within a tier, never one open tier against another.

### The capability index may lag recent releases

The Artificial Analysis intelligence index is a third-party evaluation
carried in the OpenRouter payload. It is not published at the same moment a
model is, so a recently released or recently updated model can appear with a
stale score, a score for an earlier checkpoint, or no score at all. Only 54
of 430 priced models carry one, and that coverage is itself biased toward
models that have been out long enough to be evaluated.

A tier is therefore a statement about a model's measured capability at the
time of the most recent evaluation, not necessarily its capability now. The
practical effects: recent strong releases can sit a tier below where they
belong, new models can be missing from the comparison entirely, and a tier
assignment can change on a later run with no change to the model.

The 2026-10-30 snapshot carries at least one likely instance.
`moonshotai/kimi-k3` is the fourth most expensive model in the catalogue at
15.00 per million output tokens, above `anthropic/claude-sonnet-5.5` at
10.00, while scoring 17.4 and landing in the entry tier. Its own successor
`kimi-k3.1-pro` scores 46 at a lower price. A model priced above Sonnet and
scoring in the entry band is not plausible on its face, and a stale index
entry is the likelier explanation than a genuine mispricing.

Do not correct a suspect index by hand. Flag it here, leave the data as the
source reported it, and if the problem recurs, the answer is a second
capability source rather than an adjustment.

## Limitations of the open versus closed comparison

What this comparison is, stated so that no note overclaims from it.

It compares **off-the-shelf models at published API prices on a general
capability index**. Every one of those three things is a narrowing.

**Off-the-shelf.** The models are taken as their makers ship them. B003 is
about a *post-trained* open model behind a router. Post-training is the step
that closes most of the gap on a narrow task, and nothing here measures it. A
7B model fine-tuned on one workflow can beat a general model many times its
size on that workflow, and would appear in this data, if at all, near the
bottom of the capability axis.

**API prices.** Every price is what a provider charges per token. The case
for open weights is substantially a case for self-hosting: you rent the GPU
rather than the token, the marginal cost falls towards the cost of compute,
and the economics turn on utilisation rather than list price. A model you
serve yourself does not appear in this comparison at all. This also means the
comparison cannot see the thing that makes open weights strategically
interesting, which is the option to leave.

**A general capability index.** The Artificial Analysis intelligence index is
a broad average. Routing is a bet that capability is task-specific: that a
cheaper model is adequate for most queries even if it is weaker on average. A
general index cannot test that, because it collapses exactly the variation
the bet relies on. Two models with the same index can be far apart on a
specific workload.

**The price basis is a fourth limitation, and it is not a detail.** The open
discount at the mid floor is 1.5x, 4.3x or 6.4x depending on whether you
price at the author's list, the cheapest 8-bit endpoint, or the cheapest
endpoint at any precision. Which of those a buyer can actually get depends on
their tolerance for a third-party host and for reduced precision, and this
data cannot settle that. Any statement of the form "open weights are N times
cheaper" is incomplete without the basis attached.

So what this pillar can say is narrow but real. Within the scored subset, on
off-the-shelf API pricing, open weights are meaningfully cheaper at
mid-tier capability, by somewhere between 1.5x and 6.4x depending on basis,
and no open-weight model clears the frontier floor at any price. Both halves
hold across every token mix tested.

What it cannot say is whether B003 holds, in any form. Earlier versions of
this document said the simplest form of B003 was answered no. That overstated
what the data supports in two ways. The affordability half of the claim
depends on the price basis, which moves the answer by a factor of four. And
"off the shelf at a lower token price" was never B003's claim in the first
place: B003 is about a post-trained open model behind a router, which is a
system, not a model you can look up in a catalogue. A price table cannot
answer it either way.

B003 is scorable only from `experiments/routing`, with a fixed task set, a
grading rule and cost accounting committed before the first run. Until that
exists, this pillar is evidence about token prices and capability coverage,
and the note should present it as such rather than as a verdict on the claim.

Three further limits covered above, repeated because they bear on the same
conclusion: the capability index may lag recent releases and covers only 54
of 430 priced models; the author basis excludes six open-weight models whose
makers do not serve them, a one-sided exclusion; and the blend ratio is an
assumption rather than a measurement.

## Credit pillar source map

Mapped 2026-10-30. Nothing collected yet and no collector built. This section
records where the data is, what each source can and cannot give, and what has
actually been read as opposed to assumed.

Read the issuer tables below as a starting inventory, not a verified credit
book. Figures came from the XBRL rendering pages of each filing, where column
alignment is sometimes ambiguous once the table is flattened. Every number
here needs confirming against the narrative debt footnote before it is
published or used to score anything.

### Issuers in scope

From the coverage universe, the borrowers whose debt is the pillar's subject.

| issuer | CIK | files | debt detail available |
| --- | --- | --- | --- |
| CoreWeave (CRWV) | 0001769628 | 10-Q, 10-K, 8-K | Extensive. 17 instrument-level XBRL pages. |
| Applied Digital (APLD) | 0001144879 | 10-Q, 10-K, 8-K | Good. Schedule of long-term debt plus narrative. |
| TeraWulf (WULF) | 0001083301 | 10-Q, 10-K, 8-K | Good. Debt schedule, notes and facility narratives. |
| Cipher Mining (CIFR) | 0001819989 | 10-Q, 10-K, 8-K | Good. Instrument-level schedule, SPV notes separated. |
| IREN | 0001878848 | 10-K, 8-K | Annual only on this path. No 10-Q in the recent list. |
| Nebius (NBIS) | 0001513845 | 6-K, 20-F | Thin. Foreign private issuer, no quarterly XBRL debt pages. |
| Oracle (ORCL) | 0001341439 | 10-Q, 10-K, 8-K | Thin quarterly. The 10-Q index carries no debt page; use the 10-K and 8-Ks. |
| Lambda Labs | none | none | Private. Press reports only. |
| Crusoe Energy | none | none | Private. Press reports only. |

### CoreWeave, as of 2026-06-30

The anchor case. Gross long-term debt 35,551 million USD, split 31,405
million recourse and 3,663 million non-recourse, both net of discount and
issuance costs.

| instrument | amount, USD mm | rate | notes |
| --- | --- | --- | --- |
| DDTL 1.0 | 1,300 | 15.00% effective | recourse, down from 1,553 at 2025-12-31 |
| DDTL 2.0 | 3,190 | 11.00% | recourse, down from 5,037 |
| DDTL 2.1 | 3,000 | 9.00% | recourse |
| DDTL 3.0 | 2,215 | 9.00% | recourse, up from 340 |
| DDTL 4.0 | 8,500 capacity, 2,837 drawn | SOFR + 2.25%, 7.00% effective on the drawn line | non-recourse. 0.50% commitment fee. Assets pledged 3,300 non-current plus 155 current. |
| DDTL 5.0 | 3,100 capacity, 1,101 drawn | 4.50% stated, 9.00% effective on the drawn line | recourse. 0.50% commitment fee. |
| Revolving credit facility | 0 drawn | 7.00% | recourse, was 1,000 drawn at 2025-12-31 |
| Magnetar Loan | 189 | 12.00% | recourse, down from 273 |
| OEM and software license financing | 4,220 recourse, 882 non-recourse | 11.00% and 9.00% | vendor financing |
| 2030 Senior Notes | 2,000 | 10.00% effective | |
| 2031 Senior Notes | 1,750 | 9.00% coupon, 10.00% effective | |
| 2031 Senior Notes | 2,750 | 9.75% coupon, 10.00% effective | 2,800 face, 27 unamortized discount |
| 2032 Senior Notes | 1,250 | 9.625% coupon, 10.00% effective | 1,300 face, 20 unamortized discount |
| 2032 EUR Senior Notes | EUR 2,000 face, 2,279 carrying | 8.50% coupon, 9.00% effective | cross-currency swap designated as a fair value hedge |
| 2032 Convertible Senior Notes | 4,000 | 1.75% | capped call transactions disclosed separately |
| 2031 Convertible Senior Notes | 2,588 | 2.00% effective | |
| Convertible promissory notes | 0 | 7.00% | fully repaid, was 168 |

The DDTL ladder is the single most useful series in this pillar. Successive
facility generations carry 15%, 11%, 9%, 9%, SOFR + 2.25% and 4.50%. If that
sequence is what it appears to be, the cost of GPU-backed credit at one
issuer has fallen by roughly two thirds across six facility generations. That
is a direct read on whether lenders are getting more or less comfortable with
GPUs as collateral, which is the question the pillar exists to answer.
Confirm the sequence and the drawdown dates against the narrative footnote
before treating it as a series.

> **Corrected 2026-10-30, after the XBRL check.** The paragraph above is
> wrong and is kept as written because this record does not quietly rewrite
> its own mistakes. The sequence mixes stated and effective rates. On a
> consistent effective basis the ladder is 15%, 11%, 9%, 9%, 7% and 9%, the
> 7% facility is the only non-recourse one in the set, and the newest
> facility is back at 9%. There is no two thirds decline. See "Reconciling
> the source map against the XBRL" below for the full table and for what
> does survive.

The recourse versus non-recourse split is the second thing to track. The
disclosure separates them, which most issuers do not.

### Applied Digital, period ending 2026-08-31

Fiscal year ends in May, so the quarters do not line up with the others.

| instrument | amount, USD 000s | rate |
| --- | --- | --- |
| 9.25% Senior Secured Notes due 2030 | 2,350,000 | 9.25% |
| 6.75% Senior Secured Notes due 2031 | 2,150,000 | 6.75% |
| 7.00% Senior Secured Notes due 2031 | 1,590,000 | 7.00%, new this period |
| Convertible Notes, senior unsecured | 450,000 face, 276,600 carrying | 2.75% |
| Bridge Facility | 0, was 300,000 | SOFR + 2.75% |
| Revolving Credit Facility | 82,390 | SOFR + 2.25%, 0.25% unused fee |
| Texas Capital promissory note | 58,500 | 2.75% |
| Other and secured term loans | 118,415 | not stated |

Total other long-term debt 6,721,605, less 345,013 deferred financing costs,
less 112,645 current, giving 6,263,947 net.

### TeraWulf, as of 2026-06-30

7.750% Senior Secured Notes due 2030, 3,200.0 million face as of 2025-10-22,
8.70% effective rate, 105.4 million issuance costs. Carrying amount 3,110,053
thousand, current portion 90,718 thousand. Collateral and covenants are not on
the XBRL page and need the narrative footnote.

### Cipher Mining, as of 2026-06-30

The most interesting structure of the four, because the secured notes sit at
named project entities rather than at the parent.

| instrument | principal, USD 000s | rate |
| --- | --- | --- |
| 2030 Convertible Notes | 172,500 | 1.75% |
| 2031 Convertible Notes | 1,300,000 | 0.00% |
| Cipher Compute 2030 Senior Secured Notes | 1,733,000 | 7.125% |
| Black Pearl Compute 2031 Senior Secured Notes | 2,000,000 | 6.125% |
| Stingray Compute 2031 Senior Secured Notes | 810,000 | 6.00% |

Outstanding principal 6,015,500, net borrowings 5,446,866. Principal grew from
3,205,500 at 2025-12-31, roughly doubling in six months, with Black Pearl and
Stingray both new in the period.

Two things to follow. A zero-coupon convertible carrying 398,544 of unamortized
discount on 1,300,000 principal is a large equity-linked component dressed as
debt. And project-level secured notes priced at 6.00% to 7.125%, inside
CoreWeave's parent-level senior notes at 9.00% to 9.75%, suggest lenders will
pay up for a ring-fenced contracted asset relative to corporate risk at a
bigger name. Whether that holds is a testable claim.

### Not yet read

IREN, Nebius and Oracle. All three are now reachable, as of the access fix
on 2026-10-30, and the right filing for each has been identified: the
2026-08-27 10-K for IREN with 8 debt pages, the 2026-06-22 10-K for Oracle
with 6 under "Notes Payable and Other Borrowings", and the 2026-04-30 20-F
for Nebius with 7 under "Convertible Debt". Oracle's quarterly filing does
carry no debt page, as suspected, and Nebius 6-K filings have no
FilingSummary.xml at all.

Reachable, not read. Extracting the figures is the filings extractor step
and has not been done.

### Sources for tracking over time

| source | gives | does not give | access |
| --- | --- | --- | --- |
| SEC EDGAR filings | Instrument terms, size, coupon, collateral, covenants, recourse split, drawdowns, maturity schedules. The primary source for everything structural. | Prices. Anything between filing dates. | Free. Reachable programmatically since the access fix of 2026-10-30; see below. |
| SEC EDGAR full-text search | New facilities and amendments as they are filed. Searching phrases such as "delayed draw term loan" across 8-K and 10-Q is a working monitor for new GPU-backed debt across the whole market, not only the coverage universe. | Prices. | Free, at efts.sec.gov. Confirmed working. |
| FRED | Daily index-level credit benchmarks: investment grade OAS, high yield OAS, the BB, B and CCC buckets, effective yields and the Treasury curve. The denominator for every issuer spread. | Anything issuer-specific. | Free, no API key. A fredgraph.csv request returns the full daily history as CSV. Confirmed working 2026-10-30. |
| FINRA TRACE via the FINRA API | Transaction-level corporate bond prices, the only free route to an issuer-specific bond price. | Nothing without credentials. | The fixedIncomeMarket group returns 401 unauthenticated. The otcMarket group is open, but that is equity data and not useful here. A free FINRA API account is required. Credentials go in .env. |
| Company fair-value-of-debt disclosures | A quarterly mark on each instrument, where the filer gives one. | Not universal. CoreWeave's fair value note covers marketable securities and a cross-currency swap but not the debt itself. | Free, but issuer by issuer. Check each filer before relying on it. |
| Trade press on private financings | The only visibility into Lambda, Crusoe and private GPU-backed lending. | Verifiable terms. Reports are partial and sometimes wrong. | Free. Mark every such row reported in notes. |

FRED series confirmed reachable without a key: BAMLC0A0CM investment grade
OAS, BAMLC0A4CBBB BBB OAS, BAMLH0A0HYM2 high yield OAS, BAMLH0A1HYBB BB OAS,
BAMLH0A2HYB B OAS, BAMLH0A3HYC CCC OAS, BAMLC0A0CMEY and BAMLH0A0HYM2EY
effective yields, DGS10 the 10-year Treasury.

### The EDGAR access problem, resolved 2026-10-30

The 403 is fixed. `scripts/sec_client.py` reaches every EDGAR endpoint the
pillar needs, and `python scripts/sec_client.py --check` re-tests all six
endpoint types on demand.

There were two causes, not one, which is why the earlier attempts looked
inconsistent.

**Both SEC hosts reject the default `Python-urllib/3.x` User-Agent.** A
declared User-Agent in SEC's requested format returns 200. This is SEC's
published fair access policy and the fix is to comply with it. The first of
the three options listed when this was recorded as a blocker was the right
one.

**`www.sec.gov` additionally requires an `Accept` header, and answers 403
without it rather than 406.** `data.sec.gov` does not. This is the part that
made the problem confusing: the JSON APIs worked while the filing documents
did not, with the same User-Agent, so the User-Agent looked like it had been
ruled out when it had not.

Isolated by elimination on 2026-10-30:

| headers sent | www.sec.gov FilingSummary.xml |
| --- | --- |
| default urllib User-Agent | 403 |
| User-Agent + Accept-Encoding | 403, three times, half a second apart |
| User-Agent + Accept-Encoding + Host | 403 |
| User-Agent + Accept-Encoding + Accept | 200 |
| User-Agent + Accept | 200 |

Neither cause was rate limiting. Worth recording, because the instinctive
reading of a 403 is that you are being throttled, and the instinctive fix of
waiting longer would never have worked.

The client paces at five requests a second against SEC's published limit of
ten, retries on 429 and 5xx, and does not retry a 403, since a 403 now means
the headers are wrong rather than that the server is busy.

The User-Agent defaults to the project name and its public domain, which is a
real contact route and keeps a personal address out of a repo intended to go
public. `SEC_USER_AGENT` in `.env` overrides it with a real email address,
which is what SEC would prefer. `.env` is gitignored.

**Verified against every issuer in the pillar**, 2026-10-30. Each row below
means the filing index, the FilingSummary and the debt rendering pages were
all fetched successfully. Reachable is not the same as read: extracting the
figures is the next step and has not been done.

| issuer | filing reached | debt pages |
| --- | --- | --- |
| CoreWeave | 10-Q, 2026-08-12 | 17 |
| Applied Digital | 10-Q, 2026-10-07 | 6 |
| TeraWulf | 10-Q, 2026-08-05 | 8 |
| Cipher Mining | 10-Q, 2026-08-04 | 6 |
| IREN | 10-K, 2026-08-27 | 8 |
| Oracle | 10-K, 2026-06-22 | 6 |
| Nebius | 20-F, 2026-04-30 | 7 |

Two notes on the last three, which were unread when the source map was
written. Oracle's 10-Q does carry no debt page, as suspected; the 10-K
carries six, under "Notes Payable and Other Borrowings". Nebius 6-K filings
have no FilingSummary.xml at all, which returns 404; that is a property of
how foreign private issuers file rather than an access failure, and the 20-F
carries seven pages under "Convertible Debt".

The narrative debt footnote pages are now reachable, not only the flattened
detail tables. That matters because every figure in the issuer tables above
was read off a flattened XBRL page and flagged as needing confirmation
against the narrative. The means to do that confirmation now exists.

FINRA registration remains the one outstanding blocker in this pillar.

### Proposed first credit metrics

Not collected. Proposed for approval, using the standard scorecard columns
with entity as the issuer or instrument and entity_class as the borrower type.

Benchmarks, from FRED, daily, automatable today:

| metric | unit | why |
| --- | --- | --- |
| `ig_oas` | bps | The denominator. A spread move means nothing without it. |
| `hy_oas` | bps | |
| `hy_bb_oas`, `hy_b_oas`, `hy_ccc_oas` | bps | Neocloud paper sits in this range, and which bucket it sits in is the point. |
| `ust_10y` | pct | |

Issuer structure, from filings, quarterly, manual until EDGAR access is fixed:

| metric | unit | why |
| --- | --- | --- |
| `total_debt` | usd_mm | |
| `recourse_debt_share` | pct | How much risk sits outside the parent is the first thing a lender asks. |
| `gpu_backed_facility_capacity` | usd_mm | Committed capacity against GPUs. |
| `gpu_backed_facility_drawn` | usd_mm | Drawn against that capacity. The gap is the dry powder. |
| `newest_facility_rate` | pct | The marginal cost of GPU-backed credit at this issuer. |
| `facility_rate_by_vintage` | pct | Per facility, dated. The CoreWeave DDTL ladder is the model: it shows the direction of lender appetite over time. |
| `commitment_fee` | pct | What lenders charge for the option. |
| `collateral_pledged` | usd_mm | |
| `weighted_average_coupon` | pct | |
| `gpu_depreciation_life_years` | years | Not a debt term, but the assumption that decides whether the collateral outlives the loan. The owner's underwriting angle. |

Secondary pricing, from TRACE once registered:

| metric | unit | why |
| --- | --- | --- |
| `bond_price` | pct_of_par | Per CUSIP. |
| `bond_yield_to_worst` | pct | |
| `bond_spread_to_ust` | bps | |
| `spread_over_hy_index` | bps | The issuer spread minus the matching FRED bucket. This is what the pillar is really about: whether the market charges AI infrastructure borrowers more or less than comparable credits, and which way that is moving. |

Suggested build order, for approval: the FRED benchmark collector first,
because it is free, keyless, daily, has decades of history and no blockers;
then the EDGAR access problem; then the filings extractor; then TRACE. Nothing
is built yet and nothing should be until the owner approves this shape.

Approved 2026-10-30, and the first two steps are done. The FRED collector is
built and has run; see below. The claim that it has decades of history turned
out to be wrong for eight of the nine series, which is documented in the next
section. EDGAR access is fixed; see above. The filings extractor and TRACE
are unchanged and unstarted, and TRACE still waits on FINRA registration.

### The FRED benchmark collector

Built and first run 2026-10-30. `scripts/collect_fred.py`, configured by
`config/credit_series.json`. Nine series, no API key, no account.

| metric | FRED series | unit stored | published as |
| --- | --- | --- | --- |
| `ig_oas` | BAMLC0A0CM | bps | percent |
| `bbb_oas` | BAMLC0A4CBBB | bps | percent |
| `hy_oas` | BAMLH0A0HYM2 | bps | percent |
| `hy_bb_oas` | BAMLH0A1HYBB | bps | percent |
| `hy_b_oas` | BAMLH0A2HYB | bps | percent |
| `hy_ccc_oas` | BAMLH0A3HYC | bps | percent |
| `ig_effective_yield` | BAMLC0A0CMEY | pct | percent |
| `hy_effective_yield` | BAMLH0A0HYM2EY | pct | percent |
| `ust_10y` | DGS10 | pct | percent |

The option-adjusted spread series are published in percent and stored in
basis points, multiplied by 100, because a spread is read in basis points.
The scale factor sits in the config next to each series rather than in the
code. Yields are stored as published.

Rows are written with `entity` set to the FRED series id and `entity_class`
set to `index`. The series id rather than a friendly name because it is the
thing that can be checked: open `https://fred.stlouisfed.org/series/<id>`.

**The date column holds the observation date, not the collection date.**
This differs from every other collector in the repo and is deliberate. A
market level has a date of its own and that date is the meaning; stamping
three years of history with the day it was pulled would make the series
useless. The collection date is on every row in `notes`. See
docs/decisions.md.

**Only three years of spread history exist.** The eight ICE BofA series
return a rolling three-year window and ignore the `cosd` and `coed` date
parameters, tested on 2026-10-30. The earliest obtainable observation is
2023-10-31. DGS10 has no cap and returned 1962 onward, so the Treasury series
is deeper than the spread series and any chart combining them has to say so.
The window rolls, so observations drop off the back permanently. For anything
older than three years this repo will eventually hold the only copy, which is
why the collector never rewrites a row.

**Revisions are reported, not applied.** Each run re-reads the overlap
between what FRED now serves and what is stored, and prints any value that
has changed. Nothing is overwritten. A revision is a new fact and gets a new
dated commit.

**Append only.** The collector finds the newest stored observation per series
and appends only what follows it. A second run on the same day writes
nothing. Confirmed on the first run: 7,742 rows written, then zero.

Raw responses go to `data/raw/fred/<collection date>/<series id>.csv`, full
history as returned rather than the trimmed window.

### What the first credit run shows

Baseline only. Nothing issuer-specific, and nothing here scores a claim.

| metric | latest, 2026-10-29 | 3y low | 3y high | 3y median | percentile |
| --- | --- | --- | --- | --- | --- |
| `ig_oas` | 89 bps | 73 | 133 | 84 | 62% |
| `bbb_oas` | 110 bps | 92 | 163 | 106 | 60% |
| `hy_oas` | 326 bps | 259 | 461 | 302 | 78% |
| `hy_bb_oas` | 194 bps | 150 | 306 | 182 | 73% |
| `hy_b_oas` | 332 bps | 254 | 486 | 304 | 78% |
| `hy_ccc_oas` | 1,325 bps | 690 | 1,356 | 908 | 99% |
| `ig_effective_yield` | 5.79% | 4.67 | 6.37 | 5.20 | 94% |
| `hy_effective_yield` | 7.99% | 6.39 | 9.38 | 7.07 | 91% |
| `ust_10y` | 5.05% | 0.93 | 5.31 | 4.05 | 99% |

Two patterns, stated as observations and not as explanations.

Credit quality is bifurcated rather than broadly stressed. CCC sits at the
99th percentile of its three-year range, close to its high of 1,356. BB sits
at the 73rd and investment grade at the 62nd. The CCC-minus-BB gap is 1,131
bps against a three-year median of 719. The market is discriminating sharply
inside high yield rather than repricing credit as a whole.

All-in yields are high for a reason that is mostly not credit. Investment
grade yields at the 94th percentile while investment grade spreads sit at the
62nd, with the 10-year Treasury at the 99th. Borrowing costs are elevated
because the risk-free rate is elevated. Reading a high coupon on a 2026
issue as evidence of credit stress would be a mistake, and the comparison the
pillar needs is spread over the matching index, not the coupon.

Three cautions on all of the above. The percentiles cover three mid-cycle
years with no quiet period and no prior stress episode, so a 99th percentile
here is a weaker statement than it would be over twenty years. The CCC index
is the whole CCC universe and has no known AI infrastructure weighting, so
nothing in it can be attributed to this sector without issuer-level data.
And none of these series is issuer-specific, which is the gap TRACE fills and
the reason the pillar is not finished.

### The filings extractor

Built and first run 2026-10-30. `scripts/extract_filings.py`, configured by
`config/credit_issuers.json`. Seven issuers, 1,118 metric rows.

**It reads the XBRL instance document, not the R##.htm rendering pages.**
That distinction is the point of the script. The rendering pages are HTML
tables generated from the XBRL for people to read, and flattening one to
text loses the column alignment, which is how the first pass at the source
map produced figures that had to be flagged. The instance document carries
the same facts with an explicit context on each one naming its period and
its dimensional members, so a 9.00% belonging to DDTL 2.1 cannot be read as
belonging to DDTL 3.0.

The XBRL `companyfacts` and `frames` APIs were tested first and are not
sufficient. They return consolidated facts only: `LongTermDebt` for the
whole company is there, the rate on an individual facility is not.
Instrument-level detail is the pillar's subject, so the instance document is
the only usable source.

| issuer | filing read | metric rows | instruments |
| --- | --- | --- | --- |
| CRWV | 10-Q 2026-08-12 | 132 | 20 |
| APLD | 10-Q 2026-10-07 | 108 | 21 |
| WULF | 10-Q 2026-08-05 | 81 | 18 |
| CIFR | 10-Q 2026-08-04 | 122 | 7 |
| IREN | 10-K 2026-08-27 | 99 | 26 |
| NBIS | 20-F 2026-04-30 | 66 | 18 |
| ORCL | 10-K 2026-06-22 | 510 | 75 |

Form preference beats recency. `forms` in the config is ordered best first
and the extractor takes the newest filing of the best form that exists.
Oracle is why: its 10-Q is more recent than its 10-K and carries no debt
disclosure, so taking the newest filing returned four facts instead of 510.

**Two rate metrics, never mixed.** Filers tag
`DebtInstrumentInterestRateStatedPercentage` for the coupon or stated rate
and `DebtInstrumentInterestRateEffectivePercentage` for the rate including
discount and issuance cost amortisation. These are stored as
`instrument_rate_stated` and `instrument_rate_effective` and neither is
derived from the other. Any comparison across instruments has to pick one
basis and stay on it. The cost of getting this wrong is set out under the
reconciliation below.

**Member names are preserved verbatim**, as `TICKER:MemberName` in the
entity column, with the full member chain in notes. No attempt is made to
turn `DDTL2.1FacilityMember` into a friendly name, because the translation
would be a guess a later reader could not check.

**One classification is applied.** A facility counts as GPU-backed when its
member name contains one of the substrings in `config/credit_issuers.json`,
currently `ddtl`, `delayeddraw` and `gpu`. It is recorded in notes, not used
to filter anything out. A facility is counted because its name says so, not
because anyone decided it was.

**Dates are carried as ISO strings in the value column**, with unit `date`,
for `instrument_maturity_date` and `instrument_issuance_date`. A value
column holding both numbers and dates is not elegant. The alternative was a
separate file with its own schema, which would break the rule that all five
pillar files share one header, and maturity is too central a credit term to
leave out. Readers filter on the unit column.

**Durations are ISO 8601.** A five year useful life arrives as `P5Y` and has
to be parsed, not cast. This was missed on the first run and silently sent
52 facts to the gap file, including every GPU depreciation life. Months and
days convert on 12 and 365, which is close enough for a depreciation life
and wrong enough to record here.

**Unmapped facts are written down, not dropped.** 419 debt-adjacent facts
whose tags are not in the extractor's map went to `data/credit_unmapped.csv`
with the tag, the members, the value and the reason. The gap list is the
honest part of the output, and it is what the next pass works from.

Two exclusions keep that file usable. Tags ending in `TextBlock` hold an
entire rendered footnote including its HTML, one of them 130 KB on its own,
and are skipped: they are disclosure prose rather than facts, and listing
them made the gap file 2.3 MB of markup that broke the CSV reader in
`build_db.py`. Any other value is truncated to 200 characters. The gap file
exists to say what was missed, not to hold a second copy of the filing.

Append only, and it refuses to run twice for the same collection date. The
`date` column holds the period end of the fact, following the convention set
by the FRED collector; the filing date, accession number and collection date
are in notes.

### Reconciling the source map against the XBRL

The source map was gathered by hand from flattened rendering pages and every
figure in it was flagged as needing confirmation. This is that confirmation.
Two findings were checked. One holds and one does not.

**The CoreWeave DDTL rate ladder does not hold as it was written.** The
source map reported successive facility generations at 15%, 11%, 9%, 9%,
SOFR plus 2.25% and 4.50%, and read that as the cost of GPU-backed credit
falling by roughly two thirds across six deals. That sequence mixes two
different rate bases. On the effective basis, consistently:

| facility | stated | effective | carrying, usd mm | recourse |
| --- | --- | --- | --- | --- |
| DDTL 1.0 | not tagged | 15.00% | 1,300 | recourse |
| DDTL 2.0 | not tagged | 11.00% | 3,190 | recourse |
| DDTL 2.1 | not tagged | 9.00% | 3,000 | recourse |
| DDTL 3.0 | not tagged | 9.00% | 2,215 | recourse |
| DDTL 4.0 | 2.25% over SOFR | 7.00% | 2,837 | non-recourse |
| DDTL 5.0 | 4.50% | 9.00% | 1,101 | recourse |

The 4.50% that ended the sequence is DDTL 5.0's stated rate. Its effective
rate is 9.00%. The 7.00% on DDTL 4.0 is lower than the rest, and DDTL 4.0 is
the one non-recourse facility in the ladder, so it is not comparable to the
others either.

What survives is narrower and still interesting. Among recourse facilities
the effective rate fell from 15% to 11% to 9% across the first three
generations and has been flat at 9% for the three generations since,
including DDTL 5.0, the newest. So GPU-backed credit at this issuer got
materially cheaper once and then stopped. That is a different claim from a
two thirds decline, and it is the one the filing supports.

The open question of whether the ladder is a like-for-like sequence is
therefore answered, and the answer is no. Two of the six differ in rate
basis or in recourse.

**The recourse split holds exactly.** Recourse 25,170 non-current plus 6,235
current is 31,405 million; non-recourse 2,385 plus 1,278 is 3,663 million.
Both match the source map to the million.

**The Cipher comparison holds, on a like-for-like basis.** Cipher's
project-level secured notes are tagged at stated rates of 6.00%, 6.125% and
7.125%. CoreWeave's parent-level senior notes are tagged at stated rates of
9.00%, 9.625% and 9.75%. Both are stated rates, so the comparison in the
source map was made on one basis and stands: ring-fenced project debt at the
smaller issuer prices inside corporate debt at the larger one. Worth noting
that CoreWeave's effective rate on those notes is 10.00% while Cipher tags
no effective rate on the project notes, so the gap cannot be restated on the
effective basis from this data.

A third observation falls out of the same table. Cipher's 2031 convertible
has a stated rate of 0.00% and an effective rate of 6.89%, which is a clean
illustration of why the two bases are kept apart.

**GPU depreciation lives are now readable**, which is the underwriting
assumption that decides whether the collateral outlives the loan. IREN tags
`GPUHardwareMember` and `HPCHardwareMember` at 5.0 years and mining hardware
at 4.0. Nebius tags computer equipment at 4 to 5 years. Applied Digital
tags a 3 to 5 year range without naming GPUs, alongside 39 year buildings.
CoreWeave tags no useful life at all in its 10-Q, so its depreciation
assumption is not available from this source and has to come from the 10-K
or the narrative.

## Sources

| source | pillars | access | reliability notes |
| --- | --- | --- | --- |
| OpenRouter public rankings | `open_source_share`, `elasticity` | free, scrapeable | Covers routed traffic only, not direct API traffic. Treat as a directional sample, not the market. |
| Model provider pricing pages | `elasticity` | free, scrapeable | Prices change without notice. Snapshot and archive on every collection. |
| SEC filings via EDGAR full-text search | `buyer_concentration`, `credit` | free, API | Authoritative. Lags the quarter. Needs the headers documented in the credit source map; see `scripts/sec_client.py`. |
| Company IR decks and earnings call transcripts | all | mostly free | Management framing. Record the claim, not the spin. |
| FRED | `credit` | free, no key | Index-level credit benchmarks, collected since 2026-10-30. The ICE BofA series serve a rolling three-year window only. |
| FINRA TRACE | `credit` | free, delayed | Bond prints for public issuers. Needs a free account; not yet registered. |
| GPU rental price aggregators and provider rate cards | `compute_pricing` | free | Advertised rates, not transacted rates. Note which is which. |
| Trade press on private financings | `credit`, `compute_pricing` | free | Unverifiable terms. Mark the row as `reported` in notes. |

Anything paid or manually collected gets flagged in the `notes` column of the
row it produced, and listed here.

Currently paid or manual: none.

## Coverage universe

`data/coverage_universe.csv` lists the companies tracked across the stack.

Columns: `ticker`, `company`, `layer`, `sub_segment`, `pillars`, `listed`,
`in_atreides_top10_q3`, `added_date`, `notes`.

`layer` is one of `silicon`, `networking`, `neocloud`, `hyperscaler`,
`power_and_facilities`, `model_layer`, `application`.

`pillars` is a semicolon-separated list using the five pillar names.

`listed` is `public`, `private`, or `verify` where listing status still needs
checking. A `verify` ticker means the same.

`in_atreides_top10_q3` marks the names reported as Atreides top 10 positions
as of Q3 2026. It takes two values, `yes` and `no`.

The owner confirmed on 2026-10-30 that the top 10 list is complete, so every
company not flagged `yes` is flagged `no`. An earlier version of this file
used a third value, `unknown`, for the eleven companies that were absent from
the original coverage file. That distinction is gone because the completeness
of the list settles it.

One caveat sits on top of this. The list holds ten positions and only nine are
identified here. The tenth is recorded in the source as "United" and has not
been matched to a company. It is not any of the eleven rows reclassified from
`unknown` to `no`, none of which is named United, which is what makes that
reclassification safe. Until "United" is identified, two things follow. The
`yes` rows are nine, not ten, so any count taken off this column understates
the top 10 by one. And if "United" turns out to be a company already in the
coverage universe, its row is currently flagged `no` and will need correcting
with a new commit.

## Claims ledger

`data/claims_ledger.csv` holds dated, testable claims, whether they come from
Gavin Baker, from other commentators, or from the owner.

Columns:

| column | meaning |
| --- | --- |
| `claim_id` | Stable id. Baker claims from the original ledger keep their `Bnnn` ids. |
| `date_said` | When the claim was made publicly. |
| `date_entered` | When the claim was entered into this ledger. These differ, and both matter. |
| `speaker` | Who made the claim. |
| `source_type` | For example `call`, `letter`, `podcast`, `post`, `owner`. |
| `source_name` | The specific source, for example `Atreides Q3 2026 update call`. |
| `source_url` | Direct link where one exists. Empty where the source is not public. |
| `claim_text` | The claim as stated, paraphrased only for length, never for meaning. |
| `pillar` | One of the five pillar names. |
| `claim_type` | `data_point`, `prediction`, or `framework`. See below. |
| `verification_source` | Where the evidence would come from. Carried over from the original `how_to_verify` field. |
| `resolution_criterion` | The falsifiable test, written before the outcome is known. |
| `horizon_label` | The horizon as originally stated, for example `ongoing`, `multi-year`, `30 days`. |
| `horizon_date` | The date the claim gets scored, ISO format. |
| `status` | See the status table below. |
| `status_updated` | When status last changed. |
| `evidence_url` | Required before any status other than `pending`. |
| `notes` | Anything a reader needs in order to score the claim the same way. |

A claim only belongs in the ledger if it is falsifiable. "Inference demand is
strong" is not a claim. "Open-weight models exceed 30 percent of served tokens
by the end of 2027" is.

`claim_id` format for new claims: `YYYY-MM-NN`, by the month the claim was
made. The original Baker claims keep their `Bnnn` ids so that references to
them in earlier work still resolve.

### Claim types

Carried over from the original methodology.

| type | meaning | how it gets scored |
| --- | --- | --- |
| `data_point` | A factual figure that can be checked against a source. | Confirmed or contradicted by the cited source. |
| `prediction` | A forward call with a horizon. | Scored at the horizon date against the criterion. |
| `framework` | A causal claim tested over time against the scorecard. | Scored at a review date against the direction and magnitude the framework implies. |

A `framework` claim is the easiest to fudge, because there is always another
year in which it might still come good. Two guards. Each framework claim gets
a real `horizon_date` like any other, and each gets a criterion that says what
observation would count against it, not only what would support it.

### Status values

| status | meaning |
| --- | --- |
| `pending` | The horizon date has not arrived. No score yet. |
| `correct` | The claim resolved as stated. |
| `partly correct` | Direction right, magnitude or timing wrong. |
| `wrong` | The claim resolved against. |
| `unverifiable` | The horizon arrived and no credible data exists to score it. |

### Scoring rules

1. Score at the horizon date, not before. A claim that looks wrong in month
   three of a two-year horizon stays `pending`.
2. Write down the resolution criterion in `resolution_criterion` at the time
   the claim is entered, before the outcome is known. If the criterion was not
   written in advance, the claim is `unverifiable`.
3. Resolution needs a link in `evidence_url`.
4. `unverifiable` is a real answer and should get used. Reaching for a verdict
   with weak data is worse than recording that the data was not there.
5. Changing a status is a new commit with the reason in the message, and a new
   `status_updated` date. The old status stays visible in git history.

### Horizon dates for the original 16 claims

The original ledger recorded horizons as labels rather than dates, and
recorded `date_said` as `2026-10` with no day. The call date is 2026-10-29,
confirmed by the owner on 2026-10-30, and all 16 claims carry it.

The labels are kept in `horizon_label`. `horizon_date` was derived from them
on 2026-10-30 using these rules, applied uniformly and written down here so
the dates cannot be quietly moved later:

- `Q3 2026` and `point in time`: 2026-12-31, by which date Q3 reporting and
  the referenced filings are public.
- `Oct 2026`: 2026-10-31, the end of the month the claim describes.
- `30 days`: 30 days after the call date.
- `12 months`: 12 months after the call date.
- `ongoing`: 2027-10-31, a one-year review. These are framework claims with no
  natural end, so they get an explicit annual review date instead of running
  forever unscored.
- `multi-year`: 2028-10-31, a two-year review, matching the intended length of
  the track record.

The transform itself is in `scripts/migrate_claims.py`, including every
resolution criterion, so the mapping can be re-read rather than taken on
trust.

## Integrity rules

- Never delete or overwrite a historical row. Corrections are new rows.
- Never backfill as if data had been collected earlier. The collection date is
  the real one.
- Public information only. Nothing touching the owner's current and future
  employers enters this repo.
- No API keys or secrets in version control. They live in `.env`.

## What this record cannot tell you

Worth stating up front so the notes stay honest:

- OpenRouter sees routed traffic. The largest direct API customers are invisible.
- Advertised GPU rental rates are not transacted rates, and large contracts are
  negotiated well below the rate card.
- Private neocloud debt terms reach the public through press reports that are
  often incomplete and sometimes wrong.
- Customer concentration disclosure is only as granular as a filer chooses.
