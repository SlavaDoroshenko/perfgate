# Fixed rare-stall browser pilot

Exploratory protocol, declared before the main pilot. This does not change
browser-candidate-2026-10-30 or its confirmatory sample targets.

## Question and design

Can a large but infrequent main-thread stall increase measured TBT while leaving
its median little changed, and how do the existing detection rules respond to the
same observations? A two-pair instrumentation smoke check verified that timing
marks are present and an 800 ms wall-clock stall is visible in TBT. That smoke
check is excluded from the pilot; it is not evidence for detection reliability.

Use a separately generated tail-heavy.html with the unchanged historical heavy
bundle and a small additional script. After load, requestAnimationFrame schedules
a timer that optionally blocks the main thread. Both variants run the same probe;
only the preassigned stall flag differs. Trace marks record readiness, completion,
and actual start/end times. The intended 800 ms is wall-clock elapsed duration,
not a calibrated 800 ms TBT increase or fixed CPU instruction count.

- Chrome 153.0.8010.47, Lighthouse from the locked dependency tree, devtools
  throttling, fresh Chrome/profile for each load, alternating base/PR.
- 20 measured loads per variant; two preceding warmups per variant with no stalls.
- Primary endpoint: TBT. FCP/LCP/CLS remain in the unchanged complete gate.
- Conditions: A/A (no stalls), rare (3 of 20 PR loads), dense (20 of 20 PR loads).
- Fixed rare slots: sort SHA-256 strings of `seed:index`, choose the first three,
  then execute in ordinary index order. All baseline loads are clean.
- Hosted pilot: two predeclared seeds 2026103001 and 2026103002 in each condition:
  six jobs, 240 measured loads and 24 warmups. Do not stop or extend based on verdicts.
- Local replication: one rare job, seed 2026103001, 40 measured loads and 4 warmups.
  Do not pool local and hosted observations as if they came from the same environment.

This is fixed-count 15% contamination with randomly positioned, reproducible
slots, not independent Bernoulli draws with p=0.15. Warmups are explicitly clean.
One or two jobs per condition cannot estimate detection power or false-alarm rates.
Scheduling, machine differences and dependence remain limitations.

## Integrity and outcomes

Freeze acquisition/analysis sources and this protocol before main collection.
Store the assignment schedule before acquisition. Retain every load and any
failure. Missing probe markers, missing/unexpected stalls, short recorded stalls
(more than 5 ms below nominal), failed HTTP/audits or incomplete series invalidate
the whole job; they do not justify selecting replacement observations. No silently
retried measurements. Keep incomplete/invalid jobs in the summary.

Record full LHR for every load, compact timing evidence for every load, and full
traces for all scheduled stalls and the first measured pair. Store source/build
hashes, environment, measured-load and warmup elapsed times. The extra archive
serialization cost is part of this acquisition tool's time, so its timings are
not interchangeable with the ordinary collector's timings.

For valid jobs report:

1. TBT observations, mean, median, maximum, empirical p95 (descriptive at n=20),
   measured mean/median changes and actual stall durations.
2. The unchanged complete browser gate and its separate target-TBT decision.
3. All eleven historical rules plus permutation mean, applied to the identical
   20+20 TBT observations. Permutation mean uses the existing default 999 draws
   and fixed RNG seed. These exploratory per-method decisions are unadjusted
   across methods; the product gate retains its four-metric Holm correction.
4. Primary-gate results at n=20. No adaptive choice of subset/sample size.

The tests have different endpoints and null hypotheses. Welch targets a mean
shift; MWU/BM concern ordering/distributions, and the candidate additionally
requires an observed median margin. Permutation mean assumes exchangeability
under its null. A signal in one method and absence in another is not by itself a
universal ranking. Do not modify the production candidate based on this pilot.

## Follow-up decision

Use the pilot to establish treatment realization and describe failure modes.
A broader, separately frozen study is required before adding a tail/mean decision
to the gate. Preserve inconclusive or negative results. The independent main
confirmatory cohort and equal-time comparison remain separate tasks.
