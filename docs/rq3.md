# RQ3: interleaved (abab) vs sequential series (2026-09-27)

**Question.** Both modes spend exactly the same loads: `sequential` measures all base loads and
then all PR loads, `abab` alternates them. Does the order change how often an A/A comparison
(no difference by construction) is reported as a regression?

**Data.** Current protocol (see `rq1-preliminary.md`), 2026-09-17 … 09-27: 511 A/A jobs on
GitHub-hosted `ubuntu-24.04`, four pages × two throttling modes × two orders, 24-40 jobs per
configuration, 20 loads per variant. Every job is analysed with its **real** base/PR labels and
run order — resampling would shuffle the order away, and the order is exactly what differs.

Code: `analysis/perfgate_analysis/rq3.py`. Reproduce:

```sh
cd analysis
uv run python -m perfgate_analysis.rq3 ../../perfgate-data/raw --out reports/rq3 \
  --warmup 2 --epoch fa45447b5c39 --epoch 467c2a6f9f6c --epoch 12817a1ef4f9
```

## Answer

**Yes. A sequential series raises 3-5 times more false alarms, the extra alarms are not
explained away by a minimum effect on TBT, and interleaving costs nothing.**

## 1. Per comparison: FCP, LCP and Speed Index

Two-sided Mann-Whitney at α=0.05 on each (job, metric), pooled over pages; 95% Wilson intervals.
"Gate" = significant **and** |effect| > 1%, the rule recommended in `rq2-methods.md`.

| Throttling | Mode | Comparisons | False alarms | Gate fires |
|---|---|---|---|---|
| devtools | abab | 384 | **3.1%** [1.8, 5.4] | 0 |
| devtools | sequential | 381 | **14.4%** [11.3, 18.3] | 0 |
| simulate | abab | 384 | 3.6% [2.2, 6.0] | 1 |
| simulate | sequential | 384 | 8.9% [6.4, 12.1] | 0 |

`abab` stays at or below the nominal 5% under both throttling modes. `sequential` is 4.6x worse
under `devtools` and 2.4x worse under `simulate` (Fisher p = 1.5·10⁻⁸ and 0.004; the metrics of
one job are correlated, so treat these p-values as descriptive — the job-level test in section 3
is the valid one).

What the extra false alarms look like: the mean A/A effect is zero in both modes (−0.004% vs
+0.026% under `devtools`), and the spread of the effect is similar (SD 0.31% vs 0.27%). The rank
correlation of the metric with the position in the job is the same in both modes (median
|ρ| ≈ 0.16): the machine drifts during every job. `abab` spreads that drift evenly over both
variants; `sequential` hands it to whichever variant ran second, in a direction that differs from
job to job. The result is not a bias but a stream of small, highly "significant" differences —
every one of them below 1%, which is why the gate removes them on these metrics.

## 2. TBT: where the gate does not save the sequential design

| Throttling | Mode | Comparisons | False alarms | Gate fires |
|---|---|---|---|---|
| devtools | abab | 64 | 0.0% [0.0, 5.7] | **0.0%** |
| devtools | sequential | 63 | 15.9% [8.9, 26.8] | **14.3%** |
| simulate | abab | 64 | 6.3% [2.5, 15.0] | 3.1% |
| simulate | sequential | 64 | 15.6% [8.7, 26.4] | **15.6%** |

TBT (heavy SPA and SSR pages; the other two have zero TBT) is noisy enough that drift during a
sequential series produces differences of several percent, and those pass a 1% minimum effect.
A team that measures main-thread work and runs base and PR one after another gets a false
"TBT regression" on roughly one PR in seven, with a gate that looks strict.

## 3. Per pull request: one verdict over all metrics

A PR sees one verdict per job: an alarm if **any** of its metrics is flagged (FCP, LCP, SI and,
where non-zero, TBT). Jobs are independent units, so this is also the valid test between modes.

| Throttling | Mode | Jobs | Any metric, raw | Holm-corrected | Holm + 1% gate |
|---|---|---|---|---|---|
| devtools | abab | 128 | 5.5% [2.7, 10.9] | **1.6%** [0.4, 5.5] | **0.0%** [0.0, 2.9] |
| devtools | sequential | 127 | 27.6% [20.5, 35.9] | **14.2%** [9.2, 21.3] | **3.1%** [1.2, 7.8] |
| simulate | abab | 128 | 8.6% [4.9, 14.7] | 1.6% [0.4, 5.5] | 0.0% [0.0, 2.9] |
| simulate | sequential | 128 | 18.0% [12.3, 25.5] | 8.6% [4.9, 14.7] | 3.1% [1.2, 7.8] |

Fisher test on the Holm-corrected verdict, sequential vs abab: p ≈ 1·10⁻⁴ (`devtools`),
p = 0.019 (`simulate`).

Three conclusions for the tool:

1. **Testing several metrics without correction multiplies false alarms**: 5.5% of A/A PRs raise
   at least one alarm even with `abab`, against 3% per comparison. Holm brings it back to 1.6%.
2. **Holm + a 1% minimum effect + `abab` gave zero false alarms on 256 A/A PRs.** The same rule
   with a sequential series still fires on 3.1% of PRs.
3. **The order is free.** Both modes spend the same loads and the same CI minutes; `abab` only
   changes the order. There is no trade-off to argue about.

## 4. How this changed as data accumulated

| Data | devtools abab | devtools sequential | simulate abab | simulate sequential |
|---|---|---|---|---|
| 2 days (2026-09-17) | 4.2% | 20.8% | — | — |
| 15 jobs/config (2026-09-21) | 5.6% | 16.7% (p=0.031) | 2.2% | 0.0% (n.s.) |
| 24-40 jobs/config (2026-09-27) | 3.1% | 14.4% (p=1.5·10⁻⁸) | 3.6% | 8.9% (p=0.004) |

The `devtools` effect shrank from five-fold to about four-fold and became unambiguous; the
`simulate` effect, invisible at 15 jobs, appeared at 24-40. The earlier reading "under `simulate`
the order does not matter, because Lantern models the machine away" was wrong: Lantern removes
most of the machine from FCP/LCP, but not all of it, and not from TBT.

## Caveats

- One runner type (`ubuntu-24.04`), four demo pages, 20 loads per variant. With fewer loads the
  sequential halves are shorter and the drift between them smaller; the effect at n=5-10 is not
  measured yet.
- A/A only: the question is false alarms. Detection of real regressions is compared across
  methods in `rq2-methods.md`, on `abab` data.
- The per-comparison rates in sections 1-2 pool correlated metrics of one job; section 3 is the
  independent-unit analysis.
