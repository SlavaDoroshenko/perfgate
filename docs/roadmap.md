# Roadmap, updated 18 October 2026

## Measurement bench — due by the end of October: complete

Lighthouse collection, four demo pages, pinned Chrome, scheduled GitHub jobs,
versioned raw data, app-build epochs, noise/MDE analysis and absolute CLS checks
are implemented. The [current research snapshot](research-2026-10-18.md) contains
the reproducible result tables and their limitations.

## Research — October–November: core experiments complete, replication ongoing

Implemented and evaluated:

- Eleven detection rules and effect-size estimates.
- Four regression kinds × four sizes, measured in CI.
- Run ordering and 5/10/20 loads per variant.
- Holm/BH over metrics, and one correction across four-page suites.
- History adjustment learned from the past, step/ramp changes, guarded CPU
  benchmark adjustment, E-Divisive and a Mozilla-style t-statistic detector,
  20/40-job windows.
- Fifteen real upgrade/commit scenarios; the eight new library cases passed their
  first complete CI run and now collect daily repetitions.
- An actual sitespeed collector/compare benchmark: nine completed jobs and 360
  measured loads across both tools, with the results and protocol documented.
- A [local A/A pilot](local-comparison.md): three complete jobs / 60 loads, compared
  with 109 CI jobs at matching sample size, browser and app build.

Remaining work in this stage:

- Replicate the new cases across runs and machines, including the tool comparison.
- Extend the local pilot to more pages and throttling modes.
- Evaluate changes in distribution shape, rather than only location shifts.
- Calibrate history alarms on a temporal hold-out and investigate dependence.
  Current false-alarm rates are too high on some pages for automatic blocking.
- PELT, multiple changes per window and slower drift are further extensions.
- Prepare the research article in November–December.

The initial sitespeed/local samples establish reproducibility and observed effects;
they do not provide precise estimates of rare false alarms.

## User-facing MVP — December–February: not started

- `perfgate compare`: build base/PR, measure in alternating order, emit JSON and text.
- GitHub Action, PR comment, confidence interval and verdict.
- Persistent history and a small dashboard.
- Docker image and offline installation path.
- GitLab template, MR comment, calibration and a self-hosted validation.
- User documentation.

Existing workflows collect research data. Checking an arbitrary project's PR is a
separate milestone.

## Spring 2027

Evaluate the completed system against fixed thresholds under a matched resource
budget, write the thesis and conference material, and run an authorized deployment
pilot after the MVP is ready.
