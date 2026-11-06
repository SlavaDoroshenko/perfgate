# Library upgrades: replication through 4 November 2026

Follow-up to [oss-cases.md](oss-cases.md). On 18 October each of the eight new
library cases had one job per throttling mode; the daily `oss-libs.yml` schedule has
since repeated them. Data branch `120b16d`, all hosted runners (six CPU models), no
failed loads: 33,080 loads, 827 jobs, 11 release pairs.

Command: `uv run python -m perfgate_analysis.oss_report ../../perfgate-data/raw --out ...`.
Per-job table: [results/2026-11-04/oss/jobs.csv](results/2026-11-04/oss/jobs.csv);
per case/metric summary: [replication.csv](results/2026-11-04/oss/replication.csv).
"Flagged" uses the report's two-sided rule (Holm over the page's metrics and the
FCP/LCP 1%, TBT 5%, CLS 0.005 margins); these cases have no assumed ground truth.

## TBT under devtools

| Upgrade | Jobs | Median TBT change | 10–90% of jobs | Flagged | Same sign |
|---|---:|---:|---|---:|---:|
| chart.js 3 → 4 | 90 | −16.9% | −18.7 … −15.2% | 100% | 100% |
| date-fns 2 → 4 | 90 | −19.4% | −22.4 … −17.3% | 100% | 100% |
| marked 9 → 18 | 90 | +9.7% | +7.4 … +12.5% | 98% | 100% |
| Immer | 18 | −24.7% | −25.7 … −23.1% | 100% | 100% |
| jQuery 3 → 4 | 18 | −2.3% | −3.4 … −1.5% | 0% | 100% |
| Luxon | 18 | −59.3% | −62.2 … −55.3% | 100% | 100% |
| DOMPurify | 18 | −10.0% | −11.1 … −9.3% | 100% | 100% |
| Vue compile | 18 | −6.6% | −8.7 … −5.0% | 89% | 100% |
| Vue reactivity | 18 | −61.3% | −65.9 … −55.7% | 100% | 100% |
| YAML | 18 | −91.2% | −91.5 … −89.8% | 100% | 100% |
| Zod | 18 | −39.2% | −41.8 … −32.1% | 100% | 100% |

The direction of every TBT change replicated in all jobs, across CPU models, and
the medians stay within seven percentage points of the first run (Vue reactivity: −68.4% then, −61.3% now; the rest within two). jQuery's −2–3% is real by
direction but below the 5% margin in every job, which is the margin doing its job.
Vue compilation sits near the margin, hence 89%. marked's +4.6% LCP regression
under devtools was flagged in all 90 jobs.

## A single-job result that did not replicate

The first extension run reported **+28.3% LCP for Vue compilation under
`simulate`** while its TBT improved (oss-cases.md). The 17 later jobs do not
reproduce it: median −1.1%, with jobs at −25.7%, −22.4% and −9.7% and the rest within
±2%. Under `simulate` this page's LCP is evidently bimodal, and the first job happened
to land in the slow mode for the newer release only. The original statement should be
read as a one-job observation; it is superseded by this replication.

Two other simulate-only effects did replicate: jQuery 4 (−10.0% FCP, −8.8% LCP in all
18 jobs) and Zod 4 (−11.1% FCP, −12.9% LCP), with no matching change under devtools.
Throttling modes still disagree on some metrics; reporting one mode alone would hide it.

## What this does and does not show

- Library effects on these amplified workloads are stable across days and runner CPU
  models; one comparison per case is enough to get the direction, not the magnitude
  of mode-dependent metrics.
- These are still API-heavy synthetic workloads, not whole applications; they are not
  estimates of what an upgrade does to an arbitrary site.
- The jobs fall partly after the 30 October freeze, but library cases are outside the
  frozen candidate's predeclared A/A and injected cohorts.
