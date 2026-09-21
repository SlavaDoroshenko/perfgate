# RQ2: which detection rule to use (first results, 2026-09-21)

Ten rules compared on **identical** comparisons: every method sees the same resampled draws of
real A/A loads from the same jobs, so the differences come from the rule, not from the draw.
Data: current protocol (separate per-page builds, two warm-up loads), 15 jobs per configuration,
four demo pages.

Code: `analysis/perfgate_analysis/methods.py` (rules), `evaluate.py` (harness),
`report_rq2.py` (CLI). Reproduce with

```sh
cd analysis
uv run python -m perfgate_analysis.report_rq2 ../../perfgate-data/raw --out reports/rq2 --warmup 2
```

## The rules

| Rule | Where it comes from | Loads per variant |
|---|---|---|
| `single-run >2% / >5%` | one load each side against a margin — the naive CI check | 1 |
| `median >2% / >5%` | median of n loads against a margin — Lighthouse CI budgets, CodSpeed's 2% | n |
| `Welch t` | one-sided t-test — the shape of Mozilla's alerting | n |
| `Mann-Whitney` | one-sided rank test — what sitespeed.io reports | n |
| `MWU & >1% / >2%` | significance **and** a minimum effect size | n |
| `bootstrap CI` | percentile CI of the ratio of medians, optionally with a minimum effect | n |

## Resampled comparison, 10 loads per variant

False alarm rate at δ=0 and the smallest detected regression at power 0.8 (median over
configurations):

| Metric | Rule | Loads | False alarms | MDE |
|---|---|---|---|---|
| FCP | Mann-Whitney | 10 | 4.8% | **0.5%** |
| FCP | bootstrap CI | 10 | 4.5% | 0.75% |
| FCP | Welch t | 10 | 3.7% | 1.0% |
| FCP | MWU & >1% | 10 | **0.0%** | 2.0% |
| FCP | median >2% | 10 | 0.0% | 3.0% |
| FCP | single-run >2% | **1** | 3.3% | 3.0% |
| FCP | median >5% | 10 | 0.0% | 7.5% |
| TBT | Mann-Whitney | 10 | 4.1% | 3.0% |
| TBT | median >2% | 10 | 4.3% | 3.0% |
| TBT | single-run >2% | **1** | **21.3%** | 5.0% |
| TBT | bootstrap CI & >1% | 10 | 0.0% | 5.0% |

Three things stand out.

1. **On stable metrics the tests are an order of magnitude more sensitive than budgets.** With ten
   loads, Mann-Whitney resolves 0.5% on FCP and LCP; a 2% budget needs a 3% regression, a 5% budget
   needs 7.5%. Ten loads cost about two minutes of CI time on this page.
2. **The naive single-load check is not catastrophic on stable metrics** (3.3% false alarms, MDE
   3%, one load) **and is catastrophic on noisy ones**: 21.3% false alarms on TBT. A team whose
   metric is stable can get away with it; a team measuring main-thread work cannot.
3. **The minimum effect size is what makes a test usable as a gate.** Mann-Whitney alone fires on
   real but meaningless 0.5% differences; adding "and at least 1%" drops false alarms to zero and
   still resolves 2%.

## The same rules on real jobs

Applied to the actual base/PR labels of each job, keeping the run order (120 A/A jobs for FCP/LCP,
60 for TBT, 15 control jobs with an injected `script-delay:50` worth about +2.9% FCP):

| Rule | A/A false alarms (FCP / LCP / TBT) | Control detected (FCP / LCP / TBT) |
|---|---|---|
| Mann-Whitney | 3.3 / 3.3 / 3.3 % | 100 / 87 / 7 % |
| Welch t | 3.3 / 2.5 / 1.7 % | 100 / 53 / 7 % |
| bootstrap CI | 2.5 / 3.3 / 5.0 % | 100 / 73 / 0 % |
| **MWU & >1%** | **0 / 0 / 3.3 %** | **100 / 87 / 0 %** |
| median >2% | 0 / 0 / 1.7 % | 100 / 40 / 0 % |
| median >5% | 0 / 0 / 0 % | **0 / 0 / 0 %** |
| single-run >2% | 1.7 / 3.3 / **20.0** % | 100 / 47 / 20 % |

The 5% budget — a common default — misses the real regression entirely on every metric. The 2%
budget catches it on FCP but only 40% of the time on LCP, where the tests reach 73-87%.

## Current recommendation

For a page like these, on a shared GitHub runner:

- **10 loads per variant, interleaved (`abab`), Mann-Whitney plus a minimum effect of 1%.**
  Zero false alarms in 120 A/A jobs, catches the control regression on FCP in all 15 jobs.
- Report the bootstrap confidence interval of the effect next to the verdict: "LCP +2.4%
  [+1.1%, +3.6%]" is actionable, "failed" is not.
- Do not use a single load per variant if the metric involves main-thread work.
- Budgets are not a replacement for a comparison; a 5% budget is a smoke alarm in another building.

## Caveats
- The resampled effect is a pure multiplicative shift; real regressions also change the shape of
  the distribution. The control jobs are the check against that, and there is only one injection
  type so far.
- TBT statistics come from two pages only (heavy SPA and SSR); the light and static pages have TBT
  at exactly zero.
- Everything is measured on `ubuntu-24.04` with these four demo pages.
