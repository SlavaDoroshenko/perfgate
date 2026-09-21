# Real changes from open source

Injected regressions have a known size, which is what makes them useful for measuring power.
They are also idealised: a multiplicative shift of one metric, authored by the experiment itself.
This file covers the other half — changes written by other people, where nobody knows in advance
whether the page got slower, and by how much.

## Why library releases first

Upgrading a dependency is the most common way a frontend gets slower without anyone writing slow
code. The change is real, published, and reproducible: two releases of the same package on npm,
built into the same page with the same build tooling. Compared with building two commits of a
third-party application, this removes the part that breaks most often — somebody else's install
and build — while keeping the part that matters: real code written by a real team.

`apps/vendor-bench` builds three workloads twice, once against an older release ("a") and once
against a newer one ("b"):

| Case | Library | a | b | What the page does |
|---|---|---|---|---|
| `marked` | marked | 9.1.6 | 18.0.13 | parses a ~300-section markdown document into HTML |
| `chart` | chart.js | 3.9.1 | 4.5.1 | renders a 2000-point, two-series line chart into a canvas |
| `dates` | date-fns | 2.30.0 | 4.4.0 | formats 4000 dates in four patterns, renders 400 rows |

Both variants are served side by side (`/a/<case>.html` and `/b/<case>.html`) and measured as one
comparison, exactly like a base/PR pair. Records carry `label: vendor`, so these comparisons never
enter the A/A false alarm statistics.

Collected by `.github/workflows/oss.yml`, twice a day, `abab`, both throttling modes.

## A lesson from the first attempt

The first run of this bench measured nothing at all. The pages are served from `/a/` and `/b/`,
Vite emitted absolute asset urls (`/assets/...`), every script returned 404, and both variants
rendered an empty page — equally fast, and indistinguishable. Nothing in the measurement complained.

Two fixes followed: relative asset urls, and a `failedRequests` count in every record. A page that
fails to load its own script is not a fast page, and a bench that cannot tell the difference is
not a bench. Any analysis should drop loads with `failed_requests > 0`.

## First results

On GitHub runners, 20 pairs of loads per case, `abab`, both throttling modes
(run 35584462831, 240 loads, no failed loads, no failed requests):

| Case | Metric | `devtools` | `simulate` |
|---|---|---|---|
| marked 9.1.6 → 18.0.13 | LCP | **+5.3%** (p=1e-7) | **+12.3%** (p=7e-8) |
| marked 9.1.6 → 18.0.13 | TBT | **+11.4%** (p=1e-4) | **+14.4%** (p=1e-6) |
| chart.js 3.9.1 → 4.5.1 | TBT | −17.7% (p=7e-8) | −20.0% (p=1e-7) |
| date-fns 2.30.0 → 4.4.0 | TBT | −16.5% (p=7e-8) | −25.0% (p=6e-3) |
| all three | FCP | ±0.4%, not significant | ±0.1%, not significant |

Locally (Apple M5, 5 pairs) the same directions appeared, with chart.js not yet separable from
noise at that sample size (p=0.15) — five pairs resolve a 15% difference only sometimes, twenty
resolve it with certainty.

Three real upgrades, three different answers: one clear regression, two clear improvements. That
mix is the point — a detector has to be right in both directions.

The marked case is a genuine find: a page that parses a large markdown document spends 11-14% more
blocking time on version 18 than on version 9 and paints its largest element 5-12% later. Nothing
about that is visible in a changelog.

Two observations for the other questions:

- **FCP moves in none of the cases**, because in all three workloads the library runs after the
  first paint. A budget on FCP alone would have missed every one of them.
- **`simulate` reports larger effects than `devtools` here** (+12.3% vs +5.3% LCP for marked).
  Lantern multiplies measured CPU time, so it amplifies main-thread differences — the same
  modelling that made it blind to the timer-driven `lcp-delay` injection. Neither mode is
  "conservative"; they are wrong in different directions.

## Commit pairs of real applications

The second half: somebody else's application, built from source at two refs. `oss/cases.json`
lists the cases and `scripts/build-commit-pair.mjs` clones, installs and builds each side, putting
both dist trees where the bench can serve them side by side. The built pair is cached in CI by case
and refs, so a failure to rebuild a months-old commit shows up as a failed job rather than as
silently missing data.

| Case | App | before → after | What it is |
|---|---|---|---|
| `phanpy-exclude-xmldom` | Phanpy (Mastodon client) | `edefb58a` → `c65eb596` | one line in `vite.config.js` excluding xmldom from the bundle |
| `phanpy-may-to-june` | Phanpy | `2026.05.21` → `2026.06.23` | two dated release snapshots a month apart |
| `phanpy-june-to-august` | Phanpy | `2026.06.23` → `2026.08.08` | the following snapshot pair |
| `excalidraw-0.17.6-to-0.18.0` | Excalidraw | `v0.17.6` → `v0.18.0` | a minor release of a drawing app |

Why these: both apps build from a plain `npm ci` / `yarn install` and a single build command, both
are real products rather than demos, and Phanpy publishes dated snapshots, which gives a supply of
real consecutive versions without having to argue about which commit is interesting.

### Results on the runners (20 pairs per case, both throttling modes)

| Case | Metric | `devtools` | `simulate` |
|---|---|---|---|
| `phanpy-may-to-june` | FCP | **+3.84%** (p=7e-8) | **+3.83%** (p=7e-8) |
| `phanpy-may-to-june` | LCP | **+4.15%** (p=7e-8) | **+3.95%** (p=7e-8) |
| `phanpy-may-to-june` | TBT | +15.8% (p=2e-4) | +50% of 2 ms (p=9e-3) |
| `phanpy-june-to-august` | LCP | **+0.87%** (p=3e-6) | +0.01% (p=0.46) |
| `phanpy-june-to-august` | FCP | −0.14% (p=0.04) | +0.00% (p=0.56) |
| `phanpy-june-to-august` | TBT | −5.5% (p=0.01) | +372% of 4.5 ms (p=6e-8) |
| `phanpy-exclude-xmldom` | FCP / LCP | +0.02% (p=0.39) | −0.01% / +0.88% |
| `phanpy-exclude-xmldom` | TBT | +6.8% (p=0.15) | 0.0% (p=0.30) |

**May → June is a solid regression.** About 4% on both paint metrics, identical under both
throttling models, reproduced on the runners and locally on an Apple M5. Over the same month the
build output shrank from 12 MB to 10 MB, so a bundle-size check would have reported an improvement
while the page got slower.

**June → August shows what 20 loads buy.** LCP moved by 0.87% — under a percent — and the test
still separates it from noise with p=3e-6 (11343 ms → 11442 ms). That is the sensitivity promised
by the MDE tables in `rq1-preliminary.md`, on a real application rather than a demo.

**The xmldom case did not replicate.** Locally, 8 pairs gave TBT 55 ms → 47 ms, −14.2% with
p<0.001. On the runners, 20 pairs gave +6.8% with p=0.15 — the opposite sign, not significant.
Paint metrics did not move in either place. So the honest statement is: removing 64 KB of
JavaScript that was not on the critical path had no effect we can demonstrate, and the local
result was a property of that machine rather than of the change. An effect that survives p<0.001
on one laptop and disappears on other hardware is exactly the trap this whole project is about.

**TBT under `simulate` is a few milliseconds, and relative framing lies.** June → August reports
+372% under `simulate` — that is 4.5 ms against 21.2 ms — while `devtools` reports −5.5% of 29 ms
in the opposite direction. On a page where blocking time is near zero, the two throttling models
disagree even about the sign. Relative thresholds on TBT are meaningless at that scale; this metric
needs an absolute floor, like "ignore anything below 50 ms".

## What broke while setting this up

- **The Excalidraw case failed, and it was our bug, not theirs.** At tag v0.17.6 the project had no
  `packageManager` field yet, so corepack walked up the directory tree, found *our* repository root
  and tried to run `yarn@pnpm@11.7.0`. Foreign checkouts now live outside this repository
  (`os.tmpdir()`), and the build runs with `COREPACK_ENABLE_STRICT=0`. A nested checkout inherits
  more from its host than it looks.
- **A real application cannot be served from a subdirectory.** Excalidraw is built with absolute
  asset urls (`/assets/...`), so serving it at `/<case>/before/` returned 404 for every asset and
  all 40 loads came back as `NO_FCP` — the page painted nothing. Each side now gets its own port
  (4178 and 4179) and is served from its own root. Note what worked: the measurement did not report
  a fast blank page, it reported 40 failed loads and the job failed.
- **Excalidraw needed three fixes before it built at all**: yarn pinned through `npx` (the case
  must build on a machine that has no yarn), a different `dist` path per side (the app moved from
  `build/` to `excalidraw-app/build/` between the two tags), and Node 18-22 (the tag predates
  Node 24, so the pair builds in CI but not on a laptop running a newer Node). Reproducing somebody
  else's application at a year-old tag is consistently harder than measuring it.
- The first build of a pair failed with a bare exit code in the middle of somebody else's
  `npm ci`. The script now names the step, the command and the directory.
- A local run produced 16 loads in a row with `CHROME_INTERSTITIAL_ERROR` because the static server
  was not running. All 16 were recorded as failed loads rather than as numbers. The CI job waits
  for the server to answer before measuring.
