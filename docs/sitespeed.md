# Measured comparison with sitespeed.io

The comparator runs the actual sitespeed.io 42.9.0 / Browsertime 28.4.0 collectors and
the built-in compare plugin. It does not substitute our Mann–Whitney implementation
for theirs. Dependencies are pinned in `scripts/sitespeed/package-lock.json`.

## Protocol

Run `.github/workflows/sitespeed.yml` manually. Nine independent GitHub jobs cover
three cases × three repetitions: identical heavy pages (A/A), `script-delay:36`
(nominal +2% FCP) and `long-task:99` (nominal +10% TBT). Each job runs both tools on
the same runner, Chrome 153.0.8010.47 and demo build. The tool that runs first
alternates across repetitions. Tools never measure concurrently within a job.

Each tool gets ten measured loads per variant and two unrecorded warm-ups per
variant. Sitespeed saves a fresh baseline in that job and measures base then PR;
Lighthouse uses the project's `abab` protocol. The sitespeed compare plugin keeps
its default one-sided Mann–Whitney test (`auto`, no continuity correction). The
captured `compare.json` includes its actual verdict, p-value, Cliff's delta,
Hodges–Lehmann interval and the raw samples. This is an end-to-end tool comparison;
collector and ordering differences are part of it, not a controlled comparison of
statistical tests alone.

CPU throttling is 4×, screen emulation is 412×823 at DPR 1.75 with the Lighthouse
mobile UA. Chrome uses the same `--no-sandbox` and `--disable-gpu` flags as the
existing Lighthouse collector (the former is needed on Ubuntu hosted runners).
`throttle.mjs` applies Lighthouse's request-level DevTools latency and
throughput before navigation. No video, visual metrics or profiling run is enabled.
The screenshot and observer overheads of the tools still differ. Their TBT
collection windows also differ; absolute TBT values are not interchangeable.

`metadata.json` records versions, CPU, order, workload fingerprint and wall time
(including warm-up and tool overhead). Missing measurements or browser failures
fail the job. Artifacts retain the raw samples for 90 days; the dated report also
archives them on the `data` branch under `comparisons/sitespeed/39149657629/`.
The immutable archive is
[`ed9f207`](https://github.com/SlavaDoroshenko/perfgate/tree/ed9f2072af867ae38be02097fffb6d84b89a5917/comparisons/sitespeed/39149657629),
including a manifest with source commit and file checksums.

Three repetitions establish that the comparison runs and show the observed cases.
They do not estimate a reliable population false-positive rate or prove that one
tool is generally more sensitive. Longer replication belongs to the October–November
experiment stage.

## Pilot results, 18 October 2026

[Run 39149657629](https://github.com/SlavaDoroshenko/perfgate/actions/runs/39149657629)
completed all nine jobs: 180 measured loads per tool, 360 in total, with no collector
failures; Lighthouse also reported no failed requests. The tables cover the four common metrics
FCP/LCP/TBT/CLS; sitespeed's other compare metrics are outside this aggregation.

| Case / target | Sitespeed median effect | Lighthouse median effect | Target detected, sitespeed / Lighthouse |
|---|---:|---:|---:|
| FCP nominal +2% | +1.97% | +1.85% | 3/3 / 3/3 |
| TBT nominal +10% | +45.85% | +8.40% | 3/3 / 3/3 |

Both target results survive Holm across the four metrics and a minimum effect of
1% for FCP/LCP, 5% for TBT or 0.005 absolute CLS. This is our **post-processing**
policy applied to both tools, not the native sitespeed verdict. The unadjusted
one-sided sitespeed compare result flags at least one common metric in 2/3 A/A
jobs; our one-sided MWU on Lighthouse samples flags 0/3. Holm plus the margins
flags 0/3 for each tool. Three A/A jobs are insufficient to estimate rare false
alarms or rank the tools reliably.

Sitespeed takes about 298 seconds per comparison, Lighthouse 440–441 seconds,
including warm-ups and overhead. Equal load counts therefore do not mean equal
CI time. The large TBT effect difference is consistent with different collection
windows and baselines; it does not imply that sitespeed measured the same quantity
more accurately. This end-to-end pilot also changes run order with the tool.

The runner image was fixed, but the recorded CPU model varies (EPYC 7763 and
9V74). Each pair of tools shares its runner. Tool order has two sitespeed-first
and one Lighthouse-first repetition; more repetitions should balance that order.

[Per-metric results](results/2026-10-18/sitespeed_comparisons.csv) and
[versions, CPU and timing](results/2026-10-18/sitespeed_metadata.csv) are committed.
To regenerate them from the archived comparison directory:

```sh
cd analysis
uv run python -m perfgate_analysis.tool_comparison \
  ../../perfgate-data/comparisons/sitespeed/39149657629 --out reports/sitespeed
```

## Reproduce locally

Build and serve `demo-spa`, then:

```sh
npx --yes npm@11.13.0 ci --prefix scripts/sitespeed
uv sync --locked --directory analysis
PYTHON="$PWD/analysis/.venv/bin/python" \
  CHROME_PATH=/path/to/chrome RUNS=10 CASE=fcp2 REPEAT=1 \
  node scripts/sitespeed/run.mjs
```

The browser must match the installed ChromeDriver major (153). `RESULT_DIR` selects
the output directory. The browser and the demo server should stay fixed throughout
a comparison.

Sources: [sitespeed configuration](https://www.sitespeed.io/documentation/sitespeed.io/configuration/),
[browser setup](https://www.sitespeed.io/documentation/sitespeed.io/browsers/), and the
installed `lib/plugins/compare` sources for version 42.9.0. Lighthouse constants are
read from the pinned 13.4.1 package in the project lockfile.
