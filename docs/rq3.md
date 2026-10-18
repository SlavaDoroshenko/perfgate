# RQ3: interleaved (abab) vs sequential series (updated 2026-10-05)

Latest results: [18 October snapshot](research-2026-10-18.md), now including complete
four-page suites. The tables below are the 5 October sample.

**Question.** Both modes spend exactly the same loads: `sequential` measures all base loads and
then all PR loads, `abab` alternates them. Does the order change how often an A/A comparison
(no difference by construction) is reported as a regression?

**Data.** Current protocol (see `rq1-preliminary.md`), 2026-09-17 … 10-05: 943 A/A jobs on
GitHub-hosted `ubuntu-24.04`, four pages × two throttling modes × two orders, 51-67 jobs per
configuration, 20 loads per variant (shorter jobs in section 5). Every job is analysed with its **real** base/PR labels and
run order — resampling would shuffle the order away, and the order is exactly what differs.

Code: `analysis/perfgate_analysis/rq3.py`. Reproduce:

```sh
cd analysis
uv run python -m perfgate_analysis.rq3 ../../perfgate-data/raw --out reports/rq3 \
  --warmup 2 --epoch fa45447b5c39 --epoch 467c2a6f9f6c --epoch 12817a1ef4f9
```

## Answer

**Yes. A sequential series raises 2.5-5 times more false alarms, the extra alarms are not
explained away by a minimum effect on TBT, the penalty grows with the length of the job, and
interleaving costs nothing.**

## 1. Per comparison: FCP, LCP and Speed Index

Two-sided Mann-Whitney at α=0.05 on each (job, metric), pooled over pages; 95% Wilson intervals.
"Gate" = significant **and** |effect| > 1%, the rule recommended in `rq2-methods.md`.

| Throttling | Mode | Comparisons | False alarms | Gate fires |
|---|---|---|---|---|
| devtools | abab | 708 | **3.8%** [2.6, 5.5] | 0 |
| devtools | sequential | 705 | **18.9%** [16.2, 21.9] | 9 (1.3%) |
| simulate | abab | 708 | 3.4% [2.3, 5.0] | 1 |
| simulate | sequential | 708 | 8.3% [6.5, 10.6] | 0 |

`abab` stays below the nominal 5% under both throttling modes. `sequential` is 5x worse under
`devtools` and 2.5x worse under `simulate` (Fisher p = 3·10⁻²⁰ and 1·10⁻⁴; the metrics of one job
are correlated, so treat these p-values as descriptive — the job-level test in section 3 is the
valid one).

What the extra false alarms look like: the mean A/A effect is zero in both modes (−0.004% vs
−0.015% under `devtools`), but the effect is spread wider in a sequential job (SD 0.47% vs 0.33%,
Brown-Forsythe p = 0.0004). The rank correlation of the metric with the position in the job is
the same in both modes (median |ρ| ≈ 0.15): the machine drifts during every job. `abab` spreads
that drift evenly over both variants; `sequential` hands it to whichever variant ran second, in a
direction that differs from job to job. The result is not a bias but a stream of small, highly
"significant" differences — almost all of them below 1%, which is why the gate removes most of
them on these metrics.

## 2. TBT: where the gate does not save the sequential design

| Throttling | Mode | Comparisons | False alarms | Gate fires |
|---|---|---|---|---|
| devtools | abab | 118 | 0.0% [0.0, 3.2] | **0.0%** |
| devtools | sequential | 117 | 19.7% [13.5, 27.8] | **17.9%** |
| simulate | abab | 118 | 5.1% [2.4, 10.7] | 3.4% |
| simulate | sequential | 118 | 11.0% [6.6, 17.9] | **11.0%** |

TBT (heavy SPA and SSR pages; the other two have zero TBT) is noisy enough that drift during a
sequential series produces differences of several percent, and those pass a 1% minimum effect.
A team that measures main-thread work and runs base and PR one after another gets a false
"TBT regression" on roughly one PR in five or six, with a gate that looks strict.

## 3. Per pull request: one verdict over all metrics

A PR sees one verdict per job: an alarm if **any** of its metrics is flagged (FCP, LCP, SI and,
where non-zero, TBT). Jobs are independent units, so this is also the valid test between modes.

| Throttling | Mode | Jobs | Any metric, raw | Holm | Holm + 1% gate | BH | BH + 1% gate |
|---|---|---|---|---|---|---|---|
| devtools | abab | 236 | 7.2% [4.6, 11.2] | **1.7%** [0.7, 4.3] | **0.0%** [0.0, 1.6] | 3.0% | 0.0% |
| devtools | sequential | 235 | 30.6% [25.1, 36.8] | **18.7%** [14.3, 24.2] | **7.2%** [4.6, 11.3] | 20.4% | 7.7% |
| simulate | abab | 236 | 7.2% [4.6, 11.2] | 1.3% [0.4, 3.7] | 0.4% [0.1, 2.4] | 2.5% | 0.4% |
| simulate | sequential | 236 | 15.7% [11.6, 20.9] | 7.2% [4.6, 11.2] | 2.5% [1.2, 5.4] | 10.2% | 2.5% |

Fisher test on the Holm-corrected verdict, sequential vs abab: p = 1·10⁻¹⁰ (`devtools`),
p = 0.002 (`simulate`).

Four conclusions for the tool:

1. **Testing several metrics without correction multiplies false alarms**: 7.2% of A/A PRs raise
   at least one alarm even with `abab`, against 3-4% per comparison. Holm brings it back to 1.3-1.7%.
2. **Holm + a 1% minimum effect + `abab` gave one false alarm on 472 A/A PRs (0.2%).** The same
   rule with a sequential series fires on 7.2% (`devtools`) and 2.5% (`simulate`) of PRs.
3. **Holm is the more conservative choice for the merge verdict.** For "is anything
   slower?" on a PR it lets through roughly twice as many alarms as Holm (3.0% vs 1.7%) - it
   controls the share of false discoveries among the flagged metrics, not the chance that a PR
   is blocked at all. With the 1% gate the two are identical. Holm stays the rule for the
   verdict; BH is fine for marking metrics inside a report that is already flagged.
4. **The order is free.** Both modes spend the same loads and the same CI minutes; `abab` only
   changes the order. There is no trade-off to argue about.

## 4. How this changed as data accumulated

| Data | devtools abab | devtools sequential | simulate abab | simulate sequential |
|---|---|---|---|---|
| 2 days (2026-09-17) | 4.2% | 20.8% | — | — |
| 15 jobs/config (2026-09-21) | 5.6% | 16.7% (p=0.031) | 2.2% | 0.0% (n.s.) |
| 24-40 jobs/config (2026-09-27) | 3.1% | 14.4% (p=1.5·10⁻⁸) | 3.6% | 8.9% (p=0.004) |
| 51-67 jobs/config (2026-10-05) | 3.8% | 18.9% (p=3·10⁻²⁰) | 3.4% | 8.3% (p=1·10⁻⁴) |

The `devtools` effect has stayed at four- to five-fold and became unambiguous; the
`simulate` effect, invisible at 15 jobs, appeared at 24-40. The earlier reading "under `simulate`
the order does not matter, because Lantern models the machine away" was wrong: Lantern removes
most of the machine from FCP/LCP, but not all of it, and not from TBT.

## 5. Shorter jobs: the penalty grows with the length of the series

The same jobs cut to a contiguous window of 5 or 10 loads per variant - what a shorter job would
have measured: the first pairs of an `abab` series, the last base loads and the first PR loads of
a sequential one (`--loads N`).

| Loads per variant | devtools abab | devtools sequential | simulate abab | simulate sequential | PR-level, Holm + gate (devtools abab / sequential) | TBT gate fires (devtools sequential) |
|---|---|---|---|---|---|---|
| 5 | 1.7% | 6.7% | 1.8% | 3.3% | 0.4% / 1.3% | 2.6% |
| 10 | 3.3% | **11.8%** | 2.8% | 3.8% | 0.0% / **4.3%** | **14.5%** |
| 20 | 3.8% | **18.9%** | 3.4% | 8.3% | 0.0% / **7.2%** | **17.9%** |

False alarms per comparison on FCP/LCP/SI unless stated. `abab` stays at or below the nominal
level at every length (at n=5 the rank test is conservative because its p-values are coarse).
A sequential series gets worse as it gets longer: the halves are further apart in time, so more
drift falls between them. That is the opposite of what more loads are supposed to buy, and it
means that a team that adds loads to a sequential job to "reduce noise" gets more false alarms,
not fewer.

## Caveats

- One runner type (`ubuntu-24.04`), four demo pages. Shorter jobs in section 5 are windows of
  the 20-load jobs, not separate jobs; the warm-up before them is the same.
- A/A only: the question is false alarms. Detection of real regressions is compared across
  methods in `rq2-methods.md`, on `abab` data.
- The per-comparison rates in sections 1-2 pool correlated metrics of one job; section 3 is the
  independent-unit analysis.
