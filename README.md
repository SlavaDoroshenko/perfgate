# perfgate

Statistical detection of frontend performance regressions in CI.

Lab metrics (LCP, FCP, TBT, CLS) are noisy, especially on shared CI runners, so fixed
thresholds either miss real regressions or fire on noise. perfgate measures how noisy
they actually are, and compares base and PR builds with statistical tests instead of
single-run thresholds.

**Status:** measurement bench and research analysis, plus a candidate comparison MVP.
`perfgate compare` measures two running URLs or analyzes a saved experiment;
`perfgate compare-refs` builds two Git refs in isolated worktrees and compares them.
The root composite Action wraps URL comparison, artifacts and a job summary.
The Action passed hosted A/A and injected-regression checks. Local URL and Git-ref
checks also passed; see [validation results](docs/validation-2026-10-30.md).
A [trace-based CLS investigation](docs/cls-diagnosis-2026-10-30.md) documents how
mixed layout shifts can mask an injected effect in the sample median.
A [measured rare-stall pilot](docs/tail-browser-results-2026-10-30.md) found a
limitation: mean TBT increased 22–33% while the median stayed nearly unchanged,
and the current gate missed those three sparse-regression series.
The history dashboard is not built yet.

See [comparison usage and policy](docs/compare.md), [roadmap](docs/roadmap.md), and
[research completion criteria](docs/research-completion.md). The candidate gate is
not yet prospectively calibrated; no detected regression is not proof of equivalence.
The dated [18 October research snapshot](docs/research-2026-10-18.md) remains an
immutable historical report, not a count of all subsequently collected data.

## Layout

| Path | What |
|---|---|
| `packages/collector` | CLI: repeated Lighthouse runs → JSONL, one line per page load |
| `apps/demo-spa` | SPA demo: light (`/`) and heavy (`/heavy.html`) pages |
| `apps/demo-static` | static site demo (no framework) |
| `apps/demo-ssr` | server-rendered Next.js demo |
| `schema/run.schema.json` | JSON Schema of a run record, generated from zod |
| `analysis/` | Python: noise, minimum detectable effect, detection methods, run order, change points |
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
