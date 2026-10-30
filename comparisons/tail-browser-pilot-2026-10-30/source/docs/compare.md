# Comparing two running applications

`perfgate compare` now measures two URLs, validates the full series and emits a
JSON report, a Markdown report and execution timing. It uses the existing Node
collector and Python analysis environment. It does not build application refs yet.

From the repository root:

```sh
pnpm install --frozen-lockfile
uv sync --locked --directory analysis
CHROME_PATH=/path/to/pinned/chrome pnpm perfgate compare \
  --url http://127.0.0.1:4173/ \
  --pr-url http://127.0.0.1:4174/ \
  --runs 20 --out results/my-comparison
```

Both applications must already be built, running and ready. Use an empty output
directory for every invocation. `--app` labels the page; `--app-build` optionally
records a workload fingerprint. `PERFGATE_PYTHON` overrides the default
`analysis/.venv` interpreter. Source-checkout installation is currently required.
The workflow pins Chrome 153.0.8010.47; local comparisons should use that binary
when comparing with the research corpus, rather than an auto-updated desktop browser.

To analyze one complete existing experiment without starting Chrome:

```sh
pnpm perfgate compare --input /path/to/experiment.jsonl \
  --runs 20 --out results/replayed-comparison
```

Exit status is 0 for **no regression detected**, 1 for **regression**, 2 for
**invalid measurements**, and 3 for setup/runtime errors. A zero exit status is
not a statistical equivalence certificate. Never interpret missing data as a pass.
The collector itself now exits 2 on any measured failure, missing required metric,
unknown/failed HTTP request count, or failed warmup, while retaining diagnostic records.

## Candidate policy

`browser-candidate-2026-10-30` is exploratory and still requires prospective
validation. It is deliberately versioned, not described as production-calibrated.

- Two warmups per variant; alternating base/PR; DevTools throttling; 10 or 20 loads.
- FCP, LCP, TBT and CLS are always included, even when a baseline is zero.
- One-sided asymptotic Mann–Whitney test, Holm over all page/metric hypotheses.
- Observed median effect must exceed 1% for FCP/LCP, max(5%, 5 ms) for TBT,
  or 0.005 absolute units for CLS. The TBT floor is a candidate engineering
  tolerance, not an experimentally established universal threshold.
- Zero baselines have no relative percentage; absolute changes remain testable.
- 95% percentile bootstrap intervals of the median difference are descriptive,
  pointwise and based on independent resampling (1,999 draws). They do not decide
  the verdict or guarantee simultaneous coverage under serial dependence.
- The significance test concerns the distributions; combining it with an observed
  median margin is not a test that the true median shift exceeds that margin.

Validation rejects the **entire** experiment for failed measurements, duplicate or
missing slots, inconsistent order/protocol, unknown network status, missing metrics,
or wrong sample counts. New records include `plannedRuns` and `warmupErrors`;
old data lacking planned counts can only be checked against the requested count.
The HTTP failure counter covers observed HTTP errors, not arbitrary page correctness;
a workload-specific rendering check remains valuable.

## GitHub Action

The root composite action installs the measurement environment, compares two
already-running URLs, uploads artifacts, writes a job summary and preserves the
verdict as the job exit code. Application installation, build and startup belong
to the caller. The action does not post PR comments or request write permissions.

```yaml
# After checkout/build/start of both application versions and a readiness check:
- uses: SlavaDoroshenko/perfgate@<reviewed-commit-containing-action>
  with:
    base-url: http://127.0.0.1:4173/
    pr-url: http://127.0.0.1:4174/
    runs: '20'
```

The action is implemented locally; it must be published and exercised in hosted
CI before claiming a verified integration. Run untrusted PR application code with
read-only permissions and without repository secrets. A future PR-comment job
should consume artifacts separately from measurement.

## Comparing Git refs

For a local Git repository, `compare-refs` resolves both refs to immutable commit
IDs, creates two temporary detached worktrees outside that repository, installs
and builds each version, starts each on its own port and runs the same URL comparison.
It removes only its own worktrees and servers afterward, including on build failure.

```sh
CHROME_PATH=/path/to/pinned/chrome pnpm perfgate compare-refs \
  --repo /path/to/application --base-ref main --pr-ref feature \
  --config /path/to/trusted-config.json --runs 20 --out results/refs-check
```

`examples/demo-refs.json` is a working configuration for this repository. Commands
are argument arrays, executed without a shell. `{port}` placeholders and the `PORT`
environment variable identify each server's port. `path` selects the measured page;
`readyPath` selects the HTTP readiness endpoint. Install/build commands are optional.
Build/readiness timeouts are configurable. This runs code from both refs: use it
only in the intended trust context, without unnecessary secrets in the environment.
Dirty/untracked application changes are not included; refs refer to committed trees.
Refs must exist locally; fetch, submodules, LFS and credentials are caller concerns.

Build/start logs, resolved commits, configuration and timings are saved beside the
`comparison/` subdirectory. Working directories are isolated, but shared OS resources,
external databases and the package manager cache are not. Verify that background
services do not interfere with the measured application. Multi-platform build
orchestration and native application launch are outside this browser MVP.

New raw records also include measured-load duration, total warmup duration and the
full Chrome binary version when `CHROME_PATH` is set. These support prospective
same-time budget analysis; the older corpus cannot retroactively supply those
fields. `execution.json` records full collection and analysis elapsed times.
