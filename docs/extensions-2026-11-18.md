# Follow-up cohorts: CLS-stable page, tail signal, shared-server load, 18 November 2026

Follows the [predeclared protocol](protocols/extensions-2026-11-17.md) and its storage
amendment. The gate is the frozen `browser-candidate-2026-10-30`, measured with the
collector at its frozen commit; the instruments' hashes are checked by the script.
Script: `scripts/evaluate-extensions.py`; tables in
[results/2026-11-18/extensions](results/2026-11-18/extensions/). Data:
`prospective/extensions-2026-11-17/` on the data branch, snapshot `6d57ec7a`.

## Data

| | |
|---|---|
| Complete runs / jobs / loads | 100 / 1,000 / 40,000 |
| Invalid jobs | 0 |
| Acquisition window | 2026-11-16 21:35 – 2026-11-17 22:44 UTC (two calendar days) |
| Jobs per type in the fixed sample | 100 (all collected; none after the sample) |
| Rare-stall slots confirmed by trace marks | 300 of 300 |
| Background load on during the measured span | median 50% (35–66%) of each load job |

All jobs ran on GitHub-hosted x86-64 runners with seven CPU models; 43–63% of the jobs
of each type ran on Intel Xeon 6975P-C (`by_cpu.csv`). The cohort spans about 25 hours,
so resampling by day (two days) says little; the Wilson intervals are the main
uncertainty statement, and the CPU split below is the more informative check.

## A. CLS on a CLS-stable page

| Job | Detections / jobs | Wilson 95% | Target | Met |
|---|---|---|---|---|
| A/A, reserved layout, any alarm | 0 / 100 | 0–3.7% | upper ≤ 5% | yes |
| CLS +10% (banner 70.4 px) | 100 / 100 | 96.3–100% | lower ≥ 80% | yes |
| CLS +25% (banner 80 px) | 100 / 100 | 96.3–100% | lower ≥ 80% | yes |

Measured median CLS change: +0.0078 (+9.99%) and +0.0194 (+25.0%), as designed. No
other metric was flagged in any of the 300 jobs. Within-job CLS noise on this page is
zero: every load has the same layout. Detection was complete on all seven CPU models,
including the ones where the original heavy page missed CLS in the confirmatory cohort.

So the CLS misses of 11 November come from the page, not from the gate: when the
page's own layout is deterministic, the frozen gate finds a CLS change of 10% every
time. This does not change the confirmatory result, which stays reported as missed.
Pages with asynchronously growing content can have CLS that depends on the CPU, and
for such pages CLS is a weaker signal ([CLS diagnosis](cls-diagnosis-2026-10-30.md)).

## B. Advisory tail signal for TBT

| Data | Warnings / checks | Wilson 95% | Target | Met |
|---|---|---|---|---|
| 200 confirmatory A/A four-page suites (any page) | 0 / 200 | 0–1.9% | upper ≤ 5% | yes |
| `tail-aa` (rare-stall page, no stalls) | 0 / 100 | 0–3.7% | | |
| `cls-aa-reserved` | 0 / 100 | 0–3.7% | | |
| `load-aa-abab` (A/A under background load) | 0 / 100 | 0–3.7% | | |
| `tail-rare`: 3 of 20 PR loads with an 800 ms stall | 67 / 100 | 57.3–75.4% | lower ≥ 80% | **no** |

The gate itself, as expected, does not see the rare stalls: on `tail-rare` it flagged
TBT in 1 of 100 jobs (one more job was flagged on CLS); the median TBT change was
+0.2%. The tail signal never fired on unchanged pages, in 500 checks including the
loaded runner, so it is safe to show. But it missed the sensitivity target.

Why it misses. The stall adds a mean TBT rise of about 110 ms when all of it falls in
the TBT window. With three outlying loads out of twenty, Welch's test is near its
limit: the one-sided p-value at that rise is around 0.04, just under 0.05. On the
fastest runners (Intel Xeon 6975P-C, base TBT ≈ 348 ms against ≈ 469 ms elsewhere) part
of the stall often falls after the TBT window closes. The measured mean rise is then
1–77 ms, and those jobs are not flagged:

| Runners | Warnings / jobs | Mean TBT rise when warned / not warned |
|---|---|---|
| Intel Xeon 6975P-C | 25 / 56 | 112 ms / 60 ms (median 74) |
| six other CPU models | 42 / 44 | 111 ms / 89 ms |

Both seeds behave alike (36/50, 31/50). The signal therefore catches a rare stall
when the stall actually lengthens the measured blocking time, and stays silent on
unchanged pages. As a detector of "three stalled loads out of twenty" it is not
reliable enough to promise. If it is shown at all, it is an advisory note that never
changes the verdict.

## C. Shared single server: background CPU load

Two busy threads on the four-vCPU runner, switched on and off at random for 5–60 s
periods, beside the browser.

| Hypothesis | Job | Result | Wilson 95% | Target | Met |
|---|---|---|---|---|---|
| C1 | A/A, interleaved, any alarm | 1 / 100 | 0.2–5.4% | upper ≤ 5% | **no** (by 0.4 points) |
| C2 | A/A, sequential, any alarm | 7 / 100 | 3.4–13.7% | more than interleaved | yes |
| C3 | FCP +5%, interleaved | 100 / 100 | 96.3–100% | lower ≥ 80% | yes |
| C3 | TBT +10%, interleaved | 61 / 100 | 51.2–70.0% | lower ≥ 80% | **no** |
| | FCP +5%, sequential | 100 / 100 | 96.3–100% | | |

C2: sequential minus interleaved A/A alarm rate is +6.0 points, Newcombe 95%
0.3–12.8 points. Under load, all-base-then-all-PR order lets the load pattern fall on
one variant: the seven sequential false alarms were on FCP, LCP and TBT, together or
separately. The single interleaved alarm was on CLS of the original heavy page, the
known bimodal-CLS issue, not on a timing metric. With a point estimate of 1% the C1
target is missed only because 100 jobs cannot push the upper bound below 5.4%. Its
timing metrics fired in none of the 100 jobs.

Noise under load. Within-job relative MAD of the base loads on the heavy page:

| Cohort | FCP | LCP | TBT |
|---|---:|---:|---:|
| idle (confirmatory A/A, 200 jobs) | 0.33% | 0.40% | 1.1% |
| background load, interleaved | 1.5% | 1.6% | 3.3% |
| background load, sequential | 1.3% | 1.4% | 3.3% |

Load makes the loads 3–4 times noisier. A 5% FCP change is still found every time
(median measured +5.4%). A 10% TBT change, which the idle cohort found in 98 of 100
jobs, is found in 61 of 100 (78% off Xeon 6975P-C, 44% on it), with a median measured
TBT change of +11.9%. The noise does not create false alarms when base and PR are
interleaved, but it hides smaller changes.

What this means for a single company GitLab server. Interleaving is the part that
matters: it keeps false alarms at the idle level under load, while sequential order
does not. Sensitivity drops for TBT. The practical advice is to run the measurement job
alone on the machine (one concurrent job, or a dedicated runner tag) when TBT matters;
FCP and LCP changes of 5% are still caught on a busy machine. The load model covers CPU
only, not memory, disk or network contention.

## Summary against the protocol

| Study | Target | Met |
|---|---|---|
| A | A/A ≤ 5%; CLS +10% and +25% ≥ 80% | yes |
| B | false warnings ≤ 5% | yes |
| B | rare-stall detection ≥ 80% | no (67%) |
| C1 | interleaved A/A under load ≤ 5% | no (1/100, upper bound 5.4%) |
| C2 | sequential raises more alarms than interleaved | yes (+6 points) |
| C3 | FCP +5% ≥ 80% under load | yes |
| C3 | TBT +10% ≥ 80% under load | no (61%) |

Every miss is reported as a miss. None of them touches the frozen gate's confirmatory
result. They limit two claims: how well perfgate reports rare long tasks, and how
sensitive TBT is on a busy machine.
