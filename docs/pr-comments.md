# Pull request comments

perfgate can publish its verdict as one sticky pull request comment that is
updated on every new commit. Measuring and commenting are separate workflows,
because the measuring job executes untrusted pull request code.

## Why two workflows

| | Stage 1: `pull_request` | Stage 2: `workflow_run` |
|---|---|---|
| Runs | base and PR builds, perfgate measurement | comment renderer only |
| Code source | pull request merge commit | default branch |
| Token | read-only `contents: read` | `pull-requests: write`, `actions: read` |
| Secrets | none (none for forks at all) | only the job token |
| Output | artifact `perfgate-<attempt>` with JSON/Markdown | one comment |

A single `pull_request_target` workflow that builds the PR would hand a write token
to PR code; that pattern is avoided deliberately. Stage 2 never checks out or
executes PR code and treats the downloaded artifact as untrusted input:

- the pull request number is taken from the `workflow_run` event (same-repository
  PRs) or found by head owner/branch (fork PRs), and must still point at the
  measured `head_sha`; a stale run never overwrites a newer result;
- `comparison.json` is validated against the expected shape, numbers must be
  finite, and internally inconsistent verdicts are rejected and shown as invalid;
- all text from the artifact (page names, issues) is escaped: no HTML, links,
  table breaks or `@mentions`; symbolic links and files over 1 MB are ignored;
- the explanatory text and the policy summary come from the trusted renderer,
  not from the artifact's `comparison.md`;
- the comment is found by a hidden marker *and* the bot author, so a user cannot
  plant a comment that the workflow would then overwrite.

The verdict is computed by code that the pull request can modify (stage 1 runs
the PR's workflow file). The comment is therefore advisory. A pull request author
with write access to the workflow can fake a quiet result; enforce merges with
branch protection on the measuring job and review workflow changes.

## Setting it up in another repository

1. Copy [examples/github/perfgate-measure.yml](../examples/github/perfgate-measure.yml)
   to `.github/workflows/perfgate.yml`. Adapt the build/start step: both versions
   must be built and served on two ports before the perfgate step. Replace
   `<perfgate-commit>` with a reviewed full commit SHA.
2. Copy [examples/github/perfgate-comment.yml](../examples/github/perfgate-comment.yml)
   to `.github/workflows/perfgate-comment.yml`. `workflows:` must match the
   measuring workflow's `name:`.
3. Merge both to the default branch. GitHub only starts `workflow_run` workflows
   from the default branch, so the first comment appears on pull requests opened
   or updated after the merge.
4. Optionally mark the `measure` job as a required status check. It exits 1 on a
   detected regression and 2 on invalid measurements (see [user guide](user-guide.md)).

Several measurements (pages, matrix jobs) in one run are combined into one
comment when their artifact names match `perfgate*-<attempt>` (the root action
uploads `<artifact-name>-<attempt>`). For separate comments per workflow, set a
different `comment-key` in each comment workflow.

Inputs of `SlavaDoroshenko/perfgate/comment`:

| Input | Default | Meaning |
|---|---|---|
| `github-token` | job token | needs `pull-requests: write` and `actions: read` |
| `artifact-pattern` | `perfgate*-<attempt>` | artifacts to download from the measuring run |
| `comment-key` | `default` | distinguishes several sticky comments |
| `dry-run` | `false` | render to the job summary without posting |

Output `status` is `regression`, `no_regression_detected` or `inconclusive`; it
is empty when commenting was skipped. Stage 2 succeeds regardless of the verdict.

## Comment contents

- headline verdict over all comparisons: any regression → "Performance regression
  detected"; otherwise any invalid or missing report → "Inconclusive"; otherwise
  "No regression detected";
- measured commit, link to the measuring run and per-report artifact links;
- per metric: base and PR median, change (absolute and relative, or "zero base"),
  95% bootstrap interval of the median change, raw one-sided p-value and the
  decision: regression / significant within margin / above margin but not
  significant / no change detected;
- measurement issues when the comparison was rejected as invalid;
- a short reminder of how to read the result and its limits.

## Local preview

```sh
node scripts/comment/cli.mjs render --reports results/my-comparison
```

`--reports` accepts any directory tree containing perfgate report directories
(`comparison.json`, `execution.json`, `refs.json` from `compare-refs`).

## Verification status

The renderer and the GitHub/GitLab API request sequences are covered by tests
with a fake HTTP client (`node --test scripts/comment/*.test.mjs`). The workflows
were checked as YAML only: `workflow_run` cannot run before the files reach the
default branch, so a hosted end-to-end comment has not been observed yet. In this
repository, `compare-smoke-comment.yml` is the stage 2 for `compare-smoke` and is
the intended first hosted check once merged; its injected case is expected to
produce a "regression" section.
