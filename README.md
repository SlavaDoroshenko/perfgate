# perfgate

Statistical detection of frontend performance regressions in CI.

Lab metrics (LCP, FCP, TBT, CLS) are noisy, especially on shared CI runners, so fixed
thresholds either miss real regressions or fire on noise. perfgate measures how noisy
they actually are, and compares base and PR builds with statistical tests instead of
single-run thresholds.

**Status:** early stage — measurement bench for noise and minimum detectable effect.

## Layout

| Path | What |
|---|---|
| `packages/collector` | CLI: repeated Lighthouse runs → JSONL, one line per page load |
| `apps/demo-spa` | demo app, light (`/`) and heavy (`/heavy.html`) pages, with injectable regressions (`?inject=type:size`) |
| `schema/run.schema.json` | JSON Schema of a run record, generated from zod |
| `analysis/` | Python: noise, minimum detectable effect, false alarms |
| `.github/workflows/noise.yml` | scheduled A/A measurements on GitHub runners → `data` branch |
| `docs/protocol.md` | experiment protocol |

## Analysis

```sh
git fetch origin data && git worktree add ../perfgate-data data
cd analysis
uv run python -m perfgate_analysis.report ../../perfgate-data/raw --out reports/rq1
```

Writes CSV tables (noise summary, within- vs between-job noise, power curves, MDE,
A/A false alarms) and PNG figures.

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
