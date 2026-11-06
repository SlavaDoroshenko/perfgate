# Before/after on identical jobs: fixed thresholds vs the frozen candidate

6 November 2026. Script `scripts/before-after.py`; tables in
[results/2026-11-06/before-after](results/2026-11-06/before-after/).

Same jobs as the [interim prospective report](prospective-scheduled-2026-11-04.md):
scheduled abab/devtools jobs acquired between the freeze and 4 November, 20 loads per
variant, all valid. Every rule sees the same loads in their recorded order; a rule
that needs *k* loads takes the first *k* of each variant.

| Rule | Loads per variant | What it stands for |
|---|---:|---|
| single load >5% | 1 | one Lighthouse run per PR against a 5% budget |
| median of 3 >5% | 3 | the Lighthouse CI default (`numberOfRuns: 3`) with a 5% budget |
| median of 20 >5% | 20 | the same budget at the candidate's sample size |
| candidate | 20 | frozen `browser-candidate-2026-10-30`, unchanged |

The threshold rules are `methods.single_run(.05)` and `methods.threshold(.05)` from RQ2,
applied to FCP/LCP/TBT/CLS (relative change; CLS with a zero baseline cannot alarm). They
were defined before this evaluation; nothing was tuned on these jobs. This is a
comparison on synthetic pages and injected regressions, not a deployment.

## Results

A/A rows count four-page checks with any alarm, so lower is better; injected rows count
jobs where the intended metric was flagged.

| Cohort | single load >5% | median of 3 >5% | median of 20 >5% | candidate |
|---|---:|---:|---:|---:|
| **A/A four-page check: false alarms** | **10/15** | **5/15** | **2/15** | **0/15** |
| script-delay 2% (FCP) | 0/18 | 0/18 | 0/18 | 18/18 |
| script-delay 5% | 11/18 | 11/18 | 15/18 | 18/18 |
| script-delay 10% / 25% | 18/18, 18/18 | 18/18, 18/18 | 18/18, 18/18 | 18/18, 18/18 |
| lcp-delay 2% (LCP) | 1/18 | 0/18 | 0/18 | 18/18 |
| lcp-delay 5% / 10% / 25% | 18/18 each | 18/18 each | 18/18 each | 18/18 each |
| long-task 2% (TBT) | 1/18 | 1/18 | 0/18 | 0/18 |
| long-task 5% | 11/18 | 9/18 | 5/18 | 5/18 |
| long-task 10% | 18/18 | 18/18 | 18/18 | 18/18 |
| long-task 25% | 17/18 | 16/18 | 16/18 | 16/18 |
| layout-shift 2% (CLS) | 0/18 | 1/18 | 0/18 | 0/18 |
| layout-shift 5% | 14/18 | 16/18 | 16/18 | 16/18 |
| layout-shift 10% | 17/18 | 18/18 | 17/18 | 17/18 |
| layout-shift 25% | 16/18 | 16/18 | 17/18 | 16/18 |

Wilson intervals are in [summary.csv](results/2026-11-06/before-after/summary.csv).

## Reading

- **False alarms.** A single run against a 5% budget alarmed on 10 of 15 four-page
  checks where nothing changed; three runs (Lighthouse CI default), on 5 of 15. Such a
  gate would be switched off or ignored. With the same 20 loads, the candidate raised
  none (upper Wilson bound 20%, so its own rate is not yet established).
- **Small FCP/LCP regressions.** At 2% only the candidate detects them (18/18 vs
  0–1/18). At 5% FCP the thresholds miss 3–7 jobs of 18. The candidate is more
  sensitive *and* quieter, at the same budget as "median of 20".
- **TBT at 5%.** Single-load and three-load checks flag the target more often (11 and 9
  of 18) than the candidate (5/18). This is not better sensitivity: those rules also
  alarm on most unchanged checks, and the measured TBT change (+4.5%) is below the
  candidate's deliberate 5% margin. It should be reported, not hidden.
- **Large regressions** (10%, 25%) are found by every rule; the difference between
  approaches is in small effects and in false alarms.
- **Cost.** A candidate job takes about 11–12 minutes of measurement on a hosted runner
  (40 loads plus warmups, 3 November A/A jobs); a single-load check takes under a minute.
  The comparison above is per check, not per minute of CI. A same-time comparison needs
  the durations the frozen collector records; the candidate workflow added on 6
  November provides them.

## Limits

Four synthetic pages, one CI provider, injected regressions of one kind at a time; 15
A/A checks. The predeclared targets (200 suites, 100 jobs per primary case) still apply.
An external deployment remains the test of practical value.
