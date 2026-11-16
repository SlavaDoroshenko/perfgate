# GitLab merge requests

[ci/gitlab/perfgate.gitlab-ci.yml](../ci/gitlab/perfgate.gitlab-ci.yml) adds two
jobs to merge request pipelines:

- `perfgate` (stage `test`) measures and uploads `perfgate/` as an artifact; it
  fails with exit 1 on a detected regression and 2 on invalid measurements;
- `perfgate-comment` (stage `.post`, runs even when `perfgate` failed) renders the
  same report as the GitHub comment and creates or updates one merge request note.

Both use the [Docker image](docker.md), which must be pushed to a registry that
your runners can pull from. A Docker (or Kubernetes) executor on x86-64 is
required for the pinned browser.

## Setup

1. Build and push the image, e.g. to the project's container registry:
   ```sh
   docker build --platform linux/amd64 -t registry.example.com/tools/perfgate:1 .
   docker push registry.example.com/tools/perfgate:1
   ```
2. In the application's `.gitlab-ci.yml`:
   ```yaml
   include:
     - remote: https://raw.githubusercontent.com/SlavaDoroshenko/perfgate/<commit>/ci/gitlab/perfgate.gitlab-ci.yml
       # recent GitLab versions can pin the content with integrity: sha256-<base64 digest>
   variables:
     PERFGATE_IMAGE: registry.example.com/tools/perfgate@sha256:<digest>
     PERFGATE_REFS_CONFIG: perfgate-refs.json
   ```
   For offline instances copy the template into the project (or a shared CI
   project) and use `include: local:` or `include: project:` instead of `remote:`.
3. Choose a measurement mode:
   - **refs** — set `PERFGATE_REFS_CONFIG` to a [compare-refs configuration](compare.md)
     committed to the application. The job compares
     `CI_MERGE_REQUEST_DIFF_BASE_SHA` with `CI_COMMIT_SHA`, building each in an
     isolated worktree (`GIT_DEPTH: 0` is set so the base commit is present). The
     application's build toolchain must be in the image; Node 22, pnpm and Python
     are already there.
   - **URLs** — leave `PERFGATE_REFS_CONFIG` empty, override `perfgate:` with a
     `before_script` that builds and starts both versions, and set
     `PERFGATE_BASE_URL` / `PERFGATE_PR_URL`.
4. Optional variables: `PERFGATE_RUNS` (10 or 20, default 20), `PERFGATE_APP`
   (report label, default `web`), `PERFGATE_COMMENT_KEY`.
5. For notes, create a project access token with role **Reporter** and scope
   **api**, and store it as CI/CD variable `PERFGATE_GITLAB_TOKEN`: masked, and with
   environment scope `perfgate-comment`. Without the token the comment job prints
   the rendered note to its log and succeeds.

## Token exposure

GitLab has no equivalent of GitHub's `workflow_run`: every job of a merge
request pipeline is defined by the merge request's own `.gitlab-ci.yml`. The
template limits exposure but cannot make the token unreachable for someone who
can change that file:

- The token variable is scoped to the `perfgate-comment` environment, so the
  `perfgate` job, which runs application code, does not receive it. The comment
  job uses `GIT_STRATEGY: none` and does not run repository code.
- A developer who can push a branch can still edit the pipeline to give another
  job that environment. Protected environments (a paid GitLab feature) or a token
  that is only allowed to comment limit the damage. Treat the token as available
  to everyone with push access, and give it nothing beyond Reporter/api.
- Merge requests from forks run in the fork by default, where the variable does
  not exist: the note is skipped. Running fork pipelines in the parent project
  requires a maintainer to start them deliberately; review the change first.
- The note is advisory, like the GitHub comment: the report is produced by code
  that the merge request controls. Use the failing `perfgate` job, with
  "Pipelines must succeed", for enforcement.

The renderer treats artifacts as untrusted text (see [pr-comments.md](pr-comments.md)):
it validates `comparison.json`, escapes all strings and only updates a note that
starts with its marker and was written by the token's own user.

## Retries

Retrying only the `perfgate` job does not re-run `perfgate-comment`, so the note
keeps the previous result. Retry the comment job as well, or run a new pipeline.

## Verification status

Validated end to end on GitLab CE 19.5.5 with a Docker-executor runner 19.5.3 on
one machine; see [gitlab-ce-validation-2026-11-16.md](gitlab-ce-validation-2026-11-16.md)
for the setup, the merge requests, the note text and timings. Verified there:
real `CI_MERGE_REQUEST_*` values and `compare-refs` in the job, exit codes 0 and
1, artifact and dotenv upload, the `.post` comment job with `needs` after a failed
and a successful measurement, one note created and then updated (not duplicated)
by retries and new pushes, the environment-scoped masked token (absent from the
`perfgate` job), `environment: action: access`, and the comment job without a
token. The run used the native ARM Debian-Chromium image. Not covered: the pinned
x86-64 image, the Kubernetes executor, a container registry, `include: remote:`,
merged-results and fork pipelines. Older GitLab versions lack
`environment: action: access`; use `prepare` there.

Earlier checks: `gitlab-ci-local` 4.77.1 validated the template against the GitLab
CI schema and ran both jobs on a test repository; the notes API request sequence
of `scripts/comment/cli.mjs gitlab` is covered by unit tests.

Notes from the CE run:

- Instances with a plain `http://` external URL are supported: the note links to
  the job and to its `perfgate/` artifact directory.
- When a merge request's net diff is empty (for example a change and its revert),
  GitLab leaves `CI_MERGE_REQUEST_DIFF_BASE_SHA` unset; the template then fetches
  the target branch and compares against `git merge-base`.
- On an isolated network, preload the runner helper image
  (`registry.gitlab.com/gitlab-org/gitlab-runner/gitlab-runner-helper:<arch>-v<version>`)
  next to the perfgate image; the runner pulls it for the first job.

To repeat the check, [ci/gitlab/ce-validation](../ci/gitlab/ce-validation) starts a
disposable GitLab CE and runner bound to `127.0.0.1`, registers the runner, creates
the project, token and variable, and removes everything afterwards.
