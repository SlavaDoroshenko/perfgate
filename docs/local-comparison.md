# Local A/A pilot versus GitHub runners, 18 October 2026

Three local jobs on Apple M5 / macOS completed **60 valid loads**, with no failed
audits or reported failed requests. They use the heavy page, app build
`fa45447b5c39`, Chrome for Testing 153.0.8010.47, Lighthouse 13.4.1, `devtools`,
`abab`, two warm-ups and ten measured loads per variant.

The CI comparator uses the same page, build, browser version and protocol from
data snapshot `103b1363befd1cb62a6a03cab41641fc1cbb74f5`. Taking the first ten loads
of each variant leaves **109 complete jobs / 2,180 loads**. Incomplete jobs or jobs
with a failed load in the selected sample are excluded. This matches sample sizes
without mixing in sequential or simulated-throttling runs.

## Observed noise and resampled sensitivity

Within-job noise is the median over jobs of `1.4826 × MAD / median`. MDE is the
smallest multiplicative shift detected in at least 80% of within-job resamples by
a one-sided Mann–Whitney test at 0.05. It has no effect margin or Holm correction.

| Metric | Within-job noise, CI | Within-job noise, local | Resampled MDE, CI | Resampled MDE, local |
|---|---:|---:|---:|---:|
| FCP | 0.44% | 0.49% | 0.75% | 1% |
| LCP | 0.58% | 0.37% | 1% | 0.75% |
| TBT | 1.69% | 1.09% | 3% | 2% |

This local session shows comparable within-job FCP variation and lower LCP/TBT
variation. It does not establish that a laptop is generally more stable. The
three jobs span only about twenty minutes, while CI spans 17 September–18 October
and several CPU models. Between-job coefficients of variation (CI / local) are
2.27% / 0.32% for FCP, 4.20% / 0.45% for LCP and 16.52% / 0.26% for TBT; the unequal
time spans and hardware populations are part of that difference.

This was an ordinary desktop session with background applications open. No other
perfgate report, build or test ran during collection. It is a pilot, not an idle
machine benchmark or an isolated estimate of the effect of the CPU. Resampling
three jobs does not produce hundreds of independent experimental repetitions.
The exported false-alarm rates describe resampling, not a precisely estimated
deployment error rate. CLS is retained in descriptive tables but excluded from
relative MDE estimates; a zero MAD on its repeated values does not imply no noise.

All three collector processes finished successfully. The shell wrapper's final
status-print command failed after collection because the script was edited while
running. The archived manifest records its exit code 127; subsequent schema and
completeness checks verified all sixty records. The current wrapper passes shell
syntax validation.

## Data and reproduction

Raw local records, environment metadata and checksums are archived at
[`ed9f207`](https://github.com/SlavaDoroshenko/perfgate/tree/ed9f2072af867ae38be02097fffb6d84b89a5917/raw/local/2026-10-18).
Compact outputs: [noise](results/2026-10-18/local_noise.csv),
[within/between](results/2026-10-18/local_within_between.csv),
[per-job comparisons](results/2026-10-18/local_jobs.csv),
[power curves](results/2026-10-18/local_power.csv),
[MDE](results/2026-10-18/local_mde.csv).

With separate data checkouts at the two SHAs above, from `analysis/`:

```sh
uv run python -m perfgate_analysis.local_comparison \
  /path/to/ci-snapshot/raw/*/*-aa-demo-heavy-abab-devtools.jsonl \
  /path/to/pilot-snapshot/raw/local/2026-10-18 --out reports/local
```

For a new pilot, set `CHROME_PATH` to the pinned browser and run:

```sh
THROTTLINGS=devtools MODES=abab PAGES=demo-heavy scripts/local-aa.sh 3 10
```

Keep the script and built app fixed until it exits. More days, pages, throttling
modes and machines are needed before using this result to choose deployment hardware.
