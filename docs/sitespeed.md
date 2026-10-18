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
fail the job. Artifacts retain the raw samples for 90 days. Copy those artifacts to
the `data` branch before they expire; the paper's tables must cite that snapshot.

Three repetitions establish that the comparison runs and show the observed cases.
They do not estimate a reliable population false-positive rate or prove that one
tool is generally more sensitive. Longer replication belongs to the October–November
experiment stage.

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
