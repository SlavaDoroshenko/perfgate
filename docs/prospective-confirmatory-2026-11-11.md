# Frozen candidate, confirmatory cohort: 11 November 2026

Policy `browser-candidate-2026-10-30`, unchanged; frozen source hashes checked by the
script. Targets and fixed samples: [research-completion.md](research-completion.md),
[amendment of 6 November](protocols/amendment-2026-11-06.md) and
[amendment (b)](protocols/amendment-2026-11-06b.md). Script:
`scripts/evaluate-scheduled-cohort.py --confirmatory`, sensitivity:
`scripts/confirmatory-sensitivity.py`; tables in
[results/2026-11-11/confirmatory](results/2026-11-11/confirmatory/). Data branch
snapshot `c70eb11`.

## Data

| | |
|---|---|
| Loads / jobs after the freeze (all arms) | 118,120 / 2,953 |
| Failed loads | 0 |
| Acquisition window | 2026-10-30 02:10 – 2026-11-11 17:30 UTC |
| Complete candidate runs (nine jobs stored) | 209 |
| Complete four-page A/A suites | 239, 0 invalid; first 200 used |
| Jobs per primary injected case | 246, 0 invalid; first 100 used |

The fixed samples are the first 200 suites and the first 100 jobs per case in
acquisition order, pooled over the scheduled and candidate workflows (177 of the 200
suites and 74 of each 100 jobs come from the candidate workflow). The 39 suites and
146 jobs per case collected after the fixed samples are reported in the tables
(`after_fixed_sample`) and do not enter the result.

## Result against the predeclared targets

| Cohort | Detections / jobs | Rate | Wilson 95% | Target | Met |
|---|---|---|---|---|---|
| A/A four-page suite, any alarm | 0 / 200 | 0% | 0–1.9% | upper ≤ 5% | yes |
| FCP, script-delay 5% | 100 / 100 | 100% | 96.3–100% | lower ≥ 80% | yes |
| LCP, lcp-delay 5% | 100 / 100 | 100% | 96.3–100% | lower ≥ 80% | yes |
| TBT, long-task 10% | 98 / 100 | 98% | 93.0–99.4% | lower ≥ 80% | yes |
| CLS, layout-shift 10% | 87 / 100 | 87% | 79.0–92.2% | lower ≥ 80% | **no** |
| CLS, layout-shift 25% | 85 / 100 | 85% | 76.7–90.7% | lower ≥ 80% | **no** |

Detection is counted on the target metric only. No primary FCP/LCP/CLS job was flagged
on an unrelated metric; the two TBT misses were flagged on CLS instead (abs +0.010,
both on AMD EPYC 9V45) and count as misses.

Smaller and larger cases (37 jobs each, not confirmatory): FCP and LCP 2–25% 37/37
throughout; TBT 2% 0/37, 5% 11/37, 25% 35/37; CLS 2% 0/37, 5% 32/37. TBT at 2–5% is
below the max(5%, 5 ms) margin by construction.

The A/A per-page view has three page-level alarms in 956 page jobs (two CLS on
`demo-heavy` at +0.077, one LCP +8.2% on `demo-heavy`), none of which survives Holm
over the whole four-page suite.

## Sensitivity

**Clustering by day.** The 100 jobs per case span nine acquisition days. Resampling
whole days (5,000 bootstrap draws) gives 2.5% quantiles of 1.00 (FCP, LCP), 0.97 (TBT),
0.84 (CLS 10%) and 0.78 (CLS 25%): the conclusions do not change.

**Runner CPU.** All CLS misses are on CPU models other than AMD EPYC 7763:

| CPU model | CLS 10% | CLS 25% | A/A `demo-heavy` jobs with CLS difference ≠ 0 |
|---|---|---|---|
| AMD EPYC 7763 | 34 / 34 | 37 / 37 | 0 / 82 |
| AMD EPYC 9V74 | 21 / 28 | 21 / 30 | 22 / 74 |
| AMD EPYC 9V45 | 15 / 18 | 13 / 17 | 1 / 50 |
| Intel Xeon 8573C | 10 / 11 | 4 / 5 | 2 / 19 |
| other Intel | 7 / 9 | 10 / 11 | 0 / 14 |

On the newer runners the `demo-heavy` page itself has a bimodal CLS: in a third of
A/A jobs on EPYC 9V74 the medians of two identical builds differ by 0.038 or 0.077,
an order of magnitude above the 0.005 margin. The injected shift then competes with a
page shift that occurs in some loads and not others, and the sign of the measured
difference flips (missed jobs have measured CLS differences of −0.061, −0.023, 0.0005,
but also +0.039 with no significance). On EPYC 7763 the page is CLS-stable and every
injected shift is found.

This is exploratory: the split by CPU was not predeclared, and the runner pool is not
under our control. It does not justify a CPU filter or a new margin for this
candidate; any such change is a new candidate with new data.

## Conclusion

- The false-alarm target is met with margin: 0 of 200 complete prospective four-page
  A/A suites (upper bound 1.9%).
- Detection targets are met for FCP, LCP and TBT.
- The CLS detection target is **not met** (lower bounds 79.0% and 76.7%). The cause
  located so far is page-level CLS instability of `demo-heavy` on part of the runner
  pool, not a failure to inject the shift (measured median shift 0.1007 / 0.2517).
- Wilson intervals assume independent jobs; the day-level resampling above is the
  sensitivity check required by research-completion.md.

Collection continues on the three-hour schedule; those jobs are extra data.
