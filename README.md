# perfgate

Statistical detection of frontend performance regressions in CI.

Lab metrics (LCP, FCP, TBT, CLS) are noisy, especially on shared CI runners, so fixed
thresholds either miss real regressions or fire on noise. perfgate measures how noisy
they actually are, and compares base and PR builds with statistical tests instead of
single-run thresholds.

Each check loads the base and the changed version alternately, 20 times each, on the
same runner in the same job, and flags FCP, LCP, TBT or CLS only when a one-sided
Mann–Whitney test (Holm-corrected over all pages and metrics) is significant and the
median moved by more than a small margin (1% FCP/LCP, max(5%, 5 ms) TBT, 0.005 CLS).

## Results

The policy was frozen on 30 October 2026 together with the hashes of its sources,
targets and sample sizes, and then evaluated only on data collected afterwards
([confirmatory report](docs/prospective-confirmatory-2026-11-11.md),
[before/after](docs/before-after-2026-11-11.md)). On the same 118,120 loads of GitHub
`ubuntu-24.04` runners:

| | 5% threshold, 1 load | 5% threshold, median of 20 | perfgate |
|---|---:|---:|---:|
| False alarms, unchanged four-page check | 77/200 | 17/200 | **0/200** |
| FCP +5% detected | 60/100 | 70/100 | **100/100** |
| FCP / LCP +2% detected | 0–1/37 | 0/37 | **37/37** |
| TBT +10% detected | 96/100 | 99/100 | 98/100 |
| CLS +10% / +25% detected | 83 / 83 | 91 / 93 | 87 / 85 |

The false-alarm target (Wilson upper bound ≤ 5%) and the detection targets for FCP,
LCP and TBT (lower bound ≥ 80%) are met. The CLS target is not: the demo page itself
has unstable CLS on newer runner CPUs; a predeclared follow-up on a CLS-stable page is
in [extensions-2026-11-17](docs/protocols/extensions-2026-11-17.md). Known blind
spots: TBT changes below the 5% margin, and rare long tasks that move the mean but
not the median ([rare-stall pilot](docs/tail-browser-results-2026-10-30.md)).
Change-point detection on the history of `main` is several times less sensitive on
shared runners and stays advisory ([history-cpd.md](docs/history-cpd.md)).

On a real application (twelve consecutive commits of Phanpy, each measured twice),
two FCP regressions of 2.5–3.3% were found in both repetitions; a 5% threshold sees
neither ([external pilot](docs/external-pilot-2026-11-06.md)).

A check costs about 13 min of runner time per page with 20 loads, or 7 min with
the secondary 10-load setting ([machine time](docs/machine-time-2026-11-17.md)).

## What you get

- `perfgate compare` (two running URLs) and `perfgate compare-refs` (builds two Git
  refs in isolated worktrees): JSON and Markdown reports, exit code = verdict.
- A GitHub Action ([action.yml](action.yml)) and a sticky pull request comment from a
  separate trusted workflow ([PR comments](docs/pr-comments.md)), including which
  built assets changed size.
- A GitLab CI template with a merge request note ([GitLab](docs/gitlab.md)).
- A Docker image with the pinned Chrome, installable offline ([Docker](docs/docker.md)).
- A main-branch history on a dedicated branch with a static dashboard and advisory
  change-point warnings ([history](docs/history.md)); perfgate's own:
  [slavadoroshenko.github.io/perfgate](https://slavadoroshenko.github.io/perfgate/).

Start with the [user guide](docs/user-guide.md). Statistical policy:
[compare.md](docs/compare.md) (frozen text of the evaluated candidate). No detected
regression is not proof of equivalence.

Research documents: [roadmap](docs/roadmap.md), [completion criteria](docs/research-completion.md),
[18 October snapshot](docs/research-2026-10-18.md) (immutable historical report).

## Layout

| Path | What |
|---|---|
| `packages/collector` | CLI: repeated Lighthouse runs → JSONL, one line per page load |
| `apps/demo-spa` | SPA demo: light (`/`) and heavy (`/heavy.html`) pages |
| `apps/demo-static` | static site demo (no framework) |
| `apps/demo-ssr` | server-rendered Next.js demo |
| `schema/run.schema.json` | JSON Schema of a run record, generated from zod |
| `analysis/` | Python: noise, minimum detectable effect, detection methods, run order, change points |
| `action.yml`, `comment/action.yml` | GitHub Actions: measure two URLs; publish the PR comment |
| `scripts/comment/` | comment renderer and GitHub/GitLab publisher (untrusted-input safe) |
| `history/action.yml`, `scripts/history/` | main-branch history records and static dashboard |
| `Dockerfile`, `docker/` | measurement image with pinned Chrome for Testing |
| `ci/gitlab/` | GitLab CI include template |
| `examples/` | compare-refs config and external-project GitHub workflows |
| `.github/workflows/noise.yml` | scheduled A/A measurements on GitHub runners → `data` branch |
| `docs/protocol.md` | experiment protocol |
| `docs/rq1-preliminary.md` | measured noise, MDE and false alarm rates |
| `docs/rq2-methods.md` | comparison of eleven detection rules |
| `docs/rq3.md` | interleaved vs sequential series: false alarms per comparison and per PR |
| `docs/power.md` | detection rate on real jobs with regressions of known kind and size |
| `docs/history-cpd.md` | change point detection on the main-branch history, raw vs CPU-adjusted |

## Analysis

```sh
git fetch origin data && git worktree add ../perfgate-data data
cd analysis
uv run python -m perfgate_analysis.report ../../perfgate-data/raw --out reports/rq1
```

Writes CSV tables (noise summary, within- vs between-job noise, power curves, MDE,
A/A false alarms) and PNG figures. Restrict to one protocol with `--warmup 2 --gha-only` and
`--epoch <app build>`; the other reports (`report_rq2`, `rq3`, `power`, `history`) take the same filters.

## Quick start

```sh
pnpm install
pnpm test

# 10 interleaved base/pr loads with simulated throttling
pnpm perfgate collect \
  --url http://localhost:4173/ \
  --pr-url "http://localhost:4173/?inject=script-delay:200" \
  --runs 10 --mode abab --throttling simulate \
  --out results/runs.jsonl
```

Modes:
- `sequential` — all base loads, then all PR loads;
- `abab` — interleaved, so slow drift of the machine affects both variants equally.

Every load uses a fresh Chrome profile, and each series starts with unrecorded warm-up loads
(`--warmup`, default 2). Failed loads are recorded with `error` set, so failure rate stays
visible in the data.

Regenerate the JSON Schema after changing `packages/collector/src/schema.ts`:

```sh
pnpm schema
```

## License

MIT
