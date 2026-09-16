# RQ1, preliminary observations (2026-09-16)

**Status: one day of data — 3 to 5 jobs per configuration. Directional, not conclusive.**
Everything below is measured on GitHub-hosted `ubuntu-24.04`, Chrome 153.0.8010.47,
Lighthouse 13.4.1, two pages of the demo app served from localhost.
All numbers are grouped per build (commit), see "Build isolation" in `protocol.md`.

## 1. Same-job noise is small; cross-job noise is 4-7x larger

Robust CV (1.4826·MAD/median) inside one job, against CV of job medians across jobs of the
same build:

| Page | Throttling | Metric | within job | between jobs | ratio |
|---|---|---|---|---|---|
| light | devtools | LCP | 0.24% | 0.95% | 4.0 |
| light | devtools | FCP | 0.38% | 1.32% | 3.5 |
| heavy | devtools | LCP | 0.66% | 4.52% | 6.8 |
| heavy | devtools | FCP | 0.46% | 1.91% | 4.2 |
| heavy | devtools | TBT | 1.40% | 17.85% | 12.8 |

Practical reading: comparing base and PR **inside one job** is 4 to 13 times more sensitive
than comparing a PR against a baseline stored from an earlier job. The heavier the page, the
bigger the gap.

## 2. The cross-job noise is largely a hardware lottery

Median metrics of the heavy page, `devtools`, by runner CPU:

| CPU | FCP | LCP | TBT |
|---|---|---|---|
| AMD EPYC 9V74 | 1757 ms | 2330 ms | 378 ms |
| AMD EPYC 7763 | 1804 ms | 2493 ms | 485 ms |

The same lottery barely touches the light page (LCP 2250 vs 2247 ms): a page that does almost
no work on the main thread is nearly insensitive to which machine it lands on. Sensitivity to
the runner grows with the amount of JavaScript work, i.e. exactly where regressions matter.

## 3. `simulate` is stable but blind

Under `simulate` the between-job CV of FCP/LCP collapses to 0.02-0.04%: Lantern re-estimates
metrics from a model, so the hardware lottery disappears. The same modelling also hides real
regressions — a delayed LCP image (`lcp-delay:800`) produces no change at all under `simulate`,
while `devtools` shows +840 ms (see `protocol.md`).

So the choice of throttling is not a detail: `simulate` buys stability at the price of
sensitivity. Quantifying that trade-off belongs to RQ2.

## 4. Sequential series produce false alarms, interleaved ones do not

Share of A/A jobs (no difference exists by construction) where Mann-Whitney reported a
significant difference between "base" and "pr" at α=0.05:

| Page | Throttling | Mode | FCP | LCP | SI |
|---|---|---|---|---|---|
| light | devtools | abab | 0/5 | 0/5 | 0/5 |
| light | devtools | sequential | 1/5 | 2/5 | 1/5 |
| light | simulate | abab | 0/5 | 0/5 | 0/5 |
| light | simulate | sequential | 2/5 | 1/5 | 2/5 |
| heavy | devtools | abab | 0/3 | 0/3 | 0/3 |
| heavy | devtools | sequential | 1/3 | 1/3 | 1/3 |

This is the RQ3 hypothesis: when all base loads run first and all PR loads second, any drift of
the machine during the series is attributed to the PR. Interleaving spreads it over both
variants. The sample is far too small for a rate, but the direction is consistent across pages
and throttling modes, and the magnitude (20-40% vs 0%) is large.

## 5. MDE (resampling of real A/A loads, Mann-Whitney, power 0.8)

| Page | Throttling | Metric | n=5 | n=10 | n=20 |
|---|---|---|---|---|---|
| light | devtools | FCP/LCP | 1-2% | 1% | 1% |
| heavy | devtools | LCP | 10% | 7.5% | 1% |
| heavy | devtools | TBT | 3% | 2% | 2% |
| heavy | simulate | TBT | 7.5% | 3% | 2% |

The false alarm rate of the same procedure at δ=0 stays within 0.034-0.060 against a nominal
0.05, so the resampling is calibrated.

Caveat: 1% is the lowest point of the delta grid, so "1%" means "1% or better" and needs a
finer grid once more data is in.

## Threats specific to these numbers
- 3-5 jobs per configuration, one day, one app family.
- The injected effect is a multiplicative shift of every value; real regressions change the
  shape of the distribution too.
- CLS is non-zero on the heavy page but almost constant (0.154), so a relative MDE for it is
  meaningless; it needs absolute effects.
- TBT of the light page is zero in 557 of 560 loads; the three non-zero values all occur in the
  first measured load of a job, which suggests one warm-up load is not always enough.

## Next
Keep collecting until there are tens of jobs per configuration, then re-run
`python -m perfgate_analysis.report` and turn sections 1, 3 and 4 into proper rates with
confidence intervals.
