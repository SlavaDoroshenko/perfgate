# Main-branch history and dashboard

The pull request gate compares two versions in one job. It cannot see a slow creep
(many changes below the margin) or a regression merged without the check. perfgate
therefore keeps a history of comparisons on the main branch in the user's own
repository and renders it as one static HTML page. The research behind the
change-point check is in [history-cpd.md](history-cpd.md).

## What is measured

After every push to `main`, the pushed commit is compared with the previous state of
the branch (`github.event.before`; the parent when the branch is new) using the same
root action and candidate policy as pull requests. One comparison gives two things:

- a **per-push verdict** with effects against the previous state, which catches a
  regression that reached `main` without a pull request check;
- a **history point**: the median of the measured commit's 20 loads, the series
  examined in [history-cpd.md](history-cpd.md) (one median of a job's loads per point).

Comparing against the previous state rather than measuring the commit alone (A/A)
costs a second build, but the same-job comparison is 3-10 times more sensitive than
change-point detection on raw runner history, so it remains the primary signal; the
history adds the creep that no single comparison sees. A repository that cannot
afford two builds can serve the same build on both ports: the verdict then becomes an
A/A control and only the history point is informative.

## Storage

Records are appended to `history.jsonl` on an orphan branch (`perfgate-history` by
default), the pattern this repository uses for its `data` branch. No external
service is involved. One JSON line per measured page:

| Field | Contents |
|---|---|
| `commit`, `base_commit`, `ref` | measured commit and the commit it was compared with |
| `measured_at` | time of the first measured load (UTC) |
| `page`, `status` | page label; `regression`, `no_regression_detected`, `invalid` or `error` |
| `policy`, `runs_per_variant` | decision policy and loads per version |
| `metrics.<fcp\|lcp\|tbt\|cls>` | `base_median`, `pr_median`, `absolute_effect`, `relative_effect`, `p`, `regression` |
| `env` | `cpu_model`, `chrome_version`, `chrome_binary_version`, `lighthouse_version`, `runner_image`, median `benchmark_index` of the measured commit's loads, `throttling`, `mode` |
| `run_url`, `commit_url`, `issues` | links and up to five measurement issues |

Invalid and failed comparisons are recorded too, so gaps stay visible. When a
workflow run is re-run, the dashboard uses the first valid attempt of that run:
re-running until a result looks better would bias the history. Separate runs of the
same commit (for example scheduled A/A jobs) are separate points.

## Dashboard

`index.html` is one self-contained file: inline CSS and SVG, no scripts, no external
requests. It opens from disk and can be deployed to GitHub Pages. Per page and metric:

- the history value over time, coloured by runner CPU model (the hardware lottery of
  [rq1-preliminary.md](rq1-preliminary.md) is directly visible);
- a triangle where the per-push verdict was a regression for that metric, a cross at
  the bottom for an invalid or failed comparison;
- dotted vertical lines at Chrome version changes;
- the advisory change-point result, with a dashed line at the suspected change;
- a table of the latest measurements with links to the commit and the run.

Hovering a point shows commit, verdict, median, change against the base and the
machine. A [sample dashboard](../examples/history/index.html) (open the file locally)
is generated from [examples/history/sample.jsonl](../examples/history/sample.jsonl):
30 scheduled A/A jobs each of `demo-heavy` and `demo-static` (DevTools throttling,
ABAB, 20 loads, 30 October to 11 November) from the `data` branch, replayed through
`perfgate_analysis.compare`. Every job compared one commit with itself, so the
verdicts are A/A results, not a commit history; no change-point warning fires on it.

## Change-point check (advisory)

For each page and metric, the dashboard runs the online setup of
[history-cpd.md](history-cpd.md) with the unchanged research code
(`perfgate_analysis.history`):

- only the trailing points with the same policy, loads per version, throttling and
  reported Chrome version are pooled; a browser update starts a new series;
- at least 12 such points are required; the last 20 form the window;
- the window is adjusted with Lighthouse's `benchmarkIndex`, learned from the earlier
  points only and applied only when that slope is significant over at least 12 of
  them (`bench-guarded`); with fewer earlier points the series is used raw;
- E-Divisive with one change point, 199 permutations, α = 0.05, fixed seed (the page
  is reproducible from the file);
- a warning is shown when p < 0.05 and the median after the change is higher than
  before. Series with a zero median (TBT of light pages, CLS without shifts) are skipped.

Warnings are advisory and never fail a job. In the research data the detector fired
without a change in 0-17% of 20-job windows depending on the page and adjustment,
and windows overlap, so one change keeps appearing for up to 16 further pushes.
The adjustment was evaluated on scheduled A/A jobs of the demo pages, not on a real
commit history; calibration on later data remains open ([roadmap](roadmap.md)).

## Setting it up in another repository

1. Copy [examples/github/perfgate-history.yml](../examples/github/perfgate-history.yml)
   to `.github/workflows/perfgate-history.yml`, adapt the build/start step and
   replace `<perfgate-commit>` with a reviewed full commit SHA.
2. In the repository settings, set Pages to "Source: GitHub Actions". If Pages is not
   wanted, drop the `pages` job and the upload step: `index.html` is also committed
   to the history branch.
3. Push to `main`. The first run creates the history branch. The change-point check
   starts after 12 comparable pushes.

The workflow has three jobs: `measure` builds both versions and measures with a
read-only token; `history` downloads the report artifact and appends to the branch
(`contents: write`), without running application code; `pages` deploys. Pushes are
serialised by a concurrency group; GitHub keeps only the newest pending run, so a
burst of pushes yields fewer points instead of conflicting writes. The history action
also retries a rejected push by re-applying its records to the latest branch state.

Inputs of `SlavaDoroshenko/perfgate/history`:

| Input | Default | Meaning |
|---|---|---|
| `reports` | — | directory tree with perfgate report directories |
| `commit` | `github.sha` | measured commit |
| `base-commit` | empty | commit it was compared with |
| `branch` | `perfgate-history` | history branch, created if missing |
| `title` | `perfgate history of <repo>` | dashboard title |
| `page` | `web` | label for reports without measurements |
| `github-token` | job token | needs `contents: write` |
| `push` | `true` | `false` renders without committing |

Outputs: `dashboard-directory` (`index.html` and `history.jsonl`, no `.git`) and
`warnings` (number of advisory warnings, also written to the job summary).

The dashboard and `history.jsonl` are public when Pages is public, including commit
IDs, runner CPU models and timings.

## Local use

```sh
uv sync --locked --directory analysis
# append records for one or more perfgate report directories
uv run --project analysis python scripts/history/perfgate_history.py record \
  --reports results/home-check --out history.jsonl --commit "$(git rev-parse HEAD)"
# render the dashboard
uv run --project analysis python scripts/history/perfgate_history.py dashboard \
  --history history.jsonl --out site/index.html
```

The sample page is regenerated with:

```sh
uv run --project analysis python scripts/history/perfgate_history.py dashboard \
  --history examples/history/sample.jsonl --out examples/history/index.html \
  --title "perfgate history (sample: scheduled A/A jobs)"
```

Tests: `uv run --project analysis python -m pytest -q scripts/tests/test_history_store.py`.

## Verification status and limitations

- The record builder, dashboard, change-point wrapper and escaping are covered by
  tests; the sample was produced from real scheduled jobs. The composite action and
  the example workflow were checked as YAML only; a hosted run (branch creation,
  push retry, Pages deployment) has not been observed yet.
- The history point is a median measured on whichever runner the job lands on; points
  from different CPU models are not directly comparable, which the colouring shows and
  the `benchmarkIndex` adjustment only partly removes.
- Charts show every point: 3,000 records render in under a second into a 2.7 MB page,
  but long histories become dense. The history file is not compacted or rotated.
