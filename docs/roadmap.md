# Roadmap, updated 6 November 2026

A completed empirical study is required alongside the working product. Completion
criteria and prospective validation are specified in [research-completion.md](research-completion.md).
Implementation is published in draft PR #1; validation and raw-data archive are
recorded in [validation-2026-10-30.md](validation-2026-10-30.md).

## Added on 6 November

- [Dedicated candidate collection](protocols/amendment-2026-11-06.md) every three hours
  with the frozen collector; targets expected in the second half of November.
- [Before/after on identical jobs](before-after-2026-11-06.md): fixed thresholds vs the
  candidate, interim.
- [External pilot](external-pilot-2026-11-06.md) on twelve real Phanpy changes, repeated
  twice, with same-commit controls. Two FCP regressions repeat; a rare ~140 ms LCP offset
  caused one control alarm. LCP-only verdicts need confirmation before blocking.
- Interim results: [prospective](prospective-scheduled-2026-11-04.md),
  [library replication](oss-replication-2026-11-04.md).

## Completed foundations

- Lighthouse collector, four demo pages, pinned browser, versioned raw data.
- Noise/MDE, eleven historical detection rules, injected-regression power,
  run ordering, multiple-metric and four-page checks.
- Fifteen real upgrade/commit scenarios. New library cases now have eleven
  additional daily repetitions per throttling mode after the 18 October pilot.
- Actual sitespeed comparison and local/CI pilot from 18 October.
- Past-only history adjustment, E-Divisive and Mozilla-style detector diagnostics.

## Implemented on 30 October

- Whole-comparison validation before sample selection, requested-size enforcement,
  exclusion reasons and collector failure propagation.
- Raw metadata for planned sample counts, warmup failures/duration, measured-load
  duration and full binary version when CHROME_PATH is provided.
- URL and recorded-data `perfgate compare`, one-sided multi-metric candidate gate,
  absolute/relative margins, zero-baseline support, JSON/Markdown and elapsed times.
- `perfgate compare-refs`: isolated ref builds, HTTP readiness, comparison and cleanup.
- Composite GitHub Action for running URLs, artifact and job-summary output.
- An exploratory permutation-mean rule and reproducible distribution-shape/
  serial-dependence simulations. These are not evidence of native/browser tail performance.
- Explicit research completion criteria and source-hash protocol freeze utility.

## Immediate validation and integration

- Completed: local URL and isolated Git-ref checks (80 loads), hosted Action
  A/A/injected checks, and the first post-freeze CI pilot (1,320 loads / 33 jobs).
- Review the published implementation and exercise it on an external project;
  observe the trusted PR-comment integration on hosted CI.
- Completed: [CLS trace diagnosis](cls-diagnosis-2026-10-30.md) and a separate
  reserved-layout control. Mixed layout shifts and mode occupancy can mask the
  banner effect in the median; preserve this limitation of the original workload.
  Use separately labelled calibration controls in subsequent experiments.
- Continue the required later A/A and injected cohorts without tuning on that
  holdout. One quiet A/A suite is insufficient to establish its false-alarm rate.
- Completed: [measured rare-stall pilot](tail-browser-results-2026-10-30.md),
  seven jobs / 280 measured loads. The gate misses the three sparse cases while
  their mean TBT rises 22–33%; both dense and A/A controls behave as expected.
- Predeclare a mean/tail endpoint study with sufficient null controls and familywise
  error handling before changing the product gate. Improve paint-anchored treatment
  timing in a separately versioned fixture; retain the original pilot outcomes.
- Compare same-load and same-time budgets using newly recorded durations.

## Implemented on 5 November

- Two-stage pull request comment: measurement stays in the read-only
  `pull_request` job; a `workflow_run` job validates and escapes the artifact and
  updates one sticky comment ([pr-comments.md](pr-comments.md)). Hosted
  end-to-end run pending (requires the workflow on the default branch).
- Docker image with pinned Chrome for Testing, offline installation notes and a
  native-x86 smoke workflow ([docker.md](docker.md)). Built locally; the live
  pinned-browser check awaits hosted CI because amd64 emulation cannot run Chrome.
- GitLab include template with merge request notes ([gitlab.md](gitlab.md)),
  exercised with gitlab-ci-local only; GitLab CE validation still required.
- [User guide](user-guide.md) with verdict interpretation and limitations.

## Research work still required

- More sitespeed repetitions with balanced tool order, stored raw data and explicit
  sampling targets. This workflow is manual and has not replicated automatically.
- Multiple local sessions/pages/modes and, where available, additional machines.
- History calibration on later data, temporal dependence, alert clustering and
  detection delay. Current false alarms do not justify automatic blocking.
- PELT, multiple changes and longer drifts only where needed to answer these questions.
- Final reproducible reports, source/data archive and explicit claims/limitations.

## Product work after the first verified integration

- Persistent history and a small dashboard; history warnings advisory initially.
- Docker packaging: hosted x86-64 smoke run of the pinned-browser image.
- GitLab: self-hosted CE validation of the template and merge request notes.
- Deployment pilot and completed-system comparison against fixed thresholds.

## Future scope

Native application collectors are feasible extensions of the statistical kernel,
but require separate platform experiments. See [native-adapters.md](native-adapters.md).
They are not a requirement for completing the browser research scope.
