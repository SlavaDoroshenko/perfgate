# GitLab CE validation (16 November 2026)

End-to-end run of [ci/gitlab/perfgate.gitlab-ci.yml](../ci/gitlab/perfgate.gitlab-ci.yml)
and the `gitlab` mode of the comment renderer on a real self-managed GitLab CE
instance, a single-machine setup like a company GitLab on one server. Setup
scripts: [ci/gitlab/ce-validation](../ci/gitlab/ce-validation).

## Setup

| Component | Version / setting |
|---|---|
| Host | Apple Silicon Mac, colima 6 CPUs / 12 GiB (VZ, Rosetta enabled), Docker 29.5.2, `linux/arm64` |
| GitLab | `gitlab/gitlab-ce:19.5.5-ce.0` (arm64 manifest), container limit 5 GiB; Puma single mode, Sidekiq concurrency 10, monitoring, registry, Pages, KAS off ([up.sh](../ci/gitlab/ce-validation/up.sh)) |
| Runner | `gitlab/gitlab-runner:alpine-v19.5.3`, Docker executor, registered with the runner-token flow (`POST /user/runners`, then `gitlab-runner register --token glrt-…`); `concurrent = 1`, `pull_policy = if-not-present`, `shm_size = 2 GiB`, jobs on the private network ([bootstrap.sh](../ci/gitlab/ce-validation/bootstrap.sh)) |
| Network | private Docker network; GitLab published on `127.0.0.1:8929` only; `external_url http://gitlab-ce` (plain HTTP) |
| perfgate image | `docker build --build-arg CHROME_SOURCE=debian -t perfgate:ce-debian .` (native arm64, Debian Chromium 156.0.8078.79, unpinned), used as a local image without a registry |
| Token | project access token, role Reporter, scope `api`, stored as masked CI/CD variable `PERFGATE_GITLAB_TOKEN` with environment scope `perfgate-comment` |
| Demo project | the page from `apps/demo-static`, a 20-line Node static server, [perfgate-refs.json](../ci/gitlab/ce-validation/demo/perfgate-refs.json) (refs mode), the template copied to `ci/perfgate.gitlab-ci.yml` and included with `include: local:` ([gitlab-ci.yml](../ci/gitlab/ce-validation/demo/gitlab-ci.yml)); `PERFGATE_RUNS: 10` |

The pinned x86-64 image (`--platform linux/amd64`) also builds on this host, but
Chrome for Testing 153 aborts with a core dump under Rosetta, as it fails under
QEMU ([docker.md](docker.md)). The measurements below therefore use the unpinned
Debian Chromium image: they test the integration, not the research protocol.
The pinned image was then verified inside GitLab on x86-64; see
[x86-64 run with the pinned browser](#x86-64-run-with-the-pinned-browser-github-actions).

## Merge requests and results

| MR | Change | Pipeline | `perfgate` | Note |
|---|---|---|---|---|
| !1 | 400 ms blocking script in `<head>` | 1 | failed, exit 1; FCP +411 ms (+33.8%), LCP +414 ms (+23.3%) | created: "Performance regression detected" |
| !2 | README only (A/A) | 2 | success, exit 0; FCP −0.2%, LCP −0.2% | created: "No regression detected" |
| !1 | push: script removed (MR diff now empty) | 3 | failed, exit 3: `compare-refs requires --base-ref …` (bug 2) | updated: "Inconclusive: no valid comparison" |
| !1 | push: `.gitlab-ci.yml` debug change | 4 | success, exit 0 | updated: "No regression detected" |
| !3 | change and revert, empty diff, fixed template | 5 | success, exit 0, base from `git merge-base` | created: "No regression detected" |

Verified:

- Merge request pipelines start on MR creation and on push; `CI_MERGE_REQUEST_DIFF_BASE_SHA`
  and `CI_COMMIT_SHA` resolve to the right commits with `GIT_DEPTH: 0`, and
  `compare-refs` builds both in worktrees inside the job.
- `perfgate` exits 1 on the regression, 0 on A/A; the job fails/succeeds accordingly.
  `perfgate/` (refs.json, server logs, runs.jsonl, comparison.json/.md,
  execution.json) and the dotenv report are uploaded also for the failed job.
- `perfgate-comment` (stage `.post`, `needs` with artifacts) runs after both a
  failed and a successful `perfgate`, receives `PERFGATE_RUN_URL` and
  `PERFGATE_ARTIFACT_URL` through the dotenv report, and uses `GIT_STRATEGY: none`.
- Exactly one note per MR: on !1 the same note (id 1) was created by pipeline 1,
  updated by a retry of the comment job and by the comment jobs of pipelines 3
  and 4. GitLab's own system notes ("added 1 commit") are ignored.
- A note posted by root that starts with the same marker was left untouched; the
  bot's note was updated (author check).
- `environment: { name: perfgate-comment, action: access }` is accepted and gives
  the comment job the environment-scoped variable; the `perfgate` job and a job
  without the environment do not receive it. In a job that echoes it the log
  shows `[MASKED]`; the token appears in no job log.
- With the variable deleted, a retried comment job printed the note to the log,
  exited 0 and did not change the existing note.
- The job and artifact-browse links in the note (`$CI_JOB_URL`,
  `$CI_JOB_URL/artifacts/browse/perfgate`) open the job and the report directory
  (checked with the project temporarily public).

Final note text on !1 after the retry (pipeline 1, fixed renderer):

```markdown
<!-- perfgate-comment:default -->
### perfgate: Performance regression detected

commit `8b798e3` · [measurement run](http://gitlab-ce/root/perfgate-demo/-/jobs/1) · policy `browser-candidate-2026-10-30` (candidate)

1 comparison(s): 1 with a regression, 0 invalid or incomplete, 0 without a detected regression.

#### demo\-static/comparison: regression

10 loads per variant requested · 410 s measurement and analysis · base `7bb6e2f` → PR `8b798e3` · [report artifact](http://gitlab-ce/root/perfgate-demo/-/jobs/1/artifacts/browse/perfgate)

| Metric | Base median | PR median | Change | 95% interval of change | Raw p, one-sided | Result |
|---|---:|---:|---:|---:|---:|---|
| demo\-static · FCP | 1216 ms | 1627 ms | +411 ms (+33.8%) | [+384 ms, +426 ms] | <0.0001 | **regression** |
| demo\-static · LCP | 1778 ms | 2192 ms | +414 ms (+23.3%) | [+399 ms, +424 ms] | <0.0001 | **regression** |
| demo\-static · TBT | 0.0 ms | 0.0 ms | 0.0 ms (zero base) | [0.0 ms, 0.0 ms] | 1.0000 | no change detected |
| demo\-static · CLS | 0.0778 | 0.0778 | 0.0000 (+0.0%) | [0.0000, 0.0000] | 1.0000 | no change detected |

<details><summary>How to read this</summary> … </details>
```

## Bugs found and fixed

1. **Links dropped on HTTP instances.** The renderer only accepted `https://`
   URLs, so on a GitLab with an `http://` external URL the note had neither the
   job nor the artifact link (pipeline 1, first comment job). It now accepts
   `http://` and `https://` (other schemes are still dropped); covered by
   `scripts/comment/render.test.mjs`.
2. **Empty merge request diff.** When the MR's net diff is empty (a change and its
   revert), GitLab leaves `CI_MERGE_REQUEST_DIFF_BASE_SHA` empty (the MR version
   has state `empty`), and the template called `compare-refs --base-ref ""`, which
   failed with a usage error (exit 3) and an "Inconclusive" note. The template now
   fetches the target branch and uses `git merge-base` in that case, and reports a
   clear error with exit 3 if that also fails. Verified in pipeline 5.

Behaviour worth knowing, documented in [gitlab.md](gitlab.md): retrying only the
`perfgate` job does not re-run `perfgate-comment` (the note keeps the old result);
retry the comment job too, or run a new pipeline.

## Timings

| Step | Time |
|---|---|
| Pull GitLab CE + runner images | 1 min 43 s |
| GitLab container start to sign-in page | 192 s; ~2.9 GiB RSS after the runs |
| Build `perfgate:ce-debian` (cached base layers) | 1 min 43 s; rebuild after a script change 6 s |
| `perfgate` job, refs mode, 10 loads per variant | 405–422 s (checkout 10 s, worktrees and warm-up ~90 s, ~17 s per load) |
| `perfgate-comment` job | 1.4–1.8 s |

## x86-64 run with the pinned browser (GitHub Actions)

The same scenarios, automated with assertions in
[.github/workflows/gitlab-ce-x86.yml](../.github/workflows/gitlab-ce-x86.yml) and
[scenarios.py](../ci/gitlab/ce-validation/scenarios.py), passed on a hosted
`ubuntu-24.04` x86-64 runner (4 vCPU, 16 GB):
[run 43981190090](https://github.com/SlavaDoroshenko/perfgate/actions/runs/43981190090),
16–17 November 2026, all 54 checks passed.

- Image built from the repository `Dockerfile` with `--platform linux/amd64`:
  Chrome for Testing **153.0.8010.47** (pinned), 1.48 GB, used by the runner as a
  local image (`perfgate:ci`, `pull_policy = if-not-present`).
- GitLab CE 19.5.5 (revision `342e9f9e0b4`) and runner `alpine-v19.5.3` started by
  `up.sh`/`bootstrap.sh`, published on the job's `127.0.0.1:8929` only; same
  memory settings, ~2.9 GiB RSS at the end.
- **20 loads per variant** (`PERFGATE_RUNS` set as a project variable).

| Scenario | MR | `perfgate` | FCP / LCP change | Note |
|---|---|---|---|---|
| 400 ms blocking script | !1 | failed, exit 1 | +412 ms (+33.2%) / +426 ms (+23.6%) | note 1 created, "Performance regression detected" |
| README only (A/A) | !2 | success | +0.2% / −0.0% | note 2 created, "No regression detected" |
| new push to !1: script removed, NOTES.md added | !1 | success | +0.4% / +0.1% | same note 1 updated, "No regression detected" |
| change and revert, empty diff (merge-base fallback) | !3 | success | −0.1% / +0.2% | note 4 created, "No regression detected" |

Each check also asserted: one merge request pipeline per commit, both jobs
present, artifacts (`archive`, `dotenv`) uploaded, the token absent in the
`perfgate` job, exactly one perfgate note per MR with job and artifact links and
the measured commit. Afterwards: the comment job without the token rendered
without posting and left the note unchanged; a root note with the marker was not
edited while the bot's note was; the token was printed as `[MASKED]` inside the
`perfgate-comment` environment, was absent outside it and appeared in no job log.

Note on !1 after the first pipeline:

```markdown
<!-- perfgate-comment:default -->
### perfgate: Performance regression detected

commit `f95022c` · [measurement run](http://gitlab-ce/root/perfgate-demo/-/jobs/1) · policy `browser-candidate-2026-10-30` (candidate)

1 comparison(s): 1 with a regression, 0 invalid or incomplete, 0 without a detected regression.

#### demo\-static/comparison: regression

20 loads per variant requested · 768 s measurement and analysis · base `01b0eba` → PR `f95022c` · [report artifact](http://gitlab-ce/root/perfgate-demo/-/jobs/1/artifacts/browse/perfgate)

| Metric | Base median | PR median | Change | 95% interval of change | Raw p, one-sided | Result |
|---|---:|---:|---:|---:|---:|---|
| demo\-static · FCP | 1239 ms | 1651 ms | +412 ms (+33.2%) | [+407 ms, +419 ms] | <0.0001 | **regression** |
| demo\-static · LCP | 1803 ms | 2229 ms | +426 ms (+23.6%) | [+421 ms, +435 ms] | <0.0001 | **regression** |
| demo\-static · TBT | 0.0 ms | 0.0 ms | 0.0 ms (zero base) | [0.0 ms, 0.0 ms] | 1.0000 | no change detected |
| demo\-static · CLS | 0.0778 | 0.0778 | 0.0000 (+0.0%) | [0.0000, 0.0000] | 1.0000 | no change detected |

<details><summary>How to read this</summary> … </details>
```

After the push, the same note (id 1) read "No regression detected" for commit
`779ad31` with FCP 1237 → 1242 ms and LCP 1802 → 1804 ms.

| Step | Time |
|---|---|
| Image build (cold, hosted runner) | 86 s |
| GitLab start to sign-in page (in parallel with the build) | 171 s |
| `perfgate` job, 20 loads per variant | 763–775 s (checkout to first load ~90 s, ~17.3 s per load) |
| `perfgate-comment` job | 2.3–2.6 s |
| Whole workflow | 59 min (scenarios 54 min) |

An earlier attempt ([run 43969764812](https://github.com/SlavaDoroshenko/perfgate/actions/runs/43969764812))
measured the same results but failed two harness checks: GitLab keeps a note's
`updated_at` when it is rewritten with an identical body, and creating the merge
request immediately after an API commit started two pipelines for one commit. In
that case both comment jobs kept a single note (created by one, updated by the
other). The script now checks the comment job's own report and waits before
opening the merge request.

## Not verified

- The Kubernetes executor, shell executor, autoscaling runners and runners on a
  different machine than GitLab.
- A container registry (the image was a local Docker image) and pulling by digest.
- `include: remote:` from GitHub and `include: project:`.
- Merged-results pipelines (`CI_MERGE_REQUEST_TARGET_BRANCH_SHA`, Premium), fork
  merge requests, protected environments, HTTPS with a private CA.
- URL mode (`PERFGATE_BASE_URL` / `PERFGATE_PR_URL`) and exit 2 (invalid
  measurements).
- A dedicated, quiet x86-64 machine: the hosted runner also ran GitLab itself,
  so the timings above include that load.
- Fully offline operation: the runner pulled
  `registry.gitlab.com/gitlab-org/gitlab-runner/gitlab-runner-helper:arm64-v19.5.3`
  on the first job; an isolated runner needs that helper image preloaded.

## Reproduce

```sh
cd ci/gitlab/ce-validation
./up.sh                      # GitLab CE + runner, ~3-4 min until ready
STATE=/tmp/pgce ./bootstrap.sh
docker build --platform linux/amd64 -t perfgate:ci ../../..   # x86-64 host
# (on ARM: --build-arg CHROME_SOURCE=debian, unpinned)
python3 scenarios.py --state /tmp/pgce --out /tmp/pgce-out --image perfgate:ci --runs 20
./down.sh                    # removes containers, volumes and the network
```

`scenarios.py` pushes the demo project (the page from `apps/demo-static`,
`demo/serve.mjs`, `demo/perfgate-refs.json`, `demo/gitlab-ci.yml` and the
template), opens the merge requests, asserts the outcomes and writes job logs,
notes and `summary.json` to `--out`; it exits 1 if any check fails. The
`gitlab-ce-x86` workflow runs these steps on a hosted x86-64 runner
(`workflow_dispatch`).
