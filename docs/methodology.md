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

One CSV per pillar in `data/scorecard/`, appended monthly. Columns:

- `date` the date the observation refers to, ISO format `YYYY-MM-DD`
- `metric` a stable short name, snake_case, reused month to month
- `value` numeric only, no units, no thousands separators
- `unit` for example `usd_per_mtok`, `usd_per_gpu_hour`, `pct`, `bps`, `usd_mm`
- `source` the publisher, for example `OpenRouter`, `SEC 10-Q`, `Company IR deck`
- `source_url` a direct link, archived if the page is likely to change
- `notes` anything a reader needs in order to reproduce the number

Two rules that matter more than the rest:

1. A metric name, once used, keeps its definition forever. If the definition
   has to change, create a new metric name and leave the old series alone.
2. Record the date you collected the number. If a source publishes a revised
   figure later, add a new row. Do not edit the old one.

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

## Sources

| source | pillars | access | reliability notes |
| --- | --- | --- | --- |
| OpenRouter public rankings | `open_source_share`, `elasticity` | free, scrapeable | Covers routed traffic only, not direct API traffic. Treat as a directional sample, not the market. |
| Model provider pricing pages | `elasticity` | free, scrapeable | Prices change without notice. Snapshot and archive on every collection. |
| SEC filings via EDGAR full-text search | `buyer_concentration`, `credit` | free, API | Authoritative. Lags the quarter. |
| Company IR decks and earnings call transcripts | all | mostly free | Management framing. Record the claim, not the spin. |
| FINRA TRACE | `credit` | free, delayed | Bond prints for public issuers. |
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

`in_atreides_top10_q3` carries over from the original coverage file and marks
the names reported as Atreides top 10 positions as of Q3 2026. It takes three
values. `yes` and `no` are both as recorded in that file. `unknown` means the
company was not in that file at all, so its absence from the top 10 is likely
but was never actually checked. Do not read `unknown` as `no`.

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
- Public information only. Nothing touching Raptor Group or Audax enters this
  repo.
- No API keys or secrets in version control. They live in `.env`.

## What this record cannot tell you

Worth stating up front so the notes stay honest:

- OpenRouter sees routed traffic. The largest direct API customers are invisible.
- Advertised GPU rental rates are not transacted rates, and large contracts are
  negotiated well below the rate card.
- Private neocloud debt terms reach the public through press reports that are
  often incomplete and sometimes wrong.
- Customer concentration disclosure is only as granular as a filer chooses.
