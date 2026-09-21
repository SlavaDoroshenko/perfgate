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
| Apps | four pages in three packages, production builds served on 127.0.0.1 (no network) |
| Throttling | `simulate` (Lighthouse default, Lantern model) and `devtools` (applied CPU/network throttling) |
| Schedule | 4 times a day, 01/07/13/19 UTC |

## Pages
| Label | App | URL | What it is |
|---|---|---|---|
| `demo-spa` | `apps/demo-spa` | `:4173/` | light SPA: 60 cards, almost no main-thread work after paint |
| `demo-heavy` | `apps/demo-spa` | `:4173/heavy.html` | heavy SPA: 400 cards, deterministic computation in 3 chunks after the first frame, late promo banner |
| `demo-static` | `apps/demo-static` | `:4175/` | static site: hand-written HTML/CSS article, no framework, one small script |
| `demo-ssr` | `apps/demo-ssr` | `:4174/` | server-rendered Next.js shop, 120 cards, rendered per request (`force-dynamic`), hydration on the client |

The four pages cover the range that matters for noise: a page that does almost nothing on the main
thread, one that does a lot, a document-shaped static page, and a server-rendered app whose client
cost is hydration rather than rendering. All four accept the same `?inject=type:size` regressions,
with the same semantics (`script-delay` blocks before the first paint, `long-task` after the first
frame, `layout-shift` inserts a banner after 300 ms, `lcp-delay` assigns the hero image src late).

Locally observed baselines (`devtools`, Apple M5): static FCP ~1250 ms, LCP ~1800 ms, TBT 0,
CLS 0.078; SSR FCP = LCP ~1230 ms, TBT 52-67 ms (hydration), CLS 0.078.

The light page keeps TBT and CLS at exactly zero, which makes those metrics useless for a
relative-effect analysis. The heavy page was added on 2026-09-16 for that reason: locally it
measures TBT ~340-420 ms and CLS ~0.16-0.24, both with run-to-run variation. The light page is
kept unchanged as the low-work reference point, so noise can be compared between page weights.
The static and SSR apps were added on 2026-09-21.

Data collected before 2026-09-16 comes from smoke runs (5 loads per variant) and is kept only for
sanity checks.

### Build isolation
Each page is built by its own Vite config (`vite.light.config.ts`, `vite.heavy.config.ts`) into the
same `dist`, with separate asset directories. The reason is an observed accident: when both pages
were built together, Vite extracted a shared chunk, the light page began loading one extra file,
and its `simulate` FCP/LCP jumped by ~150 ms (commit `5b4491b`) while `devtools` did not move at
all. Lantern charges a fixed penalty per additional round trip, so a purely structural change of
the bundle looked like a regression. Separate builds keep an edit of one page from moving the
other.

Consequence for analysis: the bundle differs between commits, so every run record carries `gitSha`
and cross-job statistics are grouped by build (`noise.within_between`). Mixing builds inside one
group would count the difference between bundles as measurement noise — `noise_summary.csv` reports
a `builds` column to make such mixing visible.

## Series
Each job is one experiment:
- unrecorded warm-up loads per URL: **two since 2026-09-17**, one before that (the first measured
  load of a job was the only one with non-zero TBT on an otherwise idle page). The count is stored
  in every record as `warmup`;
- `runs` loads per variant (default 20), each in a fresh Chrome process with an empty profile;
- `sequential`: all base loads, then all PR loads; `abab`: interleaved.

A/A experiments use the same URL for base and PR. A control experiment adds
`?inject=script-delay:50` to the PR URL and must be detected; it is excluded from noise statistics.

## Injected regressions
Implemented per app: `apps/demo-spa/src/inject.ts`, `apps/demo-static/public/inject.js`,
`apps/demo-ssr/app/inject.ts` + `Effects.tsx`.

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
  This is not a formality — on the heavy page the median LCP differs by ~7% between CPU models
  (see `rq1-preliminary.md`), which is larger than most regressions worth catching.
- Four pages in three packages (SPA light/heavy, static site, SSR); all are synthetic demos rather
  than production applications.
- Multiplicative shift is an idealised regression; real injected regressions are measured separately.

## Reproducing
```sh
git fetch origin data
git worktree add ../perfgate-data data
cd analysis
uv run python -m perfgate_analysis.report ../../perfgate-data/raw --out reports/rq1
```
