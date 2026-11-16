# Follow-up cohorts of 17 November 2026: CLS, tail signal, shared-server load

Recorded before the first run of `.github/workflows/extensions.yml`. Hashes of the new
instruments are in [extensions-2026-11-17.json](extensions-2026-11-17.json). The gate is
the frozen `browser-candidate-2026-10-30`, measured with the collector at its frozen
`SOURCE_SHA` (30ca833); nothing in the gate changes. The confirmatory result of
[11 November](../prospective-confirmatory-2026-11-11.md) stands as reported, including
the missed CLS target; these cohorts do not replace it.

Each run of the workflow collects ten jobs (20 loads per variant, two warmups,
devtools). The workflow dispatches the next run until **100 complete runs** (all ten
jobs stored) exist under `prospective/extensions-2026-11-17/` on the data branch.
The analysis uses the **first 100 valid jobs per job type in acquisition order**;
later jobs are reported as extra data. Wilson 95% intervals; temporal clustering is
checked by resampling acquisition days, as in the confirmatory report.

## A. CLS on a CLS-stable page

**Why.** In the confirmatory cohort the CLS targets were missed (87/100, 85/100; lower
bounds 79.0% and 76.7%). Every miss was on a CPU model other than AMD EPYC 7763, where
the original heavy page has two CLS modes caused by its own asynchronously growing
stats block ([CLS diagnosis](../cls-diagnosis-2026-10-30.md)). The reserved-layout
page (`scripts/prepare-cls-control.mjs`, part of the frozen sources' commit) reserves
that block, leaving only the banner shift: CLS = banner px / 823.

**Workload** `demo-heavy-reserved`. Baseline banner 64 px (CLS 0.0778).

| Job | PR variant | Nominal CLS change |
|---|---|---|
| `cls-aa-reserved` | same page | none |
| `cls-ls10-reserved` | banner 70.4 px | +10% (+0.0078, margin 0.005) |
| `cls-ls25-reserved` | banner 80 px | +25% (+0.0194) |

**Targets** (as in research-completion.md): CLS detection Wilson lower bound ≥ 80% for
each injected case; page-level A/A alarm (any metric) Wilson upper bound ≤ 5%.
Detection counts the CLS metric only. A positive result shows the gate detects CLS
changes when the page itself is CLS-stable; it does not repair the missed target on
the original page, which remains reported.

## B. Advisory tail signal for TBT

**Why.** The median gate misses rare long tasks
([rare-stall pilot](../tail-browser-results-2026-10-30.md): mean TBT +22–33%, median
unchanged, gate quiet). Only Welch's t-test flagged all three pilot jobs.

**Rule** (`scripts/tail_signal.py`, hash frozen): per page, one-sided Welch t-test on
TBT (PR mean greater), Holm over the pages of one check; a page warns when the adjusted
p < 0.05 and the mean TBT rose by more than max(10%, 20 ms). The signal is advisory: it
never changes the gate verdict.

**Data.**
- False warnings: the 200 four-page A/A suites of the confirmatory sample (already
  collected; this rule has not been computed on them before this record), plus the
  `cls-aa-reserved`, `tail-aa`, `load-aa-abab` jobs of this workflow (page level).
- Detection: `tail-rare` jobs, frozen pilot collector and fixture (`collect-tail.mjs`,
  `tail-heavy.html`), 3 of 20 PR loads with an 800 ms stall; the two predeclared pilot
  seeds alternate by run number. `tail-aa` jobs are the same page without stalls.

**Targets.** Suite-level false warning Wilson upper bound ≤ 5% on the 200 suites;
detection of `tail-rare` Wilson lower bound ≥ 80%. The gate's own decisions on
`tail-rare` are reported beside the signal.

## C. Shared single server: background CPU load

**Why.** A company GitLab on one server runs other jobs beside the measurement. The
cohorts so far ran on otherwise idle runners.

**Load.** `scripts/background-load.mjs`: two busy threads (the hosted runner has four
vCPUs) switched on and off for periods drawn uniformly from 5–60 s, seeded per job; the
schedule is logged. This stands for neighbouring build/test jobs; it does not model
memory, disk or network contention.

| Job | Order | PR variant |
|---|---|---|
| `load-aa-abab` | interleaved | same page |
| `load-aa-sequential` | sequential (all base, then all PR) | same page |
| `load-sd5-abab` / `load-sd5-sequential` | as named | script-delay 90 ms (FCP ≈ +5%) |
| `load-lt10-abab` | interleaved | long-task 99 ms (TBT ≈ +10%) |

The candidate requires interleaved order, so sequential jobs are evaluated with the
same per-page statistics (one-sided Mann–Whitney, Holm over the page's four metrics,
the frozen margins) applied to the sequential samples; this is the RQ3 comparison.

**Hypotheses and targets** (exploratory, declared here):
- C1. Interleaved A/A under load: page-level alarm Wilson upper bound ≤ 5%.
- C2. Sequential A/A under load raises more alarms than interleaved (reported with
  both intervals and a two-proportion difference).
- C3. Interleaved detection under load: FCP for `load-sd5-abab` and TBT for
  `load-lt10-abab`, Wilson lower bound ≥ 80%.
- Within-job noise (MAD/median) with and without load is reported against the idle
  `demo-heavy` jobs of the confirmatory cohort.

## Not changed

Policy, margins, correction, exclusions and the confirmatory sample. Any failure of a
target is reported as a failure; no job is dropped except invalid ones under the
existing validity rules, which are reported separately.
