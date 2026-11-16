# Machine time and the ten-load comparison, 17 November 2026

What one perfgate check costs on a hosted runner, and what the predeclared secondary
ten-load comparison gives on the same confirmatory samples
([prospective-confirmatory-2026-11-11.md](prospective-confirmatory-2026-11-11.md)).

## Time per page

From the 2,016 jobs of the candidate workflow (recorded per-load `durationMs` and
`warmupDurationMs`; GitHub `ubuntu-24.04`, 4 vCPU, devtools throttling, fresh Chrome
per load):

| Page | Per load | 2 warmups per variant | 20 loads per variant | 10 loads per variant |
|---|---:|---:|---:|---:|
| demo-heavy | 17.8 s | 1.2 min | 13.1 min | 7.2 min |
| demo-spa | 17.5 s | 1.2 min | 12.9 min | 7.0 min |
| demo-ssr | 18.0 s | 1.2 min | 13.2 min | 7.2 min |
| demo-static | 17.3 s | 1.2 min | 12.7 min | 6.9 min |

The 90th percentile is within 0.4 min of the median; the CPU model changes the median
by less than 0.6 min. A whole GitHub job, including checkout, dependency install,
Chrome download and the (small) demo build, took 13.7 min (median of 54 jobs,
12.8–14.2). The cost is dominated by the per-load browser start and throttled load,
not by the page: a check costs about 0.6 min per page and load pair, so pages run as
parallel jobs, and the number of pages, not their weight, sets the bill.

At the same per-load cost, a fixed-threshold check with one load per variant would
take about 35 s and with three loads (the Lighthouse CI default) about 1.8 min,
without warmups.

## Ten loads instead of twenty

The freeze declares ten loads per variant as the secondary configuration. Evaluated
on exactly the same confirmatory jobs, truncated to their first ten slots per variant
(`scripts/evaluate-scheduled-cohort.py --confirmatory --runs 10`; tables in
[results/2026-11-11/confirmatory-10-loads](results/2026-11-11/confirmatory-10-loads/)):

| Cohort | 20 loads | 10 loads |
|---|---|---|
| A/A four-page suite, any alarm | 0/200 (0–1.9%) | 1/200 (0.1–2.8%) |
| FCP, script-delay 5% | 100/100 (96.3–100%) | 99/100 (94.6–99.8%) |
| LCP, lcp-delay 5% | 100/100 (96.3–100%) | 100/100 (96.3–100%) |
| TBT, long-task 10% | 98/100 (93.0–99.4%) | 92/100 (85.0–95.9%) |
| CLS, layout-shift 10% | 87/100 (79.0–92.2%) | 69/100 (59.4–77.2%) |
| CLS, layout-shift 25% | 85/100 (76.7–90.7%) | 65/100 (55.3–73.6%) |

FCP and LCP at 2% are 37/37 with both sample sizes. With ten loads the false-alarm and
FCP/LCP/TBT targets are still met, at about half the machine time (7 instead of 13 min
per page); CLS on the original heavy page degrades further. The ten-load result is
secondary, as declared; it is not an adaptive early stop.

## Recommendation for users

- Default: 20 loads per variant, one job per page in parallel, about 14 min wall time.
- Ten loads per variant when CI time matters more than CLS sensitivity, about 8 min.
- Budget about 0.6 runner-minutes per page and load pair, plus build time of both versions.
