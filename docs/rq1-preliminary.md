# RQ1: noise and detectability on GitHub runners (updated 2026-09-27)

**Data: 2026-09-17 … 09-27, current protocol only: 21,530 loads in 551 jobs, no failed loads.**
GitHub-hosted `ubuntu-24.04`, Chrome 153.0.8010.47, Lighthouse 13.4.1, four demo pages served
from localhost, 4 scheduled runs a day. 40 A/A jobs per configuration for the two SPA pages,
24 for the static and server-rendered pages (added on 2026-09-21).

"Current protocol" = separate per-page builds and two warm-up loads. The app build is identified
by the git tree hash of the app package (`fa45447b5c39` for both SPA pages, `12817a1ef4f9` static,
`467c2a6f9f6c` SSR). Records written before `--app-build` existed carry only the commit; the
loader resolves the commit to the same tree hash, so commits that did not touch the app share an
epoch (`load.app_epoch`). The first version of this note grouped by commit and therefore saw
only 15 jobs per configuration.

Reproduce:

```sh
cd analysis
uv run python -m perfgate_analysis.report ../../perfgate-data/raw --out reports/rq1 \
  --warmup 2 --gha-only --epoch fa45447b5c39 --epoch 467c2a6f9f6c --epoch 12817a1ef4f9
```

## 0. The measurement setup is part of the measurement

Three bundle epochs and two warm-up epochs exist in the data, and both matter:

| Epoch | App source | What changed | Effect |
|---|---|---|---|
| e1 | `3325751` | light page only, single bundle | — |
| e2 | `47b3806` | both pages built together | Vite extracted a shared chunk: one extra request cost ~150 ms of `simulate` FCP/LCP, nothing under `devtools` |
| e3 | `fa45447` | separate builds per page | metric returned to the e1 level |
| warm-up | 1 → 2 loads | 2026-09-17 | first-load non-zero TBT on the light page: 2 of 28 jobs → 1 of 60 |

Ignoring the build would have reported e2 as a 6.4% cross-job noise level — an artefact ~100x
larger than the real one (0.04%). Every record therefore stores `gitSha`, `appBuild` and `warmup`.

## 1. Same-job comparison is 2-10x more sensitive than a stored baseline

Robust CV inside one job vs CV of job medians across jobs (`devtools`, `abab`):

| Page | Metric | within job | between jobs | ratio |
|---|---|---|---|---|
| heavy | FCP | 0.45% | 2.01% | 4.4 |
| heavy | LCP | 0.63% | 3.91% | 6.2 |
| heavy | TBT | 1.53% | 14.4% | 9.4 |
| light | FCP | 0.35% | 1.65% | 4.7 |
| light | LCP | 0.27% | 1.13% | 4.1 |
| SSR | FCP / LCP | 0.41% | 1.01% | 2.5 |
| SSR | TBT | 4.15% | 24.3% | 5.8 |
| static | FCP | 0.39% | 0.66% | 1.7 |

Under `simulate` the ratio for FCP/LCP of the SPA and static pages falls below 1 (0.3-0.5):
modelled metrics barely react to the machine. TBT is the exception — 7-11x worse across jobs even under `simulate`, because
Lantern scales real CPU time rather than replacing it. The static page, which does almost no
work on the main thread, is the one where a stored baseline costs least.

## 2. Cross-job noise is a hardware lottery, and it grows with page weight

Medians by runner CPU, `devtools`, all A/A loads:

| CPU | jobs | heavy FCP | heavy LCP | heavy TBT | light LCP |
|---|---|---|---|---|---|
| AMD EPYC 9V45 | 12 | 1685 ms | 2210 ms | 291 ms | 2190 ms |
| Intel Xeon 6973P-C | 6 | 1713 ms | 2250 ms | 325 ms | 2201 ms |
| AMD EPYC 9V74 | 30 | 1782 ms | 2315 ms | 430 ms | 2248 ms |
| Intel Xeon 8573C | 14 | 1747 ms | 2372 ms | 422 ms | 2234 ms |
| Intel Xeon 8370C | 9 | 1782 ms | 2456 ms | 459 ms | 2242 ms |
| AMD EPYC 7763 | 88 | 1791 ms | 2481 ms | 485 ms | 2248 ms |

Spread across CPU models: heavy page FCP 6%, LCP 12%, TBT 67%; light page LCP 2.6%. Over all
A/A jobs, 52% landed on EPYC 7763, 24% on EPYC 9V74 and the rest on four other models - a PR
compared against a baseline from a previous job is, about half the time, compared against
different hardware. `history-cpd.md` shows what this costs a history-based detector and how much
of it a per-CPU adjustment recovers.

## 3. Interleaving matters - see `rq3.md`

With 40 jobs per configuration the earlier hint is now clear: a sequential series (all base
loads, then all PR loads) raises 3-5 times more A/A false alarms than an interleaved one, under
both throttling modes. Details, job-level (PR-level) rates and the TBT case are in `rq3.md`.

## 4. MDE (resampling of real A/A loads, Mann-Whitney, power 0.8, `abab`)

The grid now starts at 0.25% (0.25 / 0.5 / 0.75 / 1 / 1.5 / 2 / 3 / 5 / 7.5 / 10 ... %), so the
old "1% or better" floor is resolved:

| Page | Throttling | Metric | n=5 | n=10 | n=20 |
|---|---|---|---|---|---|
| heavy | devtools | FCP | 1.5% | 0.75% | 0.5% |
| heavy | devtools | LCP | 5% | 1.5% | 0.75% |
| heavy | devtools | TBT | 5% | 3% | 2% |
| heavy | simulate | FCP / LCP | 0.5-0.75% | ≤0.25% | ≤0.25% |
| heavy | simulate | TBT | 7.5% | 3% | 2% |
| light | devtools | FCP / LCP | 0.75-1% | 0.5-0.75% | 0.5% |
| light | simulate | FCP / LCP | 1% | ≤0.25% | ≤0.25% |
| SSR | devtools | FCP / LCP | 1% | 0.75% | 0.5% |
| SSR | devtools | TBT | 10% | 7.5% | 5% |
| SSR | simulate | LCP | 7.5% | 1.5% | 0.5% |
| static | devtools | FCP / LCP | 1% | 0.5-0.75% | 0.5% |
| static | simulate | FCP | ≤0.25% | ≤0.25% | ≤0.25% |

Calibration: the same procedure at δ=0 yields 3.9-4.1% on average (max 6.4%) against a nominal
5%. "≤0.25%" is the lowest grid point; under `simulate` FCP/LCP of the SPA and static pages are almost
deterministic within a job (within-job CV 0.06-0.09%), so going lower measures Lantern, not the page.

Two practical readings:
- **Ten interleaved loads resolve 0.5-1.5% on FCP/LCP under `devtools`** on every page. That is
  already below the effect sizes that matter to users; the limiting factor is not the test.
- **TBT needs 3-10% at n=10.** It is the metric where the number of loads matters most, and the
  server-rendered page (hydration cost of 50-70 ms) is the hardest case.

## 5. The control regression is detected, and shows where methods will break

The control job injects `script-delay:50` into the PR url of the heavy page (`devtools`, `abab`).
Over 40 jobs, one-sided Mann-Whitney at α=0.05, "gate" = significant and at least +1%:

| Metric | Detected | With the 1% gate | Median effect | Range |
|---|---|---|---|---|
| FCP | 40/40 | 40/40 | +2.88% | +2.28% … +3.59% |
| SI | 33/40 | 27/40 | +1.34% | -0.36% … +2.81% |
| LCP | 29/40 | 27/40 | +1.76% | -5.86% … +2.71% |
| TBT | 4/40 | 2/40 | -0.06% | -1.45% … +1.89% |

LCP on the heavy page is multimodal (a job contains 3 distinct LCP levels on median, up to 5):
in the worst job the base half sat on a high level and the PR half on a low one and the
comparison inverted (-5.9%). The regression is injected before the first paint, so TBT is not
supposed to move - 4/40 detections are the false alarm rate of a one-sided test, as expected.

## Open items
- CLS on the heavy page is non-zero but constant (0.154) — needs absolute effects, not relative
  (the resampling "detects" any relative shift of a constant).
- Only `ubuntu-24.04`, four demo pages, injected effects are pure multiplicative shifts.
- Regressions of other types and sizes (long task → TBT, heavy image → LCP, layout shift → CLS)
  are not yet collected in CI.
