# Amendment of 6 November 2026: dedicated candidate collection

Recorded before the first run of `.github/workflows/candidate.yml` on `main`.

## Why

At the scheduled noise rate (~2.6 complete four-page A/A suites per day) the
predeclared 200 suites would be reached around mid-January 2027. The scheduled jobs
are also recorded by the `main` collector, which lacks planned-slot, warmup and
duration metadata ([interim report](../prospective-scheduled-2026-11-04.md)).

## What changes

- A new workflow collects only the arms the candidate is evaluated on: four-page A/A
  suites and the five primary above-margin injections (script-delay 5%, lcp-delay 5%,
  long-task 10%, layout-shift 10% and 25%), every three hours.
- It measures with the frozen sources, checked out at a pinned commit and verified
  against `browser-candidate-2026-10-30.json` before every job; a mismatch fails the
  job. Protocol: abab, devtools, two warmups, 20 loads, Chrome 153.0.8010.47.
- Results go to `prospective/browser-candidate-2026-10-30/<date>/` on the data branch,
  outside `raw/`.

## What does not change

Policy, metrics, margins, sample size, correction, exclusions and the fixed targets
(200 A/A suites, 100 jobs per primary injected case). Scheduled noise/regressions jobs
continue and count toward the same targets; both sources are reported separately and
pooled. Collection stops at the fixed targets, not when an interval looks good.

## Analysis

`scripts/evaluate-scheduled-cohort.py ... --candidate <data>/prospective/browser-candidate-2026-10-30`
adds a `source` column (`scheduled` / `candidate`) to every job and suite.
Jobs of both sources acquired in the same hour share runners and time-of-day; temporal
clustering is reviewed before intervals are interpreted as independent trials.
