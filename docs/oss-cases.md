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

## Planned: commit pairs

The second half is a pair of commits of a real application, built from source. It is closer to the
phrase "a regression from open source" and much more fragile to automate: somebody else's install,
somebody else's build, pinned to a commit from months ago. Planned as a small set of curated cases
rather than a sweep, with the case list kept in this file once the first one runs.
