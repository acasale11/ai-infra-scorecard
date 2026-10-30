# AI Infrastructure Research Record

A public, timestamped record testing one thesis: AI infrastructure is a good
place to own capital when the model layer stays competitive and low margin, and
a bad one if a few frontier labs come to dominate compute buying.

The point is the audit trail. Every number carries a date, a unit, and a source
link. Every prediction carries a horizon and gets scored when that horizon
arrives, including the ones that turn out wrong.

## Layout

```
data/claims_ledger.csv      dated, testable claims with status
data/coverage_universe.csv  companies tracked across the stack
data/scorecard/             one CSV per pillar, appended monthly
docs/methodology.md         sources, definitions, scoring rules
docs/decisions.md           dated log of judgment calls and what they cost
notes/                      monthly notes
experiments/routing/        open model plus router vs frontier model alone
```

## The five pillars

`elasticity`, `open_source_share`, `compute_pricing`, `buyer_concentration`,
`credit`. Defined in [docs/methodology.md](docs/methodology.md).

## Rules of the record

Historical rows are never edited or deleted. Corrections are new rows with an
explanation in the commit message. Data is never backfilled as though it had
been collected earlier. Public sources only.

## Status

Scaffolded 2026-10-30, then merged with the original ai-infra-scorecard
history. The ledger holds the 16 claims from the Atreides Q3 2026 update call
of 2026-10-29, all `pending`, each with a resolution criterion written before
the outcome was known. Scorecard files are empty and waiting on the first
collection run.
