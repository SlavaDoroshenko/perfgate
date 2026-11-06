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

## Verification status

**Not yet tested on a GitLab CE/EE instance.** What was checked:

- `gitlab-ci-local` 4.77.1 validated the template against the GitLab CI schema
  and ran both jobs with Docker on a test repository (refs mode, a base commit
  and a head commit with a 400 ms blocking script, 10 loads per variant). The
  measuring job reported a regression (FCP +69%) and exited 1; the comment job ran
  after the failure, received `PERFGATE_RUN_URL` through the dotenv report and
  rendered the note. This used the native ARM Debian-Chromium image, not the
  pinned x86-64 image.
- The `gitlab` mode of `scripts/comment/cli.mjs` created and then updated a single
  note against a local fake of the notes API, and the API request sequence is
  covered by unit tests.

Not verified: real `CI_MERGE_REQUEST_*` values, environment-scoped variables,
`environment: action: access` (absent from older GitLab versions; use `prepare` there), masked-variable behaviour, the
`.post` stage with `needs`, and remote include from GitHub.

### How to verify on GitLab CE

1. Start a disposable instance and a runner on an x86-64 Linux machine:
   ```sh
   docker run -d --name gitlab -p 8080:80 --shm-size 256m gitlab/gitlab-ce:<version>-ce.0
   docker run -d --name runner -v /var/run/docker.sock:/var/run/docker.sock gitlab/gitlab-runner:<version>
   ```
   Wait for GitLab to start, sign in as root (initial password in
   `/etc/gitlab/initial_root_password` inside the container), create a project
   and register the runner with the Docker executor
   (`gitlab-runner register --executor docker --docker-image alpine`).
2. Push the perfgate image to the instance's registry or a registry the runner
   can reach; set `PERFGATE_IMAGE` to it.
3. Push a small application with `perfgate-refs.json` and the include above
   (use `include: local:` with a copy of the template if the instance has no
   Internet access). On a branch, add a deliberate slowdown, e.g. a 400 ms
   blocking script in `<head>`, and open a merge request.
4. Expect: `perfgate` fails with exit 1 and uploads `perfgate/`; `perfgate-comment`
   succeeds, and the merge request shows one note headed
   "perfgate: Performance regression detected" with links to the job and artifacts.
5. Push another commit: the same note must be updated, not duplicated. Remove the
   slowdown: the note must change to "No regression detected". Unset the token:
   the comment job must succeed without posting.
6. Check that `PERFGATE_GITLAB_TOKEN` is absent in the `perfgate` job
   (`test -z "$PERFGATE_GITLAB_TOKEN"` in a temporary `before_script`).
