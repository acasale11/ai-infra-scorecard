# The thesis view

`data/thesis_view.csv` holds the owner's monthly read on each pillar:
**strengthening**, **mixed**, or **weakening**, with one line of reasoning.

It ships empty and stays empty until he writes in it. Nothing sets it
automatically, and nothing ever will. That is the entire point of the file.

## Two signals, and they answer different questions

Every pillar carries two signals now, side by side in the weekly brief and on
the dashboard home page.

| signal | question it answers | who sets it |
| --- | --- | --- |
| data health, green / amber / red | is the evidence arriving? | computed from the files, every run |
| thesis view, strengthening / mixed / weakening | what does the evidence say about the thesis? | the owner, monthly |

They can disagree, and a disagreement is informative rather than a fault. A
pillar can be green and weakening: the data is arriving cleanly and it is
going against the thesis. A pillar can be red and strengthening: there is no
collector yet, and the owner's read from outside this repo is that the case
is getting stronger. Collapsing the two into one light would hide exactly
that.

## Columns

| column | meaning |
| --- | --- |
| `date` | The day the view was taken. Monthly is the expected cadence. |
| `pillar` | One of the five pillar names, spelled as in the data files. |
| `view` | `strengthening`, `mixed`, or `weakening`. Leave the row out entirely rather than guessing. |
| `reason` | One line, in the owner's words. What in the evidence moved the view. |

## Rules

Append only, like everything else here. A new monthly read is new rows, not
an edit to the old ones. The history of how a view changed is the valuable
part: a view that was weakening in November and strengthening in February
says something, and only if both rows survive.

The brief and the dashboard show the latest row per pillar and the date it
was taken, so a view that has not been updated in months is visibly stale
rather than quietly current.

A pillar with no row shows as "not set" and nothing is inferred from its
absence.

## Why this is not automated

The data health signal is computed because it is a fact about files. The
thesis view is a judgement about what evidence means, and the judgements in
this project are the owner's to make and write. A generated thesis view
would be this repo telling him what he thinks, in a file whose purpose is to
record what he actually thought, dated, so it can be checked later.

If a mechanical thesis signal is ever wanted, it has to be driven by scored
claims in the ledger rather than by inference, and claims are scored at
their horizon and not before.

## Example of a filled row

```
date,pillar,view,reason
2026-11-30,elasticity,mixed,"Open weights still cheaper at mid tier but the gap halved when the cheapest model changed, so the advantage looks thinner than it did"
```
