# History: change point detection on the main branch (prototype 2026-09-27, online version 2026-10-05)

Latest evaluation: [18 October snapshot](research-2026-10-18.md), with guarded
benchmark adjustment, common permutations and 20/40-job windows. This remains a
research prototype; the observed false-alarm rates do not yet justify automatic blocking.

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
# past-only adjustment, step and ramp, E-Divisive vs Mozilla's t-test (about 4 minutes)
uv run python -m perfgate_analysis.history ../../perfgate-data/raw --out reports/history_online \
  --online --warmup 2 --epoch fa45447b5c39 --epoch 467c2a6f9f6c --epoch 12817a1ef4f9
```

## Results

History MDE (step found in 80% of windows) against the same-job MDE from RQ1 (10 loads per
variant, `abab`), `devtools`:

| Page | Metric | Same job, n=10 | History, raw | History, cpu-adjusted |
|---|---|---|---|---|
| heavy | FCP | 0.75% | 5% | **2%** |
| heavy | LCP | 1.5% | 7.5% | **3%** |
| heavy | TBT | 3% | 30% | **10%** |
| light | FCP | 0.75% | 3% | **2%** |
| light | LCP | 0.5% | 2% | **1%** |
| SSR | FCP / LCP | 0.75% | 2% | **1%** |
| SSR | TBT | 7.5% | 30% | **10%** |
| static | FCP | 0.75% | 2% | **1%** |

(Recomputed on data up to 05.10, 67 jobs per SPA series, 51 for static/SSR; within one grid step
of the 27.09 numbers.) Under `simulate` FCP/LCP steps of 0.5-1% are found in both versions (the modelled metric barely
depends on the machine); TBT needs 15-30% raw and 5-15% adjusted.

False alarms without a step: 0% of windows for most series, raw and adjusted. Exceptions, all in
the adjusted series: heavy TBT `devtools` 24% (5 of 21 windows), heavy FCP `devtools` 10%,
static LCP `simulate` 1 of 5 windows. Windows overlap, so these rates rest on few independent
stretches of history.

## Online version: only the past is known (2026-10-05)

The table above adjusts every window with a per-CPU reference computed over the whole series,
the window itself included. A running tool only knows the jobs before the window, so the
online evaluation (`history.py --online`) learns the adjustment from the past only:

- **cpu-past** - per-CPU median over all earlier jobs; models seen fewer than 3 times fall back
  to the median over all models;
- **bench-past** - a log-log regression of the job median on the median Lighthouse
  `benchmarkIndex` of the job (a CPU speed score Lighthouse measures before every load), fitted
  on earlier jobs, then divided out;
- **raw** - no adjustment.

Windows of 20 jobs start after 12 training jobs (36 windows for the SPA pages, 20 for
static/SSR). Two shapes of change in the second half: a **step**, and a **ramp** that grows
linearly to the full size at the last job (the slow creep). Two detectors: E-Divisive as above,
and the **shape of Mozilla Perfherder's detector** - the largest Welch t-statistic over the
splits of the window, alarm at t ≥ 7 (Perfherder's default).

History MDE (80% of windows), `devtools`:

| Page | Metric | Shape | E-Div raw | E-Div cpu-past | **E-Div bench-past** | Mozilla t raw | Mozilla t bench-past |
|---|---|---|---|---|---|---|---|
| heavy | FCP | step / ramp | 5 / 7.5% | 5 / 7.5% | **1 / 2%** | 10 / 30% | 3 / 5% |
| heavy | LCP | step / ramp | 7.5 / 15% | 7.5 / 10% | **3 / 5%** | 20% / — | 10 / 30% |
| heavy | TBT | step / ramp | 30% / — | — / — | **7.5 / 10%** | — | 20% / — |
| light | FCP | step / ramp | 2 / 3% | 2 / 3% | **1 / 2%** | 7.5 / 15% | 3 / 7.5% |
| light | LCP | step / ramp | 2 / 3% | 2 / 2% | **1 / 1%** | 5 / 10% | 2 / 5% |
| SSR | FCP / LCP | step / ramp | 1 / 2% | 1 / 1% | **1 / 1%** | 3 / 5% | 2 / 5% |
| SSR | TBT | step / ramp | 15 / 20% | 7.5 / 15% | 10 / 15% | — | 30% / — |
| static | FCP / LCP | step / ramp | 1-2 / 2% | 1-2 / 2-3% | 1-2 / 1-2% | 2-3 / 5-10% | 2 / 3-5% |

"—" = not reached by 30%. False alarms without a change (step 0, two independent estimates):

| Series | E-Divisive | Mozilla t |
|---|---|---|
| raw | 0-5% | 0% everywhere |
| cpu-past | 0-17% (heavy FCP 11-17%) | 0% |
| bench-past | 0-3% on heavy and SSR, **11-17% on the light page**, 0-20% on static | 0% |

What changed against the prototype:

1. **The per-CPU adjustment was the optimistic part.** Learned from the past only it is no
   better than raw history (heavy FCP 5% vs 5%) and adds false alarms: rare CPU models have no
   reference yet, and the reference of a model is itself noisy. The 2% of the prototype came
   from knowing the future.
2. **`benchmarkIndex` is the adjustment that survives going online.** It is measured on the very
   machine and job, needs no history per CPU model, and gives the best history MDE on the heavy
   page: 1% FCP, 3% LCP, 7.5% TBT steps - close to the same-job comparison. The price is false
   alarms on the light and static pages, where the metric hardly depends on CPU speed and the
   adjustment adds the noise of the score itself. The tool should therefore apply it only when
   the fitted slope is clearly non-zero (to be done).
3. **A slow creep costs about one grid step more than a step** (heavy FCP 1% → 2%, LCP 3% → 5%):
   E-Divisive finds a ramp of 2% over 2.5 days. A creep slower than the window is invisible to
   any single window; longer windows are the next thing to check.
4. **Mozilla's t ≥ 7 is tuned for a different trade-off.** It never fired without a change, but
   needs 2-10 times larger changes than E-Divisive on the same series; on 20-job windows a
   threshold of 7 is far in the tail. With 10 points on each side it is a detector of large
   regressions only.

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
Mann-Whitney + 1% + Holm), and CPD on the history of `main` adjusted for the machine - online,
with Lighthouse's `benchmarkIndex` rather than the CPU model - for the slow creep that no single
PR comparison can see.

## Caveats

- The section "What this says" below the online results refers to the prototype; where they
  differ, the online version is the one to trust (CPU model → `benchmarkIndex`).
- 18 days of history; windows overlap (36 for the SPA pages, 20 for static/SSR), so the false
  alarm rates rest on a few independent stretches.
- One change point per window; several changes per window, ramps longer than the window and
  PELT are not evaluated.
- The `benchmarkIndex` adjustment is always on in this evaluation; switching it on only when the
  fitted slope is significant should remove most of its false alarms on light pages.
