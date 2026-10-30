# Exploratory CLS trace diagnosis

48 complete cold-load traces: 32 measured loads and 16 warmups. Two platforms
(macOS local and Linux CI), two pages (original heavy and reserved-stats control),
64 px baseline banner versus 96 px treatment banner, four alternating measured
pairs after two warmups per variant. This is a mechanism diagnostic, not a
confirmatory error-rate/power cohort. The frozen browser detector is unchanged.

Hosted run: https://github.com/SlavaDoroshenko/perfgate/actions/runs/41009688374
Its merge source SHA is recorded in each manifest; the exact hosted diagnostic
script is saved in source/diagnose-cls-hosted.mjs. The later local-control script
adds HTTP readiness and failure metadata, without changing Lighthouse options.
The original local prototype predates script-hash metadata; its recorded git SHA
identifies the unchanged app/collector checkout, not the then-uncommitted diagnostic
script. Do not claim exact script-hash provenance for that original local series.

Two setup attempts were aborted before usable trace acquisition: the original
prototype initially used an obsolete artifact property, and the first local
control attempt returned HTTP 404 because the static server indexed files before
the control page was created. The server was restarted; all fixed-size series
shown here then completed. The final tool checks HTTP readiness before launching
Chrome and retains runtime failures in its manifest. These are disclosed setup
failures, not discarded high-CLS observations.

Each per-load JSON contains raw LayoutShift events and DOM selectors, plus compressed
full Lighthouse traces and reports. Summary CSV/JSON separates warmups. Across this
specific dataset, reported CLS equals the sum of non-recent-input weighted event
scores; this is not a replacement implementation of session-window CLS.

Reproduce from the perfgate checkout:

```sh
python3 scripts/summarize-cls-traces.py /path/to/archive/local-original --out /tmp/cls-summary
```

ERRATUM to comparisons/validation-2026-10-30: the small aggregate median change
for nominal +25% CLS does not establish an injector failure. The lower mode moved
about +25%, while changed mode occupancy masked it in the aggregate median. The
original gate miss remains unchanged. report.md distinguishes direct observations
from the inferred explanation of the historical Linux upper mode.
