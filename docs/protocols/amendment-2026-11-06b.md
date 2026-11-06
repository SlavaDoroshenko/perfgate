# Amendment of 6 November 2026 (b): chained candidate runs

Recorded before the first chained run.

## Why

GitHub dropped the scheduled `candidate` runs after the first manual one (none at
15:29 or 18:29 UTC on 6 November), and the scheduled `noise` workflow ran twice a day
instead of four times. The three-hour schedule would not reach the targets in
November.

## What changes

- After a run whose nine collection jobs all succeeded and whose data was stored,
  the workflow dispatches the next run (`workflow_dispatch` through `GITHUB_TOKEN`).
  The schedule stays as a restart if the chain breaks.
- The chain stops once 200 complete candidate runs (all nine jobs stored) exist on the
  data branch. A failed run does not dispatch another one.
- Runs follow each other around the clock, so they cover all times of day, but
  back-to-back runs are closer in time than under the schedule. Temporal clustering
  (by hour, day and CPU model) is reviewed before intervals are read as independent
  trials, as already required by research-completion.md.

## Fixed analysis sample

To avoid stopping when an interval looks good, the confirmatory analysis uses, in
acquisition order and pooled across the scheduled and candidate sources:

- the **first 200 complete four-page A/A suites**, and
- the **first 100 valid jobs per primary injected case**,

counted from the freeze. Jobs collected after those counts are reported separately as
extra data and do not change the confirmatory result. Policy, metrics, margins,
sample size, correction and exclusions are unchanged.
