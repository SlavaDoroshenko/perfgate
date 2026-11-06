# Frozen candidate on scheduled jobs after the freeze: interim, 4 November 2026

Policy `browser-candidate-2026-10-30`, unchanged. Script:
`scripts/evaluate-scheduled-cohort.py`; tables in
[results/2026-11-04/scheduled-cohort](results/2026-11-04/scheduled-cohort/).

This is an interim progress report of the predeclared cohorts in
[research-completion.md](research-completion.md), not the confirmatory result. The
fixed sample targets stand (200 four-page A/A suites, 100 jobs per injected case);
no stopping, threshold or exclusion decision is taken from these numbers.

## Data

After the freeze (`acquisition_after_utc` 2026-10-29 23:21 UTC), the scheduled
noise and regression workflows on `main` kept collecting at the freeze `git_head`
`1abe844`. A job is included only if all of its loads were acquired after the
freeze; the cutoff is 2026-11-04 23:59 UTC.

| | |
|---|---|
| Loads / jobs (all arms) | 21,120 / 528 |
| Failed loads | 0 |
| Candidate-protocol A/A suites (abab, devtools, 20 loads, four pages) | 15 complete, 0 invalid |
| Injected jobs, abab/devtools | 288 (18 per kind × size), 0 invalid |

**Deviation, disclosed.** These jobs were recorded by the `main` collector, not the
frozen one. The measurement sources (`lighthouse.ts`, `extract.ts`, `plan.ts`) are
byte-identical to the frozen hashes; the `main` recorder lacks the newer metadata
(planned slots, warmup outcome, durations), so the "failed warmup" and "planned
slots" checks cannot run, and resource-budget questions cannot be answered from
this cohort. Every other quality check of the frozen policy is applied. The first
store=false pilot of 30 October ([validation](validation-2026-10-30.md)) is kept
separate.

## A/A

15 complete four-page suites, one Holm family over 16 metric tests each:
**0/15 suites raised an alarm** (Wilson 95% upper bound 20.4%). Per page, 0/15 on
each of the four pages. Together with the 30 October pilot that is 16 quiet suites
of the 200 required; the upper bound is still far above the 5% target, so nothing
about the false-alarm rate is established yet.

Runners: the suites span six CPU models (AMD EPYC 7763/9V45/9V74, Intel Xeon
8370C/8573C/6975P); suites with mixed CPU models across pages are normal on hosted
runners and are evaluated as they are.

## Injected regressions

Target-metric detection (the intended metric flagged after Holm and the margin),
18 jobs per cell, Wilson 95% intervals in [summary.csv](results/2026-11-04/scheduled-cohort/summary.csv):

| Kind (target) | 2% | 5% | 10% | 25% |
|---|---:|---:|---:|---:|
| script-delay (FCP) | 18/18 | 18/18 | 18/18 | 18/18 |
| lcp-delay (LCP) | 18/18 | 18/18 | 18/18 | 18/18 |
| long-task (TBT) | 0/18 | 5/18 | 18/18 | 16/18 |
| layout-shift (CLS) | 0/18 | 16/18 | 17/18 | 16/18 |

Median measured change of the target metric is close to nominal for every kind
(e.g. FCP +2.1/+5.2/+10.1/+25.2%), except lcp-delay at 2% and 5% (measured +3.7% and
+6.7%).

Reading the cells against the frozen margins:

- **FCP/LCP.** All 144 jobs detect the target, including the nominal 2% cases. The
  lower Wilson bound for 18/18 is 82.4%; the 80% lower-bound target needs the full
  100 jobs per case.
- **TBT, 2% and 5%.** Measured TBT rises 1.4% and 4.5% (median), below the 5%
  relative margin, so a miss is the designed behaviour, not a detector failure.
  The page alarm is often raised by LCP instead (long-task 2%: 8/18 jobs flag any
  metric; 5%: 12/18). As in the pilot, such alarms are not counted as correct TBT
  localisation.
- **TBT, 25%: two misses.** TBT rose only 2.8% and 2.3% (EPYC 9V45, Xeon 6975P)
  while FCP/LCP were flagged. CPU model alone does not explain it: the other three
  25% jobs on EPYC 9V45 measured +32% to +38%, and EPYC 7763 jobs +20% to +24%. The
  measured effect of the long task also varies by CPU model at 10% (7763: +8–9%,
  9V74: +7–12%). Both misses need a per-load look (did the task overlap the TBT
  window?) before any explanation is offered.
- **CLS, 2%.** +2% of the baseline CLS (~0.15) is ~0.003, below the 0.005 absolute
  margin: not detectable by design.
- **CLS, 5–25%: five misses in 54 jobs.** In three of them the median CLS fell
  (−13% to −26%), consistent with the two-mode CLS distribution described in
  [cls-diagnosis-2026-10-30.md](cls-diagnosis-2026-10-30.md). In the other two
  (5% and 25%) the median rose by about the nominal size (+0.008 and +0.039),
  above the margin, but the one-sided test was not significant after Holm.

## Progress toward the fixed targets

| Cohort | Collected | Target | Rate | Reached at the current rate |
|---|---:|---:|---|---|
| A/A four-page suites | 15 (+1 pilot) | 200 | ~2.6 suites/day (scheduled runs are sometimes skipped by GitHub) | about mid-January 2027 |
| Jobs per injected case | 18 | 100 | ~3 jobs/day | about early December 2026 |

The A/A cohort is the bottleneck. Raising the frequency of the noise schedule (or a
dedicated candidate-only A/A workflow with the frozen collector, which also records
durations) would bring it forward without changing the policy; either is a
protocol amendment and should be recorded as such before it starts.

## Reproduce

```sh
git worktree add ../perfgate-data origin/data   # data branch at 120b16d or later
cd analysis
uv run python ../scripts/evaluate-scheduled-cohort.py ../../perfgate-data/raw \
  --out ../docs/results/2026-11-04/scheduled-cohort --through 2026-11-04T23:59:59Z
```

The script refuses to run if any frozen source differs from the freeze manifest.
`manifest.json` lists the checksum of every input file.
