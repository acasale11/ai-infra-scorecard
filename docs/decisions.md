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

### The median-by-tier chart is retired in favour of a price-performance frontier

The primary chart is now a scatter of capability against output price on a
log scale, with the frozen tier bands shaded behind it and a step line per
weight class showing the cheapest model that clears each capability floor.

The median chart was retired because it answered the wrong question, not
merely because its samples were thin. A buyer does not purchase the median
model in a tier. They purchase the cheapest model that clears their bar, so
the minimum is the statistic that matches the decision.

The two disagree on this data, which is what forced the change. The tier
medians showed closed weights 4.8 times dearer than open in the mid tier.
The frontier shows `anthropic/claude-haiku-5.5` at 0.50 per million output
tokens, cheaper than the open mid-tier median of 0.87 and cheaper than every
open model in the catalogue scoring above index 29. The closed mid tier holds
a few expensive models that pull its median up while Haiku sits at the
bottom of it. Both numbers are arithmetically right. A note led by the median
would have told readers open weights were several times cheaper at mid-tier
capability, which is not true of anything they could actually buy.

The frontiers cross at about index 29, and the open frontier ends at 31.7.
That crossover is invisible in any median, and it is the most decision-
relevant fact in the dataset.

What this does to B003: it sharpens the reading rather than reversing it.
Routing open-first still pays, but the band where it pays on output price is
roughly below index 29, narrower than the tier medians implied. Open weights
keep a wider advantage on input price, which the chart does not show and the
note will have to state.

The tier medians are kept. Each run writes them to
`notes/charts/<date>-tier-medians.csv` and the table stays in methodology.
They are the right summary of a tier's shape and the wrong answer to a
buying question, so they stay in the data and out of the headline.

Cost: the scatter is a denser chart that asks more of a reader than a bar
chart does, and it leans on an index with known coverage and lag problems,
now in two places rather than one.

### Prices are the model author's own, not OpenRouter's cheapest endpoint

The frontier now prices every model at its maker's standard list price, from
`data/price_verification.csv`. This started as a verification task and turned
into a correction.

OpenRouter's headline price is the cheapest endpoint across all providers.
For a closed model that is the author. For an open-weight model it is one of
forty resellers, typically at fp4. `glm-5.3-flash` spans 0.14 to 0.75 across
its endpoints; the headline took 0.14 while Z.ai charges 0.50. Comparing
those two sides put a quantized reseller price against a frontier lab's list
price and called the gap an open-weight discount.

The effect is large and one-directional. At the mid floor the open advantage
was 4.4x on headline prices and is 1.48x on author prices. Four models are
flagged where the headline sits below the author's own price, all four open
weights, none closed.

Five spot checks against provider pricing pages all matched the first-party
endpoint exactly, which is what gives confidence in the endpoint data as a
proxy for the published page. The OpenAI page returned 403 to an automated
fetch, so those models rest on endpoint data alone and say so.

Cost: six open-weight models whose authors do not serve them are now
excluded, which is a one-sided exclusion. All six score below 25 so no
reported floor moves, but it has to be restated whenever the numbers are
quoted. The comparison also now depends on a second OpenRouter endpoint and
on provider pages that change without notice.

### The blended price changes the size of the gap, not the conclusion

Blended price is (R * input + output) / (R + 1), base 5:1, with 1:1 and 20:1
as sensitivity, all in `config/weight_classes.json`. R is an assumption:
there is no public token mix for this catalogue.

The crossover sits at index 29.9 under every ratio tested, including output
only. That is not robustness in the pricing: it is that the crossover is set
by open models running out of capability at 31.7 rather than by the token
mix. Worth stating that way, because "insensitive to assumptions" sounds like
a stronger result than it is.

What does move is the size of the open advantage below the crossover, and it
moves against open weights as input share rises: 1.79x on output alone, 1.48x
at 5:1, 1.39x at 20:1. Open weights are relatively cheaper on output than on
input among these models, so an input-heavy workload erodes their edge.

### What this comparison cannot test, written down before publishing

A limitations section now sits in methodology. The short version: this
compares off-the-shelf models at published API prices on a general capability
index. B003 is about post-trained open models, behind a router, where
self-hosting is a live option and capability is task-specific. Each of those
is outside what this measures.

So the pillar tests the simplest form of B003, and the answer to that narrow
question on 2026-10-30 is no: you cannot buy frontier capability off the
shelf from an open-weight model at any price, and below the frontier the
discount is smaller than the headline suggested. B003 itself is not scorable
from this data and must wait on `experiments/routing`.

Logged because the temptation at publication time will be to let a clean
chart stand in for the claim it is adjacent to. The chart is about token
list prices. The claim is about a system.

### Three price bases, because there is no single right price

Correcting the previous entry, on the owner's reading. Pricing every model at
its author's list price was the wrong fix.

Multi-provider competition on open weights is a real, purchasable advantage
and is a large part of what the thesis is about: anyone can serve published
weights, so the price falls toward the cost of compute. `glm-5.3-flash` has
40 providers and that is the point of it being open. Collapsing that to the
author's list price deletes the mechanism being measured.

The actual confound was precision, not resellers. The cheapest endpoint for
an open model is often a 4-bit build set against a closed model served at
full precision.

So three bases are carried and the spread between them is reported:
cheapest at any precision as a lower bound, cheapest at fp8 or better as the
base case, and the author's list price as an upper bound. The base case keeps
the competition and drops the precision mismatch.

The open discount at the mid floor is 6.4x, 4.3x or 1.5x across those three.
That range is the honest answer, and no single number should be published
without its basis.

Undeclared precision counts as qualifying for the base case. Of 94 closed
endpoints, 92 declared nothing, so excluding undeclared endpoints would empty
the closed side. The cost is that an undeclared endpoint could be a
lower-precision build, which would understate the base case.

Cost: three numbers to explain instead of one, and the base case drops
`kimi-k3.1-pro`, served only at mxfp4, while the author basis drops six
open-weight models. Coverage now differs between bases, which has to be
stated whenever they are compared.

### Provider price spread is now a metric, not a footnote

Four metrics per open-weight model under `open_source_share`:
`provider_competition_count`, `provider_price_spread_ratio`,
`provider_price_min` and `provider_price_max`. 656 rows on the first run.

How much competition published weights actually attract is a direct measure
of what open weights are worth, and it belongs in the pillar rather than
buried in a chart footnote.

It already says something. Across 165 open models the median has 2 providers
and a 1.01x spread; the most contested has 14.5x. Competition is
concentrated in the models people use, not spread across the open catalogue.
A claim that open weights commoditise inference is really a claim about a
dozen models.

### The limitations section no longer answers B003

Revised. It had said the simplest form of B003 was answered no. That
overstated the data twice over.

First, the affordability half depends on the price basis, which moves the
answer by a factor of four. Second, "can you buy frontier capability off the
shelf at a lower token price" was never B003's claim. B003 is about a
post-trained open model behind a router, which is a system, not a catalogue
entry. A price table cannot answer it in either direction.

What the pillar can say: within the scored subset, open weights are
meaningfully cheaper at mid-tier capability, by somewhere between 1.5x and
6.4x depending on basis, and no open model clears the frontier floor at any
price. Both hold across every token mix tested. That is a statement about
token prices and capability coverage, not a verdict on a claim.

Logged because this is the second time the interpretation ran ahead of the
data in the same direction, toward a cleaner story than the evidence
supports. The pattern to watch is reaching for a verdict on a framework claim
from whatever data happens to be in hand.

### Credit pillar mapped before anything was collected

Source map written, no collector built, waiting on approval. Recorded here
because the mapping turned up two findings and two blockers that shape what
gets built.

Findings. CoreWeave discloses six successive GPU-backed facility generations
at 15%, 11%, 9%, 9%, SOFR plus 2.25% and 4.50%. That ladder is close to a
direct measurement of lender appetite for GPUs as collateral over time, which
is the pillar question, and no other issuer read so far discloses anything
like it. Separately, Cipher issues secured notes at named project entities
rather than the parent, priced 6.00% to 7.125%, inside CoreWeave parent-level
notes at 9.00% to 9.75%. A ring-fenced contracted asset appears to fund
cheaper than corporate risk at a larger borrower. That is a testable claim
and belongs in the ledger once confirmed.

Blockers. Programmatic requests to sec.gov returned 403 from this
environment across several User-Agent strings, while the same URLs fetched
through a browser path worked. And the FINRA fixed income API returns 401
without credentials. Neither is hard to fix but both have to be fixed before
a collector is worth writing, so they are recorded as blockers rather than
noted in passing.

Everything in the issuer tables came from XBRL rendering pages, where
flattening makes column alignment ambiguous. The numbers are an inventory to
confirm against narrative footnotes, not a verified credit book, and the
section says so at the top. Publishing a coupon read off a flattened table
would be exactly the kind of error this repo is built to avoid.

Build order proposed: FRED benchmarks first because they have no blockers at
all, then SEC access, then the filings extractor, then TRACE.

### The date column holds the observation date for FRED rows

Every other collector stamps a row with the day it was pulled. The FRED
collector stamps it with the day the market data refers to, and records the
pull date in `notes` instead.

A model's listed price has no date of its own, so the collection date is the
only honest stamp available. A published index level does have a date of its
own, and it is the one that carries the meaning: high yield at 326 bps on
2026-10-29 belongs on 2026-10-29 whether it was fetched that evening or three
years later. Stamping all 7,742 observations with 2026-10-30 would have
stacked three years of market history onto a single day and left the series
unusable for the thing it exists to do, which is show movement over time.

This is not the backfilling the integrity rules forbid. Nothing claims to
have been collected earlier than it was, the collection date is on every row,
and no measurement is reconstructed after the fact. FRED is publishing a
dated historical record and the dates are part of what is published.

Cost: the `date` column no longer means the same thing in every pillar file,
so anything reading across pillars has to know which collector wrote the row.
The `source` column tells it.

### FRED serves only three years of spread history, and the window moves

Tested on 2026-10-30. The eight ICE BofA series return exactly three years
and ignore the `cosd` and `coed` date parameters, so 2023-10-31 is the
earliest observation obtainable, not the earliest that exists. DGS10 is a
Federal Reserve series with no such cap and returned 1962 onward.

Two consequences, and the second is the one that matters.

The intended pre-cycle baseline is not available. The window opens a year
after ChatGPT and well after the 2022 rates drawdown, so there is no quiet
period and no prior stress episode to measure a future widening against.
Every percentile quoted off these series is a percentile of three mid-cycle
years, which is a much weaker statement than it sounds.

And the window rolls. Observations drop off the back as time passes and
cannot be fetched again. `data/scorecard/credit.csv` is therefore not a
convenience copy of a source that will always be there; for anything older
than three years it will eventually be the only copy. That turns the
append-only rule from good hygiene into the thing holding the series
together, and it is an argument for collecting on a schedule rather than
when convenient.

Cost: the spread series and the Treasury series cover different spans, so any
chart combining them has to say so.

### FRED revisions are reported, never rewritten

On each run the collector re-reads the overlap between what FRED now serves
and what is already stored, and prints any value that has changed. It does
not update the stored row.

FRED does revise, rarely. Silently overwriting would mean the file quietly
stopped matching the commit that created it, and the record would lose the
one property it is built for. A revision is a new fact: it belongs in a new
dated commit with an explanation.

Cost: a revised value sits in the file as a known-stale number until someone
acts on the warning. The warning prints on every run, so it does not get lost,
but nothing enforces acting on it.

## Open questions

Carried forward until resolved. Resolving one is a new dated entry, not an
edit here.

- Which holding is "United" in the Atreides Q3 2026 top 10.
- How to reach SEC EDGAR programmatically from this environment, given 403s
  on direct requests.
- Whether the CoreWeave DDTL rate ladder is a true like-for-like sequence or
  whether the facilities differ in collateral and seniority in ways that make
  the comparison invalid.
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
- Whether credit collection needs a schedule rather than running when
  convenient, given the ICE BofA three-year window rolls and lost
  observations cannot be re-fetched.
- Whether the CCC bucket sitting at the 99th percentile of its three-year
  range, while BB sits at the 73rd and investment grade at the 62nd, has
  anything to do with AI infrastructure credit. The index-level data cannot
  say. It needs issuer-level spreads, which needs TRACE.
