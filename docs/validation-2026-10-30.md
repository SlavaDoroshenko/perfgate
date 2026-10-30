# MVP and first frozen-policy pilot: 30 October 2026

Implementation: draft [PR #1](https://github.com/SlavaDoroshenko/perfgate/pull/1),
source `c91deb072204fe440e50ffd529deecb7128b1845`.
Raw data and checksums: [data archive](https://github.com/SlavaDoroshenko/perfgate/tree/1c9fcdc/comparisons/validation-2026-10-30).
The candidate's exact source hashes still match the protocol freeze. Its recorded
git_head predates the implementation commit; the hashes identify the tested bytes.
No thresholds were tuned using this pilot.

## Product validation

77 Python tests and 39 JavaScript tests passed, as did type checks and builds.
Recorded-data CLI checks exercise exits 0 (no regression detected), 1 (regression),
and 2 (invalid comparison). A quiet result does not establish equivalence.

Four local comparisons produced 80 measured loads (warmups separate), using pinned
Chrome 153.0.8010.47, ABAB, devtools throttling, two warmups and ten loads per variant:

| Case | Result |
|---|---|
| Light page A/A | No regression detected |
| Heavy page A/A | No regression detected |
| Heavy page +179 ms script-delay | Regression detected |
| Same Git commit, two independent builds | No regression detected |

The Git-ref path installed/built both copies, waited for HTTP readiness and removed
its temporary worktrees; cleanup_issues was empty. The local +179 ms scenario
measured roughly +7% FCP, rather than the nominal CI-calibrated +10%. These are
single-session functionality checks on one machine, not cross-machine validation.

Hosted [Action smoke](https://github.com/SlavaDoroshenko/perfgate/actions/runs/40974126703)
and [CI](https://github.com/SlavaDoroshenko/perfgate/actions/runs/40974126784) passed.
The Action correctly distinguishes same-URL A/A and an injected delay. Archived
smoke raw data comes from the earlier successful run 40973404648. Generic smoke
artifacts lack the matched application-build metadata required for the historical
core cohort; keep them as integration evidence.

## First prospective pilot

[Noise](https://github.com/SlavaDoroshenko/perfgate/actions/runs/40974119962) and
[injections](https://github.com/SlavaDoroshenko/perfgate/actions/runs/40974124046)
ran with runs=20 and store=false after the freeze: 1,320 measured loads, 33 jobs,
zero failed loads and zero invalid jobs. All acquisition timestamps are after the
frozen boundary. The archive is outside raw/ to preserve the historical cohort.

The candidate ABAB/devtools four-page A/A suite is quiet. Other ordering/throttling
arms are retained but are outside this candidate's operating protocol. There is
only one independent suite here, so this cannot establish a low false-alarm rate.

| Injection | Target detections in this pilot |
|---|---|
| Script delay | 2%, 5%, 10%, 25% nominal cases |
| LCP delay | 2%, 5%, 10%, 25% nominal cases |
| Long task | 10%, 25%; no target detection at 2%, 5% |
| Layout shift | 10%; no target detection at 2%, 5%, 25% |

Each cell represents one job per nominal level, not a power estimate. The +5%
long-task case raises a page alarm through LCP, while TBT rises only 3.82%, below
its 5% relative margin. Do not count this as successful TBT detection.
The nominal +25% layout-shift job measures only +0.25% CLS (+0.000491 absolute):
this aggregate effect does not establish that the injector itself failed.
Subsequent [trace diagnosis](cls-diagnosis-2026-10-30.md) found two CLS modes whose
changing occupancy can mask the banner effect in the median. The original gate
outcome is retained; no detector threshold was changed. The +2% CLS effect is below the
absolute 0.005 margin; the +5% case exceeds the margin but is not significant after
correction in this job. Retain all outcomes, including these limitations.

See [per-job results](results/2026-10-30/prospective_pilot_jobs.csv),
[manifest](results/2026-10-30/prospective_pilot_manifest.json) and
[local results](results/2026-10-30/local_mvp.csv). Reproduce the prospective summary
with scripts/summarize-pilot.py and the archived prospective directory.

## Next research steps

1. Incorporate the [CLS trace diagnosis](cls-diagnosis-2026-10-30.md): distinguish
   nominal treatment, multimodal observed effects, target detection and any-metric
   detection. Use a separately labelled controlled workload for further calibration.
2. Continue the predeclared independent cohorts (200 full A/A suites and 100 jobs
   per primary injected case), reporting interval estimates and exclusions.
3. Measure rare-stall browser scenarios and compare both equal-load and equal-time
   budgets. Current tail evidence is simulated only.
4. Repeat sitespeed and local sessions; test an external project. Calibrate history
   alarms on later data before allowing blocking decisions.
5. Produce the final reproducible report against the research completion criteria.

This completes an implemented and exercised MVP plus an initial prospective pilot,
not the entire empirical study. Native adapters remain a separately scoped extension.
