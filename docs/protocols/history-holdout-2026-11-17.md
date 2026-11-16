# History change-point detection on a temporal hold-out: protocol of 17 November 2026

Recorded before the analysis. The history detector was evaluated on data up to the
18 October snapshot (data `103b136`, last commit 2026-10-18 16:45 UTC; [results](../research-2026-10-18.md#history-sensitivity-and-the-cost-of-longer-windows)).
Every job acquired after that snapshot has never been used to choose or tune it. This
protocol evaluates the detector, unchanged, on those later jobs.

## Detector (unchanged)

`analysis/perfgate_analysis/history.py` at the frozen hashes of
`browser-candidate-2026-10-30`: one point per A/A job (median of its base loads),
E-Divisive with one change point, 199 permutations, α = 0.05, minimum segment 4;
machine adjustment `bench-guarded` learned only from jobs before the window. Windows of
20 and 40 jobs. The raw series, the other adjustments and Mozilla's t ≥ 7 detector are
reported as secondary.

## Data

- Primary: the scheduled `noise` workflow A/A jobs (abab, devtools, two warmups), the
  same cadence as the series the detector was evaluated on; pages `demo-heavy`,
  `demo-spa`, `demo-static`, `demo-ssr`; metrics FCP, LCP, TBT; current app epochs.
- Secondary: the same pages pooled with the A/A jobs of the candidate workflow
  (denser in time: a window of 20 jobs then covers hours, not days).
- Hold-out windows: every window whose jobs all started after 2026-10-18 16:45 UTC.
  Jobs before that time serve only as the past for the machine adjustment.
- Cutoff for the hold-out: all jobs on the data branch on 17 November 2026.

## Outcomes

1. False-alarm rate per series (step 0): sliding windows, as before, and **disjoint**
   windows (non-overlapping, so the alarms are closer to independent trials), with
   Wilson intervals for the disjoint ones.
2. MDE for steps and ramps (detection in ≥ 80% of windows), as before.
3. Comparison with the 18 October numbers for the same series and window.

Decision rule declared now: the detector may be called **calibrated for blocking** on a
series only if its disjoint-window false-alarm rate has a Wilson upper bound ≤ 5% on
the hold-out; otherwise it stays advisory. With few disjoint windows this cannot be
shown; that outcome is reported as such.
