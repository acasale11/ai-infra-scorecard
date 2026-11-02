# Open calls

`data/open_calls.csv` holds the owner's live calls. It ships empty and stays
empty until he writes one. A call is a judgement, and the judgements in this
project are his.

The weekly brief reads this file, prices each open call against its
benchmark, and flags any call trading near its exit level. It does not open,
close or grade calls.

## Columns

| column | meaning |
| --- | --- |
| `call_id` | Short stable id, e.g. `C001`. Never reused. |
| `date_opened` | The day the call was made, not the day it was written down. |
| `entity` | What the call is on. A ticker, or an `entity` value that appears in a scorecard file. |
| `direction` | `long`, `short`, `long_spread`, `short_spread`, or `flat`. |
| `claim_id` | The ledger claim this call expresses, if any. Links the call to the thesis it tests. |
| `thesis` | One line on why, in the owner's words. |
| `benchmark_metric` | The `metric` in a scorecard file used to price the call, e.g. `hy_ccc_oas`. Leave blank for a call the data cannot price. |
| `entry_level` | The benchmark value when the call was opened. |
| `entry_unit` | `bps`, `pct`, `usd_mm`, `ratio`, `x`. |
| `exit_condition` | Plain English: what would make this call done. |
| `exit_level` | The benchmark value that triggers the exit, where there is one. |
| `invalidation` | What would mean the call was wrong rather than early. Required. A call with no invalidation is an opinion. |
| `status` | `open`, `closed`, `invalidated`. |
| `date_closed` | Blank while open. |
| `notes` | Anything else. |

## Rules

Same integrity rules as everything else here. A call is never edited after
it is opened except to set `status`, `date_closed` and append to `notes`. A
changed view is a new call with a new id, and the old one is closed with a
reason. The record is meant to show what was thought at the time, including
the calls that aged badly.

`invalidation` is not optional. The point of writing it before the outcome
is that it cannot be rewritten after.
