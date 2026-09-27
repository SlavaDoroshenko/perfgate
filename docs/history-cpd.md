# History: change point detection on the main branch (first prototype, 2026-09-27)

**Why a second level.** The same-job comparison answers "did this PR make the page slower".
It is blind to two things: a slow creep (ten PRs of +0.5% each pass every gate, the page is 5%
slower) and a regression merged without the check. Both show up only in the history of the main
branch. Mozilla (Perfherder), MongoDB, Netflix and Apache Otava (ex-Hunter) detect regressions on
history with change point detection (CPD); none of them does it for browser metrics on shared
CI runners, where the history is exactly what RQ1 shows to be noisy.

**Question.** How large must a step in the history be before CPD finds it on GitHub runners, and
how much of the hardware lottery (`rq1-preliminary.md`, section 2) can be removed by accounting
for the runner CPU?

## Method

- **Series.** One point per scheduled A/A job: the median of its 20 base loads. `abab` jobs,
  current protocol, 40 jobs per page for the SPA pages (2026-09-17 … 09-27), 24 for static/SSR.
  This is the series a tool would get from one measurement of `main` four times a day.
- **Two versions of the series.** *raw*, and *cpu-adjusted*: every job median divided by the
  median of the jobs that ran on the same CPU model.
- **Detector.** E-Divisive with one change point (energy statistic, α=1), the method behind
  MongoDB's and Otava's detectors; significance by a permutation test (199 permutations, α=0.05).
- **Evaluation.** Windows of 20 consecutive jobs (5 days). With nothing injected, a detection is a
  false alarm. For power, the second half of the window is multiplied by 1+δ, i.e. a step of known
  size 10 jobs (2.5 days) before the end. History MDE = smallest δ found in ≥80% of windows.

Code: `analysis/perfgate_analysis/history.py`. Reproduce:

```sh
cd analysis
uv run python -m perfgate_analysis.history ../../perfgate-data/raw --out reports/history \
  --warmup 2 --epoch fa45447b5c39 --epoch 467c2a6f9f6c --epoch 12817a1ef4f9
```

## Results

History MDE (step found in 80% of windows) against the same-job MDE from RQ1 (10 loads per
variant, `abab`), `devtools`:

| Page | Metric | Same job, n=10 | History, raw | History, cpu-adjusted |
|---|---|---|---|---|
| heavy | FCP | 0.75% | 5% | **2%** |
| heavy | LCP | 1.5% | 10% | **2%** |
| heavy | TBT | 3% | 30% | **7.5%** |
| light | FCP | 0.75% | 3% | **2%** |
| light | LCP | 0.5% | 2% | **1%** |
| SSR | FCP / LCP | 0.75% | 2% | **0.5%** |
| SSR | TBT | 7.5% | >30% | **7.5%** |
| static | FCP | 0.75% | 1% | **0.5%** |

Under `simulate` FCP/LCP steps of 0.5-1% are found in both versions (the modelled metric barely
depends on the machine); TBT needs 15-30% raw and 5-15% adjusted.

False alarms without a step: 0% of windows for most series, raw and adjusted. Exceptions, all in
the adjusted series: heavy TBT `devtools` 24% (5 of 21 windows), heavy FCP `devtools` 10%,
static LCP `simulate` 1 of 5 windows. Windows overlap, so these rates rest on few independent
stretches of history.

## What this says

1. **On raw history, CPD is 3-10x less sensitive than a same-job comparison** — the RQ1
   between-job noise translated into a detector. On the heavy page it needs a 10% LCP step and a
   30% TBT step: CPD on raw GitHub-runner history finds hardware, not regressions.
2. **Accounting for the CPU model recovers most of the gap for FCP/LCP**: 2% on the heavy page,
   0.5-1% on the lighter ones — comparable to the same-job comparison (a history point is a median
   of 20 loads, and ten of them follow the step), at the cost of a delay: here 10 jobs, 2.5 days.
3. **TBT stays the hard case** on history too, and it is where the adjustment also brings false
   alarms. A per-CPU baseline needs enough jobs on each CPU model; rare models (6-14 jobs over ten
   days) make it unstable.

For the tool this supports a two-level design: a gate on every PR (same job, interleaved,
Mann-Whitney + 1% + Holm), and CPD on the history of `main` with the runner CPU recorded and
adjusted for, for the slow creep that no single PR comparison can see.

## Caveats — this is a prototype

- The per-CPU reference is computed from the whole window before the step is injected, which is
  optimistic: a running tool only has the history before the change. Next step: compute it from
  earlier jobs only.
- Ten days of history; 21 overlapping windows for the SPA pages, 5 for static/SSR.
- One change point per window, a pure multiplicative step. Gradual drifts (the actual slow creep)
  and several steps per window are not evaluated yet.
- Not yet compared with other CPD methods (PELT, Mozilla's t-test on sliding windows) or with the
  Lighthouse `benchmarkIndex` as an alternative machine adjustment.
