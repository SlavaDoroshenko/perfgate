# Roadmap, updated 30 October 2026

A completed empirical study is required alongside the working product. Completion
criteria and prospective validation are specified in [research-completion.md](research-completion.md).
Changes below are implemented in the local working branch unless explicitly published.

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

- Finish fresh local end-to-end checks and record their limitations.
- Publish/review the implementation, then exercise the Action in hosted CI and on
  an external project; add a separate trusted PR-comment integration.
- Freeze the candidate before confirmatory acquisition; collect and evaluate the
  required later A/A and injected cases without tuning on that holdout.
- Add measured rare-stall browser scenarios. The simulated median-gate weakness
  must be investigated before making claims about arbitrary regression shapes.
- Compare same-load and same-time budgets using newly recorded durations.

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
- Docker packaging and documented autonomous/offline installation.
- GitLab template, MR integration and self-hosted validation.
- Deployment pilot and completed-system comparison against fixed thresholds.

## Future scope

Native application collectors are feasible extensions of the statistical kernel,
but require separate platform experiments. See [native-adapters.md](native-adapters.md).
They are not a requirement for completing the browser research scope.
