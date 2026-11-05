# perfgate user guide

perfgate compares the lab page-load performance of two versions of a web
application — usually the base branch and a pull request — on the same machine
in the same job. It loads both versions repeatedly in alternating order with
Lighthouse in a pinned Chrome, and reports whether FCP, LCP, TBT or CLS got
worse by more than a small margin, using a statistical test instead of a
single-run threshold.

This guide covers usage. The statistical policy and its rationale are in
[compare.md](compare.md); research status is in [roadmap.md](roadmap.md).

## 1. Installation

Choose one:

- **Docker image** (recommended for CI and offline machines): everything,
  including Chrome for Testing 153.0.8010.47, is inside. See [docker.md](docker.md).
  ```sh
  docker build --platform linux/amd64 -t perfgate:local .
  docker run --rm perfgate:local --help
  ```
- **GitHub Action**: the root `action.yml` installs the same pinned environment on
  a GitHub-hosted runner (section 5).
- **Source checkout**: Node 22+, pnpm 11.7.0, [uv](https://docs.astral.sh/uv/) and
  a pinned Chrome binary.
  ```sh
  git clone https://github.com/SlavaDoroshenko/perfgate && cd perfgate
  pnpm install --frozen-lockfile
  uv sync --locked --directory analysis
  export CHROME_PATH=/path/to/chrome-for-testing-153.0.8010.47/chrome
  pnpm perfgate --help
  ```
  An auto-updating desktop browser works but produces results that must not be
  pooled with the research corpus or with other browser versions. The raw records
  store the browser version so mixed series are detectable.

## 2. Comparing two running URLs

Build and start both versions yourself (different ports, or different hosts) and
wait until both respond. Then:

```sh
pnpm perfgate compare \
  --url http://127.0.0.1:4173/ --pr-url http://127.0.0.1:4174/ \
  --runs 20 --app home --out results/home-check
```

In the Docker image the command is `perfgate compare ...` and paths are inside
`/work` (`docker run --rm --network host --shm-size=2g -v "$PWD/results:/work" perfgate:local compare ... --out /work/home-check`).

| Option | Meaning |
|---|---|
| `--url`, `--pr-url` | base and changed page |
| `--runs 10\|20` | measured loads per version (20 is the primary configuration) |
| `--app` | page label in the report |
| `--app-build` | optional workload fingerprint stored in every record |
| `--out` | new or empty directory; existing reports are never reused |

The protocol is fixed: two unrecorded warm-up loads per version, alternating
base/PR order, DevTools throttling, a fresh browser profile per load. With 20
runs a comparison makes 44 page loads; budget minutes, not seconds (about 7
minutes for 24 loads of the demo page in the Docker image on a laptop).

Output directory:

| File | Contents |
|---|---|
| `runs.jsonl` | one raw record per measured load, including failures |
| `comparison.json` | machine-readable verdict, per-metric statistics, issues |
| `comparison.md` | the same as a Markdown table |
| `execution.json` | collection/analysis durations and collector exit code |

Re-analyzing recorded data does not start Chrome:

```sh
pnpm perfgate compare --input results/home-check/runs.jsonl --runs 20 --out results/home-replay
```

## 3. Comparing two Git refs

`compare-refs` builds and serves two commits of a local repository in temporary
worktrees and then runs the URL comparison:

```sh
pnpm perfgate compare-refs --repo ../my-app --base-ref main --pr-ref feature \
  --config ../my-app/perfgate-refs.json --runs 20 --out results/refs-check
```

The configuration is JSON with argument arrays (no shell):

```json
{
  "install": ["pnpm", "install", "--frozen-lockfile"],
  "build": ["pnpm", "build"],
  "start": ["pnpm", "exec", "vite", "preview", "--host", "127.0.0.1", "--port", "{port}", "--strictPort"],
  "path": "/",
  "readyPath": "/",
  "app": "home"
}
```

`{port}` and the `PORT` variable give each server its port. Only committed
content is measured. Both refs run on your machine with your environment: use
this only for code you are prepared to execute. Details: [compare.md](compare.md).

## 4. Exit codes

| Exit | Status | Meaning |
|---|---|---|
| 0 | `no_regression_detected` | the test found no regression above the margins |
| 1 | `regression` | at least one metric regressed significantly and above its margin |
| 2 | `invalid` | the measurement series is unusable (failed loads, missing metrics, wrong counts) |
| 3 | — | setup or runtime error (bad arguments, missing Python environment, build failure) |

Treat 2 and 3 as failures, never as passes.

## 5. CI integration

**GitHub Actions.** Build and start both versions, then:

```yaml
- uses: SlavaDoroshenko/perfgate@<reviewed-commit>
  with:
    base-url: http://127.0.0.1:4173/
    pr-url: http://127.0.0.1:4174/
    runs: '20'
    app: home
```

The step uploads the report directory as artifact `perfgate-<attempt>`, writes
the Markdown report to the job summary, exposes `verdict` and
`report-directory` outputs and fails the job with the exit codes above. For a
pull request comment add the separate trusted workflow from
[pr-comments.md](pr-comments.md); complete examples are in `examples/github/`.

**GitLab CI.** Include `ci/gitlab/perfgate.gitlab-ci.yml`; see [gitlab.md](gitlab.md).

**Other CI systems.** Run the Docker image, keep the output directory as an
artifact and use the exit code. `perfgate comment render --reports <dir>`
produces the same Markdown summary for any code review system.

## 6. Reading the result

A metric is reported as a **regression** only when both hold:

1. the one-sided Mann–Whitney test says the PR loads are slower, after Holm
   correction across all four metrics of all compared pages (5% family level);
2. the observed change of the median exceeds the margin: 1% for FCP and LCP,
   max(5%, 5 ms) for TBT, 0.005 absolute for CLS.

The comment and Markdown report label every metric:

| Label | Meaning |
|---|---|
| regression | significant and above the margin |
| significant, within margin | a consistent but small slowdown (below the margin) |
| above margin, not significant | a large median change that the noise does not support |
| no change detected | neither |

**"No regression detected" is not proof of equivalence.** It means this test,
with this many loads on this machine, did not find a slowdown above the margins.
Changes smaller than the minimum detectable effect, slowdowns that affect only a
few loads (tails, rare stalls), and changes that the lab profile does not
exercise pass quietly. The interval column shows which median shifts are still
plausible: a wide interval means the measurement could not rule out a meaningful
change.

The intervals are 95% bootstrap intervals of the median difference. They are
descriptive and pointwise: they do not decide the verdict, and they assume loads
are independent.

**Invalid** means the protocol failed, not that performance was fine. Look at
`issues` in `comparison.json` and at `error` fields in `runs.jsonl`: common causes
are HTTP errors, a page that never reaches LCP, an unreachable server or a
crashed browser.

Do not re-run a failed check until it passes: that discards real detections.
Re-running quiet checks until one fails likewise pushes the false-alarm rate far
above the nominal 5%. If a result is surprising, investigate the raw
records or run a separate, pre-planned confirmation.

## 7. Limitations

- The decision policy `browser-candidate-2026-10-30` is a candidate. Its
  false-alarm rate and power are under prospective validation; one quiet A/A
  suite and single injected jobs so far ([validation](validation-2026-10-30.md)).
- Median-based: in a measured rare-stall pilot, mean TBT rose 22–33% while the
  median barely moved, and the gate missed all three sparse cases
  ([results](tail-browser-results-2026-10-30.md)).
- CLS can be multimodal; a shift in how often the page lands in each layout mode
  can mask a real change in the median ([diagnosis](cls-diagnosis-2026-10-30.md)).
- Lab measurement with throttling on one machine: results describe this machine
  and profile, not field performance for real users. Do not compare reports from
  different machines or browser versions.
- Chrome for Testing has no Linux ARM build; ARM hosts can only run the separately
  labelled Debian-Chromium image, and amd64 emulation cannot measure at all.
- The PR comment and GitLab note are advisory reports of code the pull request
  controls; enforce with the failing job.
- No history, dashboard or trend alerts yet; native (non-browser) applications are
  out of scope ([native-adapters.md](native-adapters.md)).

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| exit 3, "Python analysis unavailable" | `uv sync --locked --directory analysis` or set `PERFGATE_PYTHON` |
| exit 3, "--out must be empty" | use a new output directory per comparison |
| every load fails with `Target closed` in Docker | add `--shm-size=2g`; do not run the amd64 image under emulation |
| `failed audit or network request` issues | check the server logs; failed HTTP requests invalidate the series by design |
| `compare-refs` cannot resolve a ref | fetch it locally first (`git fetch origin main`) |
| `dubious ownership` from Git in a container | add the repository to `safe.directory` (see [docker.md](docker.md)) |
