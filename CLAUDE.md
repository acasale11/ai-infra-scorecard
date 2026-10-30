# CLAUDE.md

## What this project is

A public, timestamped research record testing one investment thesis: AI
infrastructure wins when the model layer is competitive and low margin, and
loses if a few frontier labs dominate compute buying. The framework comes from
Gavin Baker's (Atreides Management) public commentary, starting with the Q3
2026 update call.

The owner is a finance and data science student with a private credit and
underwriting background. The long-term goal is a two-year track record of data,
monthly notes, and pitches that shows underwriting judgment applied to AI
infrastructure. The work must show his own judgment, so do not write published
notes for him. Help with data, code, analysis, and outlines.

## The five pillars

1. `elasticity` token prices compared with token volume
2. `open_source_share` open-model share of tokens served (OpenRouter and similar)
3. `compute_pricing` GPU rental prices and resale or renewal values by chip generation
4. `buyer_concentration` share of neocloud and hyperscaler revenue or backlog tied to OpenAI and Anthropic
5. `credit` neocloud bond spreads, GPU-backed loan terms, data center financing (the owner's differentiated angle)

Use these exact pillar names in data files and tags.

## Repo structure

- `data/claims_ledger.csv` dated, testable claims from Baker and the owner, with status
- `data/coverage_universe.csv` about 29 companies across the AI infrastructure stack
- `data/scorecard/` one CSV per pillar, appended monthly (columns: date, metric, value, unit, source, source_url, notes)
- `docs/methodology.md` sources, definitions, scoring rules
- `notes/` monthly scorecard notes, mirrored on Substack
- `experiments/routing/` test of an open model plus frontier router vs a frontier model alone

## Public outputs

The project is semi-anonymous. No full name, employer, or school appears on
anything public. That covers the Substack, X, charts, the repo README, and
the repo itself if it is ever made public.

Public identity, and the only place these values are edited:
`config/identity.json`.

| field | value |
| --- | --- |
| display name | Tony C. |
| X handle | @TonyC_research |
| Substack | https://tonycresearch.substack.com |

Anything that renders a byline or footer reads that file through
`scripts/project_config.py`. Never hardcode the handle in a script, a chart,
or a note.

Off limits on public outputs: the owner's legal name, the university he
attends, and any current or former employer. They are deliberately not listed
here, because this file is itself a public output. The separate rule that no
employer material enters the repo at all stands on top of this and is
stricter.

Semi-anonymous means pseudonymous, not untraceable. The aim is that a casual
reader or a search for the owner's real name does not land here. It is not a
defence against anyone determined, and nothing in this repo should be written
on the assumption that the pseudonym holds.

## Integrity rules (never break these)

- Never delete or overwrite historical data or claims. Corrections are new rows or new commits with an explanation.
- Never backfill data as if it were collected earlier. Record the actual collection date.
- Claim status values: pending, correct, partly correct, wrong, unverifiable. Score predictions at their horizon, not before.
- Public information only. Nothing related to the owner's employers (Raptor Group, Audax) goes in this repo.
- Never commit API keys or secrets. Keep them in `.env`, which is gitignored.

## Agent infrastructure (planned, build in this order)

1. Data layer: SQLite database plus scheduled collection scripts for the scorecard metrics. Prefer reliable free sources; flag paid or manual ones in `methodology.md`.
2. Claims ledger agent: ingests Baker's letters, podcasts, and posts and extracts dated, testable claims into the ledger.
3. Earnings and filings agent: after each earnings season, tags data points from the coverage universe against the five pillars with source links; for neoclouds, pulls debt terms, customer concentration, and depreciation assumptions.
4. Monthly brief generator: combines scorecard and tagged data into a dashboard and an outline of what changed. The owner writes the note.

## Conventions

- Python, with small readable scripts over frameworks.
- Explain what you changed in plain language after each task; the owner is still building technical depth.
- Commit with clear messages and push when a task is done, then confirm the branch is up to date with origin.
- Keep prose em-dash-free and concise in any docs you write.
