# Measurement protocol (RQ1: noise and MDE)

## Questions
- **RQ1.** How noisy are lab metrics (FCP, LCP, TBT, CLS, Speed Index) on GitHub-hosted
  runners, and what is the smallest regression detectable with 5 / 10 / 20 loads per variant?
- RQ2 (later). Which detection method gives the best false alarm / miss trade-off at a fixed CI budget?
- RQ3 (later). Does interleaving base and PR loads in one job (ABAB) reduce noise compared with sequential series?

## Setup
| Item | Value |
|---|---|
| Runner | GitHub-hosted `ubuntu-24.04` (image version recorded per run) |
| Browser | Chrome for Testing, pinned in `.github/workflows/noise.yml` |
| Lighthouse | pinned by `pnpm-lock.yaml`, performance category only, default mobile config |
| Node | 22 |
| Apps | two pages of `apps/demo-spa`, production build served by `vite preview` on 127.0.0.1 (no network) |
| Throttling | `simulate` (Lighthouse default, Lantern model) and `devtools` (applied CPU/network throttling) |
| Schedule | 4 times a day, 01/07/13/19 UTC |

## Pages
| Label | URL | What it is |
|---|---|---|
| `demo-spa` | `/` | light page: 60 cards, almost no main-thread work after paint |
| `demo-heavy` | `/heavy.html` | heavy page: 400 cards, deterministic computation in 3 chunks after the first frame, late promo banner |

The light page keeps TBT and CLS at exactly zero, which makes those metrics useless for a
relative-effect analysis. The heavy page was added on 2026-09-16 for that reason: locally it
measures TBT ≈ 340–420 ms and CLS ≈ 0.16–0.24, both with run-to-run variation. The light page is
kept unchanged as the low-work reference point, so noise can be compared between page weights.

Data collected before 2026-09-16 comes from smoke runs (5 loads per variant) and is kept only for
sanity checks.

## Series
Each job is one experiment:
- one unrecorded warm-up load per URL;
- `runs` loads per variant (default 20), each in a fresh Chrome process with an empty profile;
- `sequential`: all base loads, then all PR loads; `abab`: interleaved.

A/A experiments use the same URL for base and PR. A control experiment adds
`?inject=script-delay:50` to the PR URL and must be detected; it is excluded from noise statistics.

## Injected regressions (`apps/demo-spa/src/inject.ts`)
| Param | Effect | Main metric |
|---|---|---|
| `script-delay:<ms>` | blocking JS before first render | FCP, LCP |
| `long-task:<ms>` | blocking JS right after the first frame | TBT |
| `layout-shift:<px>` | banner inserted above content after 300 ms | CLS |
| `lcp-delay:<ms>` | hero image src assigned late | LCP |

Observed on a local smoke test (Apple M5, 2 pairs per injection):

| Injection | `simulate` | `devtools` |
|---|---|---|
| `script-delay:100` | FCP unchanged, TBT +360 ms | FCP +~110 ms, LCP +~100 ms |
| `long-task:200` | TBT +750 ms | — |
| `layout-shift:120` | CLS 0 → 0.146 | — |
| `lcp-delay:800` | **no change** | LCP +~840 ms |

`simulate` does not replay the page: Lantern re-estimates metrics from the trace with a 4× CPU
multiplier and ignores timers, so some real regressions are invisible or move to another metric.
This is itself a finding for RQ2; the control experiment therefore runs with `devtools`.
LCP under `simulate` is also bimodal on this page (~1350 / ~1500 ms), i.e. the noise is discrete.

## Analysis (`analysis/`)
- Noise: median, IQR, CV, robust CV (1.4826·MAD/median), share of zeros; within-job robust CV vs
  CV of job medians across days (same-job comparison vs stored baseline).
- MDE: resampling of real A/A loads inside each job, multiplicative shift δ applied to the PR
  subsample, one-sided Mann–Whitney U, α = 0.05; MDE = smallest δ with power ≥ 0.8.
  The rejection rate at δ = 0 is the false alarm rate.
- Real-label A/A false alarms: two-sided MWU of base vs PR within each job; keeps run order, so
  drift in sequential series is visible.
- Metrics with a zero median (typically CLS, often TBT) have no relative MDE; they are reported
  via share of zeros and handled with absolute effects in RQ2.

## Threats to validity
- Lab metrics only; no field data, no INP.
- Runner hardware and images change over time: image version and CPU model are stored per load.
- One small SPA in this iteration; SSR and static apps are added in later iterations.
- Multiplicative shift is an idealised regression; real injected regressions are measured separately.

## Reproducing
```sh
git fetch origin data
git worktree add ../perfgate-data data
cd analysis
uv run python -m perfgate_analysis.report ../../perfgate-data/raw --out reports/rq1
```
