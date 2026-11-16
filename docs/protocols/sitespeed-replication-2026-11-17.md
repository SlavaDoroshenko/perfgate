# Sitespeed replication of 17 November 2026

Recorded before the run. The [18 October pilot](../sitespeed.md) had three repetitions
per case with tool order unbalanced (two sitespeed-first, one Lighthouse-first).

- One dispatch of `.github/workflows/sitespeed.yml` with `runs=10` and
  `repeats=[1..10]`: 10 repetitions × 3 cases (`aa`, `fcp2`, `tbt10`) = 30 jobs,
  60 comparisons (two tools per job on the same runner, never concurrently).
- Tool order alternates with the repetition number: five sitespeed-first and five
  Lighthouse-first repetitions per case.
- Analysis exactly as in the pilot (`perfgate_analysis.tool_comparison`): per tool,
  one-sided Mann–Whitney on each metric, Holm over the four metrics plus the frozen
  margins; also the native unadjusted sitespeed compare result. Reported: A/A alarms
  and target-metric detections per tool, with Wilson intervals, by tool order, and
  wall time per comparison.
- No sample-size changes after seeing results; failed jobs are reported, not rerun.
- Raw outputs (metadata, compare and Lighthouse samples) are archived on the data
  branch under `comparisons/sitespeed/<run id>/`.
