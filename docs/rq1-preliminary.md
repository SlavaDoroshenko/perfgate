# RQ1, preliminary observations (updated 2026-09-17)

**Status: two days of data — 1780 loads in 55 jobs, no failed loads. Directional, not final.**
GitHub-hosted `ubuntu-24.04`, Chrome 153.0.8010.47, Lighthouse 13.4.1, two pages of the demo app
served from localhost. All statistics are grouped per build (commit); see "Build isolation" in
`protocol.md`.

## 0. The bundle is part of the experiment

Four build epochs exist in the data. The light page under `simulate`:

| Build | Jobs | FCP | LCP |
|---|---|---|---|
| `0d567a8` | 2 | 1202.7 | 1504.1 |
| `5b4491b` (shared chunk) | 6 | 1353.4 | 1654.8 |
| `8bd59a9` | 2 | 1202.2 | 1503.2 |
| `a79b8cb` (separate builds) | 4 | 1202.3 | 1503.4 |

Building both pages together made Vite extract a shared chunk; one extra request cost ~150 ms of
modelled FCP/LCP under `simulate` and nothing under `devtools`. After splitting the builds the
metric returned to its original level, which confirms the cause. Any analysis that ignores the
build would have reported this as a 6.4% cross-job noise level — an artefact ~100x larger than the
real one (0.04%).

## 1. Same-job comparison is 3-13x more sensitive than a stored baseline

Robust CV inside one job vs CV of job medians across jobs of the same build (3 jobs each):

| Page | Throttling | Metric | within job | between jobs | ratio |
|---|---|---|---|---|---|
| heavy | devtools | TBT | 1.40% | 17.85% | 12.7 |
| heavy | devtools | LCP | 0.66% | 4.52% | 6.8 |
| heavy | devtools | FCP | 0.46% | 1.91% | 4.1 |
| light | devtools | LCP | 0.24% | 0.95% | 4.0 |
| light | devtools | FCP | 0.38% | 1.32% | 3.5 |

Under `simulate` the ratio drops below 1 (0.2-0.7): modelled metrics barely react to the machine,
so a stored baseline is as good as a same-job one — at the price described in section 3.

## 2. Cross-job noise is mostly a hardware lottery

Median metrics of the heavy page, `devtools`, by runner CPU:

| CPU | FCP | LCP | TBT |
|---|---|---|---|
| AMD EPYC 9V74 | 1757 ms | 2330 ms | 378 ms |
| AMD EPYC 7763 | 1804 ms | 2493 ms | 485 ms |

The light page barely moves between CPU models (LCP 2250 vs 2247 ms). Sensitivity to the runner
grows with main-thread work, i.e. precisely where regressions matter.

## 3. `simulate` is stable but blind

Between-job CV of FCP/LCP under `simulate` is 0.02-0.04%, because Lantern re-estimates metrics from
a model and never sees the hardware. The same modelling hides real regressions: `lcp-delay:800`
produces no change at all under `simulate`, while `devtools` shows +840 ms. Stability is bought
with sensitivity.

## 4. Sequential series raise 5x more false alarms than interleaved ones

A/A jobs where two-sided Mann-Whitney reported a difference between "base" and "pr" at α=0.05,
pooled over FCP, LCP and Speed Index, both pages, both throttling modes:

| Mode | Alarms | Checks | Rate |
|---|---|---|---|
| `abab` | 3 | 72 | **4.2%** |
| `sequential` | 15 | 72 | **20.8%** |

`abab` lands on the nominal 5%; `sequential` is four times above it. The same asymmetry shows in
raw shifts: 10 of 72 sequential jobs move the median by more than 0.5%, against 1 of 72 for `abab`.

**But the size of these false alarms is negligible.** Every alarm above is between -0.62% and
+0.54%, median -0.04%. With n=20 and a within-job CV of ~0.3%, the test resolves differences of
0.2%, and a series that drifts by 0.2% is enough to trip it. The drift is mostly negative (the PR
half of a sequential series tends to be slightly *faster*), i.e. the machine speeds up during the
series rather than slowing down.

Practical conclusion, and it belongs in RQ2: a p-value alone is not a decision rule. Pairing
significance with a minimum effect size (say, 1%) removes every false alarm observed here without
touching a real regression of the size anyone cares about. This is the argument for reporting a
confidence interval of the effect (Hodges-Lehmann, as sitespeed.io does) instead of a bare verdict.

## 5. MDE (resampling of real A/A loads, Mann-Whitney, power 0.8)

| Page | Throttling | Metric | n=5 | n=10 | n=20 |
|---|---|---|---|---|---|
| light | both | FCP/LCP | 1-2% | 1% | 1% |
| heavy | devtools | FCP/LCP | 2-10% | 1-2% | 1% |
| heavy | both | TBT | 5-7.5% | 2-3% | 2% |

The same procedure at δ=0 gives 0.034-0.060 against a nominal 0.05, so the resampling is
calibrated. 1% is the lowest grid point, so "1%" means "1% or better"; a finer grid is needed.

## Open questions
- **Warm-up.** TBT of the light page is zero in 557 of 560 loads; all three non-zero values occur
  in the first measured load of a job. One warm-up load may not be enough. Changing it now would
  start another protocol epoch — decide before the long collection.
- CLS on the heavy page is non-zero but nearly constant (0.154), so it needs absolute effects
  rather than relative ones.
- Only `ubuntu-24.04`, one app family, injected effects are pure multiplicative shifts.

## Next
Collect until there are tens of jobs per configuration and per build, then re-run
`python -m perfgate_analysis.report` and turn sections 1 and 4 into rates with confidence
intervals.
