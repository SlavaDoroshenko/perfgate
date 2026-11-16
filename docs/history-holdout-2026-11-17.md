# History change-point detection on a temporal hold-out, 17 November 2026

Follows the [predeclared protocol](protocols/history-holdout-2026-11-17.md). The detector
is unchanged since its [18 October evaluation](research-2026-10-18.md#history-sensitivity-and-the-cost-of-longer-windows):
E-Divisive with one change point, 199 permutations, α = 0.05, `bench-guarded` machine
adjustment learned only from earlier jobs. Every evaluated window lies entirely after
the 18 October snapshot; earlier jobs serve only as the past for the adjustment.
Script: `scripts/history-holdout.py`; tables in
[results/2026-11-17/history-holdout](results/2026-11-17/history-holdout/).

## Data

| Cohort | Past jobs per page | Hold-out jobs per page | Hold-out span |
|---|---:|---:|---|
| Scheduled `noise` A/A (primary, same cadence as before) | 94–110 | 82 | 18 Oct – 16 Nov |
| Pooled with the candidate workflow's A/A | 94–110 | 306 | 18 Oct – 16 Nov |

Pages `demo-heavy`, `demo-spa`, `demo-static`, `demo-ssr`; abab, devtools, two
warmups; FCP, LCP, TBT (TBT series with a zero median are not checked, as before).

## Sliding windows, primary cohort

False-alarm rate (no injected change) and the smallest step / ramp found in ≥ 80% of
windows; 63 windows of 20 jobs, 43 of 40 jobs per series:

| Page | Metric | Window 20: false alarms | step / ramp MDE | Window 40: false alarms | step / ramp MDE | 18 Oct, window 20: false alarms |
|---|---|---:|---|---:|---|---:|
| heavy | FCP | 1.6% | 2 / 2% | 2.3% | 1 / 2% | 1.3% |
| heavy | LCP | 9.5% | 5 / 7.5% | 7.0% | 3 / 3% | 5.1% |
| heavy | TBT | 0% | 15 / 15% | 0% | 5 / 7.5% | 3.8% |
| spa | FCP | 0% | 1 / 2% | 0% | 1 / 1% | 7.6% |
| spa | LCP | 0% | 1 / 1% | 0% | 1 / 1% | 5.1% |
| ssr | FCP | 4.8% | 1 / 2% | 7.0% | 1 / 1% | 12.7% |
| ssr | LCP | 4.8% | 1 / 2% | 7.0% | 1 / 1% | 12.7% |
| ssr | TBT | 3.2% | 15 / 20% | 2.3% | 10 / 15% | 15.9% |
| static | FCP | 0% | 1 / 1% | 2.3% | 1 / 1% | 7.9% |
| static | LCP | 3.2% | 1 / 1% | 23.3% | 1 / 1% | 7.9% |

Sensitivity carries over to the new month: FCP and LCP steps of 1–2% on the lighter
pages and 2–7.5% on the heavy page, TBT 5–20%, within one or two grid steps of the
18 October numbers. False alarms on overlapping windows range from 0% to 9.5% with
20-job windows and up to 23% with 40-job windows (static LCP: one episode spans many
overlapping windows).

## Disjoint windows

Overlapping windows share jobs, so their rates rest on few independent stretches.
Cut into non-overlapping windows:

| Cohort | Window | Windows (all series) | Alarms | Wilson 95% |
|---|---:|---:|---:|---|
| Scheduled | 20 | 40 | 0 | 0–8.8% |
| Scheduled | 40 | 20 | 3 | 5.2–36.0% |
| Pooled | 20 | 150 | 6 | 1.8–8.5% |
| Pooled | 40 | 70 | 0 | 0–5.2% |

Per series there are only 4 (scheduled) or 15 (pooled) disjoint 20-job windows, so no
single series reaches a Wilson upper bound ≤ 5% (per-series tables in
`disjoint_summary.csv`). Series of the same run share runners, so the pooled totals
above are not independent trials either.

## Conclusion

Under the predeclared rule the detector is **not calibrated for blocking** on any
series: the hold-out is too short to bound its false-alarm rate at 5%, and the point
estimates (0–10% per series with 20-job windows) are of the same order as on the data
it was chosen on. Its sensitivity does transfer to a month it has never seen. The
history therefore stays an advisory second level, as the dashboard presents it, beside
the same-job gate that decides. Establishing a blocking history detector needs several
months of scheduled history, or a dedicated machine whose between-job noise is far
lower than on shared runners ([local comparison](local-comparison.md)).
