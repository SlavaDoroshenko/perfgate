# RQ1: noise and detectability on GitHub runners (updated 2026-09-21)

**Data: 2026-09-15 … 09-20, 7180 loads in 190 jobs, no failed loads.**
GitHub-hosted `ubuntu-24.04`, Chrome 153.0.8010.47, Lighthouse 13.4.1, two pages of the demo app
served from localhost, 4 scheduled runs a day.

Unless stated otherwise, all numbers come from the **current protocol** — separate per-page builds
(app source tree `fa45447`) and two warm-up loads — which covers **15 jobs per configuration**
(8 configurations, 4800 loads).

## 0. The measurement setup is part of the measurement

Three bundle epochs and two warm-up epochs exist in the data, and both matter:

| Epoch | App source | What changed | Effect |
|---|---|---|---|
| e1 | `3325751` | light page only, single bundle | — |
| e2 | `47b3806` | both pages built together | Vite extracted a shared chunk: one extra request cost ~150 ms of `simulate` FCP/LCP, nothing under `devtools` |
| e3 | `fa45447` | separate builds per page | metric returned to the e1 level |
| warm-up | 1 → 2 loads | 2026-09-17 | first-load non-zero TBT on the light page: 2 of 28 jobs → 1 of 60 |

Ignoring the build would have reported e2 as a 6.4% cross-job noise level — an artefact ~100x
larger than the real one (0.04%). Every record therefore stores `gitSha` and `warmup`.

## 1. Same-job comparison is 4-11x more sensitive than a stored baseline

Robust CV inside one job vs CV of job medians across 15 jobs:

| Page | Throttling | Metric | within job | between jobs | ratio |
|---|---|---|---|---|---|
| heavy | devtools | FCP | 0.41% | 2.11% | 5.2 |
| heavy | devtools | LCP | 0.49% | 3.70% | 7.6 |
| heavy | devtools | TBT | 1.77% | 13.6% | 7.7 |
| heavy | simulate | TBT | 1.50% | 16.8% | 11.2 |
| light | devtools | FCP | 0.34% | 1.59% | 4.6 |
| light | devtools | LCP | 0.27% | 1.07% | 3.9 |

For FCP and LCP under `simulate` the ratio falls below 1 (0.4-0.5): modelled metrics barely react
to the machine. TBT is the exception — it stays 11x worse across jobs even under `simulate`,
because Lantern scales real CPU time rather than replacing it.

## 2. Cross-job noise is a hardware lottery, and it grows with page weight

Medians by runner CPU, `devtools` (current protocol):

| CPU | heavy FCP | heavy LCP | heavy TBT | light LCP |
|---|---|---|---|---|
| AMD EPYC 9V45 | 1674 ms | 2198 ms | 281 ms | 2191 ms |
| Intel Xeon 6973P-C | 1714 ms | 2254 ms | 328 ms | 2201 ms |
| AMD EPYC 9V74 | 1751 ms | 2328 ms | 376 ms | 2253 ms |
| Intel Xeon 8573C | 1738 ms | 2350 ms | 411 ms | 2233 ms |
| Intel Xeon 8370C | 1781 ms | 2455 ms | 459 ms | 2245 ms |
| AMD EPYC 7763 | 1791 ms | 2483 ms | 487 ms | 2247 ms |

Spread across CPU models: heavy page LCP 13%, TBT 73%; light page LCP 2.8%. Half of all jobs land
on EPYC 7763, the rest are spread over five other models — a PR compared against a baseline from a
previous job is, half the time, compared against different hardware.

## 3. Sequential series raise more false alarms — but only where the machine is real

Share of A/A jobs (no difference exists by construction) where two-sided Mann-Whitney reported a
difference at α=0.05, pooled over FCP, LCP and Speed Index, 95% Wilson intervals:

| Subset | `abab` | `sequential` | Fisher p |
|---|---|---|---|
| all | 3.9% [1.9, 7.8] | 8.3% [5.1, 13.3] | 0.122 |
| `devtools` only | 5.6% [2.4, 12.4] | 16.7% [10.4, 25.7] | **0.031** |
| `simulate` only | 2.2% [0.6, 7.7] | 0.0% [0.0, 4.1] | 0.497 |

`abab` sits on the nominal 5% everywhere. `sequential` triples the false alarm rate under
`devtools`, where loads really execute and the machine can drift during the series; under
`simulate` the effect vanishes, which is consistent with Lantern modelling the machine away.

Two honest caveats:

- **An earlier estimate on two days of data (20.8% vs 4.2%) did not survive more data.** With 15
  jobs per configuration the gap is three-fold, not five-fold, and pooled over both throttling
  modes it is not significant. This is the small-sample lesson, and it is why the collection runs
  for weeks rather than days.
- **The false alarms are statistically significant but practically tiny**: every one of them shifts
  the median by between -0.58% and +0.71%. With n=20 and a within-job CV of ~0.3% the test resolves
  differences of 0.2%. Pairing significance with a minimum effect size (e.g. 1%) removes all of
  them. There is no systematic direction: median shift per job is within ±0.06% in every
  configuration, so this is job-specific drift, not a bias of the design.

## 4. MDE (resampling of real A/A loads, Mann-Whitney, power 0.8)

| Page | Throttling | Metric | n=5 | n=10 | n=20 |
|---|---|---|---|---|---|
| light | both | FCP/LCP | 1% | 1% | 1% |
| heavy | devtools | FCP | 1% | 1% | 1% |
| heavy | devtools | LCP | 3-5% | 1% | 1% |
| heavy | both | TBT | 5-7.5% | 3-5% | 2-3% |

The same procedure at δ=0 yields a median 0.044-0.049 against a nominal 0.05, so it is calibrated.
1% is the lowest grid point, so "1%" means "1% or better"; a finer grid is needed to resolve it.

## 5. The control regression is detected, and shows where methods will break

The control job injects `script-delay:50` into the PR url. Over 15 jobs:

| Metric | Detected | Median effect | Range |
|---|---|---|---|
| FCP | 15/15 | +2.85% | +2.28% … +3.15% |
| SI | 14/15 | +1.37% | +0.16% … +2.09% |
| LCP | 13/15 | +1.94% | -4.99% … +2.66% |

The -4.99% job is instructive: LCP on the heavy page is multimodal (a job contains 3 distinct LCP
levels on median, up to 5), and in that job the base half happened to sit on a high level while the
PR half sat on a low one. A single-number comparison inverted. Multimodal metrics are exactly where
the choice of method matters, and this belongs in RQ2.

## Open items
- CLS on the heavy page is non-zero but constant (0.154) — needs absolute effects, not relative.
- Only `ubuntu-24.04`, one app family, injected effects are pure multiplicative shifts.
- The 1% grid floor hides how much better than 1% FCP/LCP detection really is.

## Reproducing
```sh
git fetch origin data && git worktree add ../perfgate-data data
cd analysis
uv run python -m perfgate_analysis.report ../../perfgate-data/raw --out reports/rq1
```
