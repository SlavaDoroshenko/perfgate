# External pilot: twelve real Phanpy changes through the frozen candidate

6 November 2026. Workflows `external-pilot.yml` and `external-aa.yml` on `main`;
analysis `scripts/external-pilot.py`; tables in
[results/2026-11-06/external-pilot](results/2026-11-06/external-pilot/) and
[external-aa](results/2026-11-06/external-aa/). Raw data: `pilot/` on the data branch.

## Design

[Phanpy](https://github.com/cheeaun/phanpy), a Mastodon web client, commits to `main`
directly, so a commit against its first parent stands for one merged PR. From its 40
latest app-code commits (21 October – 6 November 2026) twelve were chosen: all five
dependency upgrades and seven feature/style changes. Each pair was built from scratch
in CI and measured with the frozen candidate protocol (abab, devtools, two warmups, 20
loads, Chrome 153), twice, in two separate workflow runs on different runners. Controls: the
same commit built twice, independently — two commits × two runs, then eight more jobs
of one commit, half of them with the two builds' ports swapped.

There is no ground truth here: the pilot shows which changes each rule would have
blocked and whether that verdict repeats, not detection power.

## Verdicts

| Rule | Changes blocked (2 × 12) | Same-commit controls blocked |
|---|---:|---:|
| single load >5% | 10/24 | 4/12 |
| median of 3 >5% | 9/24 | 1/12 |
| median of 20 >5% | 5/24 | 2/12 |
| candidate | 6/24 | 1/12 |

Almost every threshold alarm comes from TBT. On this page TBT is 2–36 ms, so a 4 ms
difference is +21%; the candidate's 5 ms absolute floor keeps it quiet, the relative
thresholds do not.

The candidate flagged four changes in the first run and two in the second:

| Change | Run 1 | Run 2 |
|---|---|---|
| `624fa08b` Upgrade deps (lingui 6.12, mingcute icons 3.1, p-retry 9, …) | FCP +3.3%, LCP +1.4% | FCP +3.2%, LCP +2.7% |
| `91986a90` Revamp whole icons logic | FCP +2.5%, LCP +2.0% | FCP +2.5%, LCP +2.0% |
| `51223533` Upgrade deps | LCP +1.3% | quiet (LCP +0.04%) |
| `96e1f784` Upgrade deps (preact 11.1) | LCP +1.2% | quiet (LCP +0.01%) |

The two FCP regressions repeated with nearly identical sizes on different CPU models.
The two LCP-only verdicts did not.

## The one control alarm

One same-commit job (run 2 of `624fa08b`) was flagged: LCP +1.17%. The whole PR
sample sat about 140 ms above the base sample (LCP ≈ 11.8 s; both samples tight, no
overlap), so this was a systematic per-side offset inside one job, not noise in a few
loads. Offsets of the same size appear in the non-replicating verdicts above (+1.2%,
+1.3%) and once with the opposite sign (`a7362255`, run 1: −1.17%).

What it is not:

- **Not the code.** Two local builds of `624fa08b` differ only in the embedded build
  time and the resulting chunk hashes; file sizes are byte-identical, gzip sizes
  differ by 2 bytes.
- **Not the port or server.** Eight further same-commit jobs, four with the builds'
  ports swapped, were all quiet; median LCP differences were within ±10 ms.

So a discrete ~140 ms LCP offset hits roughly one job in nine on this app
(observed in 4 of 36 Phanpy jobs). It is just above the 1% LCP margin.
Candidate false alarms on external same-commit controls: 1/12 (Wilson 95%: 1.5–35%).

## Trace of the offset (added 11 November)

Sixteen more same-commit jobs of `624fa08b` (`external-lcp-trace.yml`, run
42267470785; `scripts/diagnose-lcp.mjs`, same protocol as a candidate job) kept the
LCP element, its subparts and every request of every load. Data:
`pilot/lcp-trace/2026-11-06/` on the data branch.

- The offset recurred in 2 of 16 jobs: −1.16% (base slower by 138 ms) and +1.04%
  (PR slower by 122 ms). The other 14 jobs were within ±0.09%.
- The LCP element is the same lazy hero image in every load. The whole difference is
  in `resourceLoadDuration` (2274 vs 2137 ms; 2272 vs 2136 ms); TTFB, load delay
  and render delay are equal.
- In both jobs the slower side is the one whose `dom-*.js` chunk is transferred over
  the network: 56,017 bytes in all 20 loads of that side, starting at ~10.3 s while
  the hero image downloads. In the other 30 of 32 builds the same request transfers
  0 bytes. At the devtools throughput of 1.6 Mbit/s, 56 KB is ~270 ms of link
  time; shared with the image it delays the image by ~135 ms, and the concurrent
  tablet image and `compose` chunk by ~300 and ~160 ms, which matches the trace.

**Correction, 17 November.** An earlier version of this section concluded that the
build is nondeterministic. It is not. Sixteen jobs each building `624fa08b` twice
(`external-builds.yml`, run 43962268547, compared with `scripts/assets/diff.mjs`;
data in `pilot/phanpy-builds/` on the data branch) found the two builds identical in
every pair except `main-*.js` (a few bytes of embedded build time) and `version.json`.
The `dom` chunk has the same content in every build; only its content hash in the
file name differs.

The file name is what matters. The two slow sides are the only 2 of the 32 traced builds
whose `dom` chunk hash contains an underscore (`dom-_Aqan-22.js`, `dom-3mzK_nIF.js`).
Phanpy's service worker (`public/sw.js` at this commit) routes hashed scripts and
styles to its asset cache only if the URL matches `/-[0-9a-z-]{4,}\./i`. That class
has no `_`, although Rollup hashes use the URL-safe alphabet including `_`. A chunk
whose hash contains an underscore therefore bypasses the service worker and is
fetched by the page itself, under the page's throttled network, at the moment the hero
image downloads; requests the service worker answers show 0 transferred bytes in the
page's network log. The likely reason the bypass costs time in the lab is that
DevTools network throttling applies to the page's requests, not to the service
worker's own fetches; this part was not tested separately.

So the alarm reflects a real, if small, behaviour of the application (assets whose
hash contains `_` are not handled by its asset cache), triggered by an arbitrary
hash, not noise in the measurement. Reported upstream as
[cheeaun/phanpy#1634](https://github.com/cheeaun/phanpy/issues/1634), fix proposed in
[#1635](https://github.com/cheeaun/phanpy/pull/1635). Two further traced jobs (4 and 14) show the same
56 KB transfer in single loads with ordinary hashes, consistent with loads where the
service worker did not yet control the page.

For users this means a same-commit LCP alarm can be correct and still surprising.
The comment now shows which built assets differ between base and PR next to the
verdict; here it would show identical builds, which points the investigation away
from the code and towards how the files are served.

## Consequences

The frozen candidate is not changed. For deployment and for the thesis:

1. On a real application, an LCP-only alarm of about 1–1.5% needs
   confirmation before it blocks a merge: either re-measure on alarm, or keep the
   gate advisory for LCP-only verdicts. A candidate policy that does this must be
   frozen and evaluated as a new candidate, not retrofitted to these jobs.
2. FCP/LCP regressions of 2.5–3.3% from real changes were detected and repeated —
   the size range the thresholds cannot see (5% budget).
3. Repeating every pilot pair at least twice is what exposed the problem; one run per
   pair would have reported four regressions and no reproducibility question.

Next: more same-commit jobs on Phanpy to estimate the external false-alarm rate with
a useful interval.
