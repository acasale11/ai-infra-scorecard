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

### What the rule covers

The rule applies to the content of public outputs: charts, the dashboard,
notes, posts, and the prose in this repo. None of them carry the owner's
legal name, his university, or the owner's current and future employers.
Those are deliberately not listed anywhere in the repo, including in this
rule, because these files are public outputs themselves.

### What the rule does not cover

Git metadata. The repo lives on the owner's personal GitHub account and
commits carry his real name and email. That is a deliberate, accepted
choice: the account and the commit history are traceable to him and are
meant to be. Do not flag it, and do not propose rewriting history or
switching to a pseudonymous committer.

So the pseudonym is a presentation layer, not concealment. It keeps the
owner's legal name off the face of the work, which is what the byline and
the search result show. Anyone who opens the repo can see who wrote it, and
that is fine. Nothing here should be written on the assumption that the
pseudonym hides anything from someone who looks.

## Integrity rules (never break these)

- Never delete or overwrite historical data or claims. Corrections are new rows or new commits with an explanation.
- Never backfill data as if it were collected earlier. Record the actual collection date.
- Claim status values: pending, correct, partly correct, wrong, unverifiable. Score predictions at their horizon, not before.
- Public information only. Nothing related to the owner's current and future employers goes in this repo.
- Never commit API keys or secrets. Keep them in `.env`, which is gitignored.

## Agent infrastructure (planned, build in this order)

1. Data layer: SQLite database plus scheduled collection scripts for the scorecard metrics. Prefer reliable free sources; flag paid or manual ones in `methodology.md`.
2. Claims ledger agent: ingests Baker's letters, podcasts, and posts and extracts dated, testable claims into the ledger.
3. Earnings and filings agent: after each earnings season, tags data points from the coverage universe against the five pillars with source links; for neoclouds, pulls debt terms, customer concentration, and depreciation assumptions.
4. Monthly brief generator: combines scorecard and tagged data into a dashboard and an outline of what changed. The owner writes the note.

## How a session ends

Do not propose new builds at the end of a session. No "next I could build
X", no list of candidate next steps, no card or offer to start the
follow-on work.

End with the plain-English summary of what was done, what it means, and
anything that is uncertain or unverified, and then stop. The owner decides
what happens next.

This is not a style preference. The project's value is the owner's
judgement about what is worth measuring, and a session that ends by
proposing the next build quietly moves that judgement to whoever is
proposing. Recording an option in `docs/decisions.md` under open questions
is the right place for it; the end of a session is not.

Blockers and unfinished work are different and must still be stated
plainly, because those are facts about the work rather than suggestions
about what to do next.

## Conventions

- Python, with small readable scripts over frameworks.
- Explain what you changed in plain language after each task; the owner is still building technical depth.
- Commit with clear messages and push when a task is done, then confirm the branch is up to date with origin.
- Keep prose em-dash-free and concise in any docs you write.
