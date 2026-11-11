# Before/after on the confirmatory samples: 11 November 2026

Same comparison as [before-after-2026-11-06.md](before-after-2026-11-06.md), now on
exactly the fixed confirmatory samples of
[prospective-confirmatory-2026-11-11.md](prospective-confirmatory-2026-11-11.md):
the first 200 complete four-page A/A suites and the first 100 jobs per primary
injected case (smaller cases: all 37 jobs). Script: `scripts/before-after.py --sample`;
tables in [results/2026-11-11/before-after](results/2026-11-11/before-after/).

"Before" rules use the first 1, 3 or 20 loads of each variant against a 5% relative
margin on any of FCP/LCP/TBT/CLS; "after" is the frozen candidate, unchanged.

| Check | 1 load, >5% | median of 3, >5% | median of 20, >5% | candidate |
|---|---:|---:|---:|---:|
| A/A four-page check, any alarm | 77/200 | 56/200 | 17/200 | 0/200 |
| FCP, script-delay 2% | 0/37 | 0/37 | 0/37 | 37/37 |
| FCP, script-delay 5% | 60/100 | 64/100 | 70/100 | 100/100 |
| LCP, lcp-delay 2% | 1/37 | 0/37 | 0/37 | 37/37 |
| LCP, lcp-delay 5% | 98/100 | 100/100 | 100/100 | 100/100 |
| TBT, long-task 5% | 19/37 | 17/37 | 11/37 | 11/37 |
| TBT, long-task 10% | 96/100 | 97/100 | 99/100 | 98/100 |
| CLS, layout-shift 10% | 83/100 | 92/100 | 91/100 | 87/100 |
| CLS, layout-shift 25% | 83/100 | 85/100 | 93/100 | 85/100 |

With the same twenty loads, the fixed 5% threshold raises an alarm in 8.5% of
unchanged four-page checks (Wilson 5.4–13.2%) and the candidate in none (0–1.9%).
The threshold misses 30% of 5% FCP regressions and all 2% FCP/LCP regressions. It
finds CLS shifts slightly more often than the candidate, at the price of those false
alarms; the CLS gap is the page-level instability described in the confirmatory
report. Below-margin TBT cases (5%) are found by neither reliably.
