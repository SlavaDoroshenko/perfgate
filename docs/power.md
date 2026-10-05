# Power on real CI noise: regressions of known kind and size (2026-10-05)

RQ2 estimated power by shifting resampled A/A loads. This is the check that resampling cannot
replace: real jobs on GitHub runners, where the PR build carries a synthetic regression of
2/5/10/25% and every rule sees the job exactly as it was measured, run order included.

Bench: `.github/workflows/regressions.yml`, four times a day since 28.09; 4 kinds × 4 sizes,
`devtools` throttling, `abab`, 20 loads per variant. Data up to 05.10: **409 jobs, 25-26 per
cell**. False alarms of the same rules: **134 A/A jobs** of the same pages, mode and throttling
(`noise.yml`). Shorter jobs are the first 5 or 10 pairs of each series, not a random subsample.

Code: `analysis/perfgate_analysis/power.py`. Reproduce with

```sh
cd analysis
uv run python -m perfgate_analysis.power ../../perfgate-data/raw --out reports/power \
  --warmup 2 --epoch fa45447b5c39 --epoch 467c2a6f9f6c --epoch 12817a1ef4f9
```

| Kind | Aimed at | Page | Effect reached (median over jobs, IQR) |
|---|---|---|---|
| `script-delay` | FCP | heavy | +2.1 / 5.1 / 10.1 / 25.2 % (IQR ≤ 0.6 pp) |
| `long-task` | TBT | heavy | **+1.0** / 4.1 / 9.0 / 24.0 % (IQR 1.1-7 pp) |
| `lcp-delay` | LCP | light | +3.6 / 6.6 / 11.7 / 26.7 % (constant +1.5 pp on top) |
| `layout-shift` | CLS | heavy | +2.0 / 5.0 / 10.1 / 25.2 % of the median, see §3 |

## 1. Detection rate, 10 loads per variant

Share of jobs flagged on the target metric (25-26 jobs per cell; a 26/26 cell has a 95% Wilson
interval of 87-100%):

| Rule | FCP 2 / 5 / 10 / 25 % | TBT 2 / 5 / 10 / 25 % | LCP 2 / 5 / 10 / 25 % | A/A false alarms (FCP / LCP / TBT) |
|---|---|---|---|---|
| Mann-Whitney | 96 / 100 / 100 / 100 | 38 / 96 / 96 / 96 | 100 / 100 / 100 / 100 | 1.5-6.1 / 0-4.5 / 7.6 % |
| **MWU & >1%** | **96 / 100 / 100 / 100** | **35 / 96 / 96 / 96** | 100 / 100 / 100 / 100 | **0 / 0 / 4.5 %** |
| Brunner-Munzel | 96 / 100 / 100 / 100 | 38 / 96 / 96 / 96 | 100 / 100 / 100 / 100 | 1.5-6.1 / 1.5-4.5 / 9.1 % |
| Welch t | 100 / 100 / 100 / 100 | 35 / 96 / 96 / 100 | 100 / 100 / 100 / 100 | 1.5-4.5 / 0-3.0 / 7.6 % |
| median >2% | 65 / 100 / 100 / 100 | 23 / 100 / 100 / 100 | 100 / 100 / 100 / 100 | 0 / 0-3.0 / 4.5 % |
| median >5% | **0 / 69** / 100 / 100 | 0 / **38** / 96 / 96 | 0 / 100 / 100 / 100 | 0 / 0-1.5 / 0 % |
| single-run >2% (1 load) | 62 / 100 / 100 / 100 | 35 / 77 / 100 / 100 | 100 / 100 / 100 / 100 | 0-1.5 / 0-4.5 / **19.7 %** |

With 5 loads the tests lose most on TBT (5%: 77-85%) and FCP stays at 92-100%; with 20 loads
the TBT 2% cell (really +1%) rises to 46-65%.

What this says:

1. **Resampling did not lie.** RQ2 predicted an MDE of 0.5-1% on FCP with ten loads; on real
   jobs a 2% FCP regression is caught 96% of the time, at zero false alarms with the 1% gate.
2. **A 5% budget misses regressions it was meant to catch.** On FCP a real +5% passes 31% of
   the time and on TBT 62% of the time: the median sits right at the threshold, so the gate
   is a coin toss. The test-based rule has no such cliff at its margin, because the margin
   (1%) is far below the sizes that matter.
3. **TBT is the hard metric.** A nominal 2% long task moved TBT by only +1% with a spread as
   large as the effect: a small extra task is partly absorbed by the tasks already on the main
   thread. No rule detects it reliably, and the 1% gate is what keeps false alarms on TBT
   below 5%. Single-run checks fire on 20% of identical TBT comparisons.
4. **LCP behind a delayed image is trivially detectable** - the delay adds a constant, not
   noise - and is the best case for every rule. The point of the cell is the opposite one:
   a delay on the heavy page turned into +24-28% LCP at any size (the LCP timer waits behind
   the post-paint long tasks), so the size of an LCP regression depends on what else the page
   does, not only on the change.
5. **Brunner-Munzel buys nothing here.** The injected regressions shift the distribution
   rather than change its shape, and on 10 loads the test is slightly liberal (9.1% A/A on
   TBT). It stays in RQ2 as the rule for shape changes, which this bench does not inject yet.

## 2. Welch t is not a safe default for CLS-like metrics

Welch's t detects 24-40% of the 2-10% CLS regressions (10 or 20 loads) where the rank tests
detect 80-100%: CLS takes
two or three distinct values per job, and a mean of a two-valued variable is dominated by how
often the rare value occurs.

## 3. CLS is a race, not a timing - judge it in absolute units

In the lab a page shifts by one of a few fixed amounts. On the heavy page a base load has CLS
0.154 or 0.231 (median two distinct values per job); **24% of loads take the larger one**,
depending on whether the late content lands before or after the first paint. A relative
"+25% CLS" is therefore mostly a statement about how many loads lost that race, which is why
the relative rules above do not grow with the size of the regression.

Judged by the absolute difference of medians (Google's "good" CLS ends at 0.1):

| Rule | 10 loads: 2 / 5 / 10 / 25 % | A/A | 20 loads: 2 / 5 / 10 / 25 % | A/A |
|---|---|---|---|---|
| median diff > 0.005 | 12 / 96 / 100 / 100 | 7.6 % | 8 / 96 / 96 / 100 | 1.5 % |
| **MWU & diff > 0.005** | 12 / 88 / 92 / 88 | **0 %** | 8 / 92 / 96 / 100 | **0 %** |
| MWU & diff > 0.01 | 12 / 27 / 92 / 88 | 0 % | 8 / 15 / 96 / 100 | 0 % |
| MWU & diff > 0.025 | 12 / 27 / 4 / 88 | 0 % | 8 / 15 / 4 / 100 | 0 % |

The +2% regression is +0.003 in absolute CLS - below any margin worth gating on - and is
missed by design. Recommendation for the gate: **CLS by absolute difference with a rank test,
margin 0.005-0.01**, not by a percentage; the report should show how often each variant took
the larger shift.

## Caveats

- One page per kind and one throttling mode; sizes are calibrated on the medians of 26-27.09,
  so cells are labelled by the nominal size and the reached effect is reported next to it.
- The injected regressions are shifts. Changes of shape (a task that fires only sometimes, a
  slower tail) are what Brunner-Munzel exists for and are the next thing to inject.
- 25-26 jobs per cell: an observed 96% has a 95% interval of about 81-99%. The bench keeps
  running; the tables are regenerated by the command above.
