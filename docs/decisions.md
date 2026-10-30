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

### Public identity is pseudonymous and lives in one file

The project publishes as Tony C., `@TonyC_research`,
`tonycresearch.substack.com`. No full name, employer or school goes on a
public output.

All three values sit in `config/identity.json` and are read through
`scripts/project_config.py`. Nothing hardcodes a handle. Changing the handle
later is one edit, and more to the point, there is exactly one place to audit
when checking that nothing has leaked.

A config file is worth it here for a reason beyond convenience. Semi-anonymity
fails through a single forgotten string in a footer. Centralising the identity
turns "did I remember everywhere?" into a question with a checkable answer.

Cost: one more indirection between a script and the text it prints.

### Semi-anonymous means pseudonymous, not untraceable

Worth stating plainly so nothing is written on a false assumption. The aim is
that a casual reader, or someone searching the owner's real name, does not
land here. It does not survive anyone determined. Nothing in this repo should
be written as though the pseudonym protects it, and the rule that no employer
material enters the repo at all remains the real protection.

### Git commit authorship contradicts the pseudonym, and is unresolved

Every commit so far, including this one, is authored with the owner's legal
name and his university email address. Not reproduced here, for the same
reason they should not be there: eleven commits carry both, in a repo intended
to become public. It is the exact thing the rule above forbids, and no chart
footer matters next to it.

Not changed unilaterally, because the options differ in ways only the owner
can weigh. Setting a pseudonymous `user.name` and a GitHub noreply address
fixes future commits and leaves the existing eleven. Rewriting history fixes
all of them but changes every hash, needs a force push, and sits badly with
the decision to preserve the original upload commit. Leaving it is defensible
only while the repo stays private.

A second leak of the same kind, found in the same pass. CLAUDE.md and
`docs/methodology.md` both named the owner's employers in the course of
writing the rule that forbids mentioning them, and a first draft of the
public outputs section added the university too. The draft was fixed before
committing. The employer names were inherited from the original CLAUDE.md
and are still there, inside the integrity rules, where they read as the thing
being prohibited rather than as a disclosure. They are still two real
employer names in a file meant to go public, and they need the owner's call
alongside the authorship question.

The general lesson, logged because it will recur: a rule that forbids naming
something cannot be written by naming it.

The repo is private today, so nothing has leaked yet. This stays an open
question until the owner picks one, and it must be settled before the repo is
made public or the first chart is posted.

### Git metadata is out of scope for the pseudonym (resolves the two entries above)

The owner's call, and it supersedes the two open items logged earlier today.

The repo stays on his personal GitHub account with commit authorship
unchanged. The account and every commit are traceable to him, and that is
accepted rather than tolerated. No history rewrite, no pseudonymous
committer, no noreply address.

The semi-anonymous rule applies to the content of public outputs: charts,
the dashboard, notes, posts, and the prose in this repo. It does not apply to
git metadata. The pseudonym is a presentation layer that keeps the owner's
legal name off the byline and out of a search result. It was never
concealment, and treating it as concealment is what produced the earlier
flag.

The employer names are removed from CLAUDE.md and methodology.md and replaced
with "the owner's current and future employers", which states the rule
without being the disclosure. The phrasing is future-proof, so a job change
does not need an edit. A scan of the whole working tree returns no mention of
the employers, the legal name, or the university.

CLAUDE.md now says explicitly that git metadata is out of scope and that this
should not be raised again, so the next agent to read it does not relitigate
a settled decision.

Cost: anyone who opens the repo sees who wrote it. That is the intended
trade. The thing it buys is that the work does not surface under the owner's
legal name, and that employer material never enters the repo at all, which is
the rule that was always doing the real protective work.

### Weight classification moved to its own dated table, with evidence per row

`data/model_classification.csv` now holds the class, and `elasticity.csv`
keeps whatever class was in force when each price row was collected. Existing
rows are not rewritten, so the join is the price series to the current
classification.

Classification is evidence-backed rather than remembered. A model is open
because OpenRouter gave it a `hugging_face_id` or because a weights repo was
found under the organisation's namespace, and the row carries the repo URL.
It is closed because the organisation is on the closed list, or because its
namespace demonstrably publishes weights and holds nothing for this model.
That last step is the only inference, and it is gated on proving the
namespace publishes before a miss counts.

Unclassified fell from 80 to 42. The remainder is 25 models whose
organisation has no mapped namespace and 17 hosted variants of open bases,
each with a reason on the row.

Cost: a join instead of a column, and a classification that can move between
runs. The second is the point. It also depends on Hugging Face as a second
external source, so a Hugging Face outage degrades a run.

### Tier bands are frozen, and the result argues against the thesis

*Superseded in part on 2026-10-30 by "The frontier gap reads differently against B003 and B015" below. The reading of B003 here is wrong. The entry is left as written.*

Tiers come from the Artificial Analysis intelligence index in the OpenRouter
payload, in absolute bands rather than percentiles, frozen in
`config/weight_classes.json` on 2026-10-30. Price is never an input, since
the output is a price comparison.

The bands were set before the comparison was run, and they are not revisited
to accommodate what the comparison showed. That rule exists because of what
it showed: no open-weight model reaches the frontier band. The highest
scoring open model is GLM-5.3 at 31.7 against a floor of 45. Lowering the
floor to 30 would manufacture an open frontier entrant and a much friendlier
chart, which is exactly why the bands are frozen.

The tier cut also shrinks the headline. The uncontrolled comparison made open
weights look six times cheaper on input; controlled for tier, open is much
cheaper in the mid tier, roughly level on input price at entry level, and
absent at the top. Part of the original gap was a mix effect.

This is evidence against claims B003 and B015 rather than for them. Neither
moves off `pending`, because both carry horizons that have not arrived and
scoring early is exactly what the rules forbid. It is recorded here so the
first note does not quietly lead with the friendlier uncontrolled number.

Cost: the comparison covers the 54 models carrying an index, not the 430
priced ones, so it is a statement about scored models and has to be worded
that way.

### The frontier gap reads differently against B003 and B015

Correcting the entry above, on the owner's reading. The tier result is not
evidence against B003.

B003 is the hybrid routing claim: a post-trained open model handles routine
work and a frontier model handles the hard queries, at roughly 25 to 30
percent of frontier cost. That design assumes a frontier capability gap. It
is the reason the router exists. So a snapshot showing no open model at the
frontier, combined with a large mid-tier price gap, is what the claim
predicts, not a contradiction of it. The mid tier is where routine traffic
is served, and open weights there are roughly five times cheaper on output.
Recorded as consistent with B003.

B015 is different. It claims the industry is heading toward strong open
source alongside several competitive frontier labs. A frontier band with no
open entrant does not refute that today, since the claim has a multi-year
horizon and describes a direction. But if that gap persists or widens, it
weakens the claim directly. Recorded as a watch item for B015: track whether
the highest open-weight intelligence index closes on the frontier floor, and
report the gap in each monthly note.

Neither status changes. Both stay pending, both horizons are years out, and
scoring early is what the rules forbid. The error here was mine and it was an
error of interpretation, not of data: I read a capability gap as damaging to
a claim that is built on the existence of a capability gap. Logged because
the failure mode generalises. A framework claim is easy to score against by
testing something adjacent to what it actually says.

### The open entry tier looks dearer than the open mid tier, and it is not an outlier

Median output price for open weights came out at 1.35 in the entry tier
against 0.87 in the mid tier, which reads backwards. Investigated rather than
left in the chart unexplained.

It is not an outlier effect. Dropping the obvious outlier, `moonshotai/kimi-k3`
at 15.00 per million output tokens, moves the entry median only from 1.35 to
1.20, still above the mid tier. Dropping the top two leaves it at 1.20.

The instability is in the mid tier, not the entry tier. Open mid holds seven
models in two clusters, three cheap speed variants at 0.14, 0.28 and 0.30,
and three dear models at 2.10, 2.70 and 3.60. The median is the single model
in the gap between them, `xiaomi/mimo-v2.6-pro` at 0.87. Swap that one model
out and the mid median moves to 0.30 or to 2.10. A median resting on one
observation in a bimodal sample of seven is not a number to publish a
conclusion on.

The deeper reason is that price and capability are close to unrelated inside
the open-weight set. Pearson correlation between the intelligence index and
log output price across the nineteen scored open models is -0.001. Price
tracks serving cost, meaning parameter count, architecture and whether the
SKU is speed-optimised. It does not track capability. The cheap mid-tier
models are all flash variants; the dear entry-tier ones are large models such
as `nvidia/nemotron-3-ultra-550b-a55b` and specialty models such as
`thinkingmachines/inkling`.

What this costs the tier comparison: the cross-tier ordering of open-weight
medians carries no signal at these sample sizes, and the note should not
claim one. The open-versus-closed comparison within the mid tier is the
usable result, and even that rests on seven models against six.

`moonshotai/kimi-k3` is also a likely bad data point rather than a cheap
model priced oddly. It is the fourth most expensive model in the catalogue at
15.00, above `anthropic/claude-sonnet-5.5` at 10.00, while scoring 17.4. Its
own successor `kimi-k3.1-pro` scores 46 at a lower price of 10.00. A model
priced above Sonnet and scoring in the entry band is not plausible, and a
stale index entry is the likelier explanation. See the index lag caveat in
methodology.

## Open questions

Carried forward until resolved. Resolving one is a new dated entry, not an
edit here.

- Which holding is "United" in the Atreides Q3 2026 top 10.
- Whether Cerebras, Anthropic and SpaceX (xAI) are listed, currently `verify`
  in the coverage universe.
- Whether OpenRouter data alone is a defensible basis for the
  `open_source_share` pillar given it misses direct API traffic, or whether a
  second source is needed before the first note.
- Which of the 25 organisations still lacking a Hugging Face namespace can
  be mapped in `config/weight_classes.json`, and whether the 17 hosted
  variants of open bases deserve a class of their own rather than sitting in
  unclassified.
- Whether a second capability source is needed, given only 54 of 430 priced
  models carry an Artificial Analysis index, and given at least one index
  value (`moonshotai/kimi-k3`) looks stale.
- Whether tier medians should be reported at all below some minimum sample
  size, or replaced with the full distribution.
- B015 watch item: whether the gap between the highest open-weight
  intelligence index and the frontier floor closes, holds or widens.
- Whether `elasticity.csv` should keep taking 860 rows a month, or whether
  per-model prices belong in their own file with only aggregates on the
  pillar series.
