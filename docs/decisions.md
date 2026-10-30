# Decision log

Choices that shaped this record and that a reader could not reconstruct from
the data or the commit diffs alone. Methodology says what the rules are. This
says why they are those rules and what was given up.

Entries are append-only, newest date first. A decision that gets reversed
stays here and the reversal is a new entry, because a record that only shows
the surviving decisions hides the ones that were wrong.

Each entry gives the decision, the reasoning, and what it costs.

## 2026-10-30

### Scorecard files ship empty

No metric rows were seeded at scaffold time. Writing plausible token prices
and GPU rates would have meant dating numbers as collected on a day they were
not collected, which is the exact failure the integrity rules exist to stop.

Cost: the repo opens with nothing to look at, and the first real collection
run has to happen before any of this is useful.

### The two histories were merged, not rebased

The original upload commit 461520b is a parent of the merge commit e8bc0ff,
so it stays reachable with its own author and timestamp. A rebase would have
produced tidier linear history by rewriting that commit, and a force push
would have removed it.

For a record whose value is that nothing quietly disappears, keeping the
original commit beat having a clean graph.

Cost: the history has a merge commit and two roots, which looks odd to anyone
expecting a linear log.

### The ledger schema was widened rather than mapped onto

The scaffold schema had 13 columns. The original file held `speaker`, `type`
and a free-text `horizon` that the scaffold had nowhere to put. Rather than
drop them, the schema went to 18 columns: `speaker`, `claim_type`,
`horizon_label` and `verification_source` were added, and `testable_metric`
was replaced by `resolution_criterion`.

`verification_source` keeps the original `how_to_verify` text verbatim and
sits next to the new criterion instead of being overwritten by it, so a reader
can see what was derived from what.

Cost: a wide CSV that is awkward to read in a terminal.

### Original claim ids were kept

The Baker claims stay `B001` to `B016` rather than being renumbered to the
`YYYY-MM-NN` scheme used for new claims. Any earlier note or message referring
to `B008` still resolves.

Cost: two id schemes in one file, documented in methodology.

### Horizon labels were converted to dates by fixed public rules

The original horizons were labels such as `ongoing`, `point in time` and
`multi-year`. Those cannot be scored, because there is always a reason to wait
another quarter. Each label maps to a date by a rule written down in
methodology before any claim resolved.

`ongoing` became a one-year review date and `multi-year` a two-year one. Both
are arbitrary. They are written down so they are arbitrary once rather than
arbitrary again at every review.

Cost: a framework claim now gets scored on a date that its author never set,
which will sometimes feel unfair to the claim.

### date_said and date_entered are separate fields

The call was 2026-10-29. These claims were entered 2026-10-30. Collapsing the
two would have made the ledger look like a live transcript of the call.

Cost: nothing, beyond one more column.

### Criteria state what would falsify the claim

Each criterion says what observation counts against the claim, not only what
counts for it. Two say outright that `unverifiable` is the likely outcome:
B009, because no daily GPU rental index can be reconstructed for October after
the fact, and B011, because a filing may simply not appear. B016 is
conditional, so its criterion scores the antecedent first and returns
`unverifiable` if the condition never fires, on the reasoning that a
conditional whose condition never triggers has not been tested.

Cost: this will produce more `unverifiable` verdicts than a looser reading
would, and a scorecard with many unverifiables looks weaker than one that
reaches for answers. That appearance is the point.

### The top-10 flag resolved from three values to two

The flag briefly carried `unknown` for eleven companies absent from the
original coverage file. The owner confirmed the top 10 list is complete, which
makes absence a fact rather than a gap, so those eleven are now `no`.

One position is still unidentified. The list holds ten and nine are named; the
tenth appears in the source as "United" and has not been matched to a company.
Resolving the eleven to `no` is safe because none of them is named United.

Cost: the `yes` rows number nine, not ten, so any count off this column
understates the top 10 by one. If "United" turns out to be a company already
in the universe, its row currently reads `no` and will need a correcting
commit.

### B011's criterion was tightened

The original wording, "publicly reports" within 30 days, left the source open
and would have invited an argument at the horizon about whether a press
mention or an interview counted. It now names Anthropic S-1/A amendments filed
with the SEC on or before 2026-11-28.

One branch was added beyond the instruction. An exactly unchanged ARR figure
is neither an increase nor a decline, so it scores wrong, carrying over the
prior criterion's reading that a flat update is not a positive one. Without
that branch the criterion has a hole at precisely the value most likely to
cause a dispute.

The revision happened on 2026-10-30, before the 2026-11-28 horizon and before
any outcome was known, so the rule that criteria predate outcomes still holds.
The original wording is in git at 967fbf0 and the row's notes point there.

Cost: this is a criterion rewritten after the claim was logged. It was legitimate
here because nothing had resolved, but the same move made after a horizon
passes would be indefensible, and the precedent needs watching.

### The CSVs are canonical and the database is disposable

`data/scorecard/*.csv` and the two files in `data/` are the record. SQLite at
`data/research.db` is built from them by `scripts/build_db.py`, is gitignored,
and is dropped and rebuilt on every run. Nothing is written back to the CSVs.
No fact exists in the database that the CSVs do not already hold.

The alternative, making SQLite primary and exporting CSVs, is the normal way
to build this and would be better at everything except the one thing that
matters here. A binary file does not diff. The whole claim of this repo is
that a reader can see what changed and when, and a commit that says "database
updated" cannot be audited by anyone, including its author a year later.

Cost: every collector has to handle append-only text safely, duplicate
protection is the collector's job rather than a unique index, and large
series will eventually make the CSVs unwieldy. `elasticity.csv` took on 860
rows from one run, so that day is not far off.

### Scorecard files gained entity and entity_class

CLAUDE.md names seven columns. The scorecard files now have nine, with
`entity` and `entity_class` added, and all five share the header.

The pillars are mostly per-entity series. A token price is the price of a
particular model, a spread is a spread on a particular issuer. With seven
columns the entity has to be encoded into the metric name, which makes the
series unqueryable and breaks the rule that a metric name keeps one
definition forever. The generic pair was chosen over a model-specific one so
that all five files stay stackable into a single table.

Cost: a documented deviation from CLAUDE.md, which should be reconciled.
Two columns will sit empty on any market-wide metric.

### Raw API responses are committed

Each collector writes the unmodified response to
`data/raw/<source>/<date>.json` before parsing, and those files are in git.
The first one is 1.2 MB.

Parsing is a judgment and can be wrong. A price on a specific past date
cannot be re-collected, only re-derived, and only if the original response
was kept.

Cost: repo size grows by roughly 1.2 MB a month from this collector alone,
which is fine for years and not forever.

### Open or closed weights is decided by a rule, not by knowledge

`entity_class` comes from two tests in order: a non-empty `hugging_face_id`
means `open_weights`, then a short list of six closed-weight organisations
means `closed_weights`, then everything else is `unclassified`. On the first
run that left 80 of 430 models unclassified, about a fifth.

Some of those 80 could be classified from memory. Cohere and ByteDance Seed
are in the group. They were left alone on purpose. A tag applied from what
the author happens to know is not reproducible by a reader, will not be
applied consistently in twelve months, and quietly turns a measured series
into an opinion. The rule is auditable and its failures are visible in the
`unclassified` count.

Cost: `open_weights` is a floor rather than a count, since a model published
somewhere other than Hugging Face reads as unclassified. Any open-share
figure taken off this column understates the real one, and the note needs to
say so rather than quoting it as measured.

## Open questions

Carried forward until resolved. Resolving one is a new dated entry, not an
edit here.

- Which holding is "United" in the Atreides Q3 2026 top 10.
- Whether Cerebras, Anthropic and SpaceX (xAI) are listed, currently `verify`
  in the coverage universe.
- Whether OpenRouter data alone is a defensible basis for the
  `open_source_share` pillar given it misses direct API traffic, or whether a
  second source is needed before the first note.
- Which of the 80 unclassified organisations can be moved onto the
  closed-weight list with a checkable source rather than from memory.
- Whether `elasticity.csv` should keep taking 860 rows a month, or whether
  per-model prices belong in their own file with only aggregates on the
  pillar series.
