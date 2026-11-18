# Changelog

## 0.1.0 (2026-11-18)

First release. The statistical policy is `browser-candidate-2026-10-30`, frozen on
30 October 2026 and evaluated prospectively afterwards
([confirmatory report](docs/prospective-confirmatory-2026-11-11.md)).

### Tool

- `perfgate compare` (two running URLs) and `perfgate compare-refs` (two Git refs built
  in isolated worktrees): two warmups, interleaved loads in a fresh Chrome profile,
  DevTools throttling, 10 or 20 loads per variant; JSON and Markdown reports; exit code
  0 no regression detected, 1 regression, 2 invalid measurements, 3 error.
- GitHub Action (`action.yml`) with artifacts and job summary; optional `base-dist` /
  `pr-dist` add the built-asset size differences.
- Sticky pull request comment from a separate trusted workflow (`comment/action.yml`),
  and the same report as a GitLab merge request note.
- GitLab CI template (`ci/gitlab/perfgate.gitlab-ci.yml`), validated on GitLab CE.
- Docker image with Chrome for Testing 153.0.8010.47, installable offline;
  `ghcr.io/slavadoroshenko/perfgate`.
- Advisory rare long-task note: `tail.json` (Welch test on mean TBT) and a table in the
  comment for warned pages only; `perfgate tail` in the image.
- Main-branch history on a dedicated branch with a static dashboard and advisory
  change-point warnings (`history/action.yml`).

### Evaluated

- Prospective cohort (118,120 loads after the freeze): 0/200 false alarms on unchanged
  four-page checks; FCP +5% 100/100, LCP +5% 100/100, TBT +10% 98/100 detected; CLS
  87/100 and 85/100, below the predeclared 80% lower bound.
- Same loads with a 5% threshold: 17–77/200 false alarms, FCP +5% 60–70/100.
- Real application (Phanpy): two FCP regressions of 2.5–3.3% found in both repetitions.
- Follow-up cohorts (40,000 loads): CLS +10% / +25% detected 100/100 each on a page
  with deterministic layout; rare-long-task note warned 67/100 stalled jobs and 0/500
  unchanged checks; under background CPU load interleaved order gave 1/100 false alarms
  against 7/100 sequential, FCP +5% 100/100, TBT +10% 61/100.
- Limits: TBT changes below the 5% margin, rare long tasks that do not move the median,
  TBT sensitivity on a busy machine, and history change-point detection on shared
  runners (advisory only).
