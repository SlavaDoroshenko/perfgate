# Roadmap, updated 18 November 2026

Completion criteria: [research-completion.md](research-completion.md). Results in order
of evidence: the [confirmatory cohort](prospective-confirmatory-2026-11-11.md), then the
reports linked below. Dated reports are snapshots and are not rewritten afterwards,
except for marked corrections.

## Product: done

- `perfgate compare` and `perfgate compare-refs`, JSON/Markdown reports, exit codes;
  the frozen policy `browser-candidate-2026-10-30` ([compare.md](compare.md)).
- GitHub Action, two-stage sticky pull request comment, verified on real pull
  requests ([pr-comments.md](pr-comments.md)); built-asset size differences in the
  comment.
- GitLab CI template with merge request notes, validated on GitLab CE 19.5, including
  the pinned x86-64 image with 20 loads per variant on an x86-64 runner
  ([gitlab-ce-validation-2026-11-16.md](gitlab-ce-validation-2026-11-16.md)).
- Docker image with the pinned Chrome, offline installation; x86-64 smoke in CI
  ([docker.md](docker.md)); published to ghcr.io on release tags.
- Advisory rare long-task note (`tail.json`) in the comment, never part of the verdict
  ([pr-comments.md](pr-comments.md#rare-long-tasks)).
- Main-branch history and static dashboard with advisory change-point warnings
  ([history.md](history.md)); this repository's own history is on GitHub Pages.
- [User guide](user-guide.md), [changelog](../CHANGELOG.md), citation metadata.

## Research: done

- RQ1 noise and minimum detectable effects; RQ2 eleven detection rules; RQ3 interleaved
  versus sequential order ([research-2026-10-18.md](research-2026-10-18.md)).
- Policy frozen with source hashes on 30 October; prospective confirmatory cohort:
  0/200 false alarms on four-page checks, FCP/LCP/TBT targets met, CLS target missed
  and traced to the demo page ([report](prospective-confirmatory-2026-11-11.md)).
- [Before/after](before-after-2026-11-11.md) against fixed thresholds on the same loads;
  [machine time and the ten-load setting](machine-time-2026-11-17.md).
- Real application: [Phanpy pilot](external-pilot-2026-11-06.md), including the traced
  same-commit LCP offset (a service-worker route that skips `_` in hashes, reported
  upstream).
- [CLS diagnosis](cls-diagnosis-2026-10-30.md), [rare-stall pilot](tail-browser-results-2026-10-30.md),
  [library and commit cases](oss-cases.md), [replication](oss-replication-2026-11-04.md).
- [sitespeed.io comparison](sitespeed.md), pilot and balanced ten-repetition replication.
- History change-point detection, online evaluation and a
  [temporal hold-out](history-holdout-2026-11-17.md): sensitivity transfers, false alarms
  stay too high for blocking; advisory only.
- [Local laptop pilot](local-comparison.md).
- [Follow-up cohorts](extensions-2026-11-18.md), 1,000 jobs: CLS on a CLS-stable page
  (targets met), the advisory tail signal (no false warnings in 500 checks, 67% of
  rare-stall jobs warned, below target) and background CPU load as on a shared single
  server (interleaved 1/100 vs sequential 7/100 false alarms; TBT sensitivity drops).
  Scheduled research collection ended on 18 November.

## Not in scope of this release

- A deployment pilot in an organisation (needs permission) and the completed-system
  comparison there.
- Several local machines and long local sessions; a dedicated measurement server.
- GitLab with Kubernetes or shell executors, a container registry, a separate runner
  machine and fully offline runner images.
- PELT, several changes per window, drifts longer than the window.
- Native application collectors ([native-adapters.md](native-adapters.md)).
