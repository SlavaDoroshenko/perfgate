# Frozen rare-stall browser pilot

Main acquisition: workflow 41035614668, source d1b45e8; six hosted jobs plus one
local rare job. Source freeze identifies 5a18138 and exact acquisition/analysis
hashes. Main dataset: 280 measured loads + 28 clean warmups, seven valid jobs,
49 assigned stalls verified in traces. Conditions/seeds/counts were fixed before
main acquisition. The preceding four-load instrumentation smoke is separate and
must not be included in the main pilot.

All scheduled slots and failures are retained. There were no failed main-pilot
loads. One dense-control stall ended before FCP; the observation remains in the
analysis and is documented as a treatment/metric-window limitation. No candidate
threshold, sample size or assignment was changed after inspecting results.

The browser candidate missed all three rare cases while their measured mean TBT
increased 22–33% and the median stayed nearly unchanged. It detected both dense
controls and was quiet in both A/A jobs. Welch alone among the twelve exploratory
TBT rules flagged all three rare jobs; this small pilot cannot establish method
superiority or estimate power. See report.md and analysis/ for all outcomes.

Raw JSONL is compatible with the frozen project schema. Every load has compact
execution evidence and compressed LHR; full traces are retained for assigned stalls
and the first measured pair. The main/ directory is the analysis input. Artifacts
outside main/ are not additional independent trials. Original main records are
copied byte-for-byte; file checksums are in sha256.json.

From the perfgate checkout with analysis dependencies installed:

```sh
PYTHONPATH=analysis analysis/.venv/bin/python scripts/analyze-tail.py /path/to/archive/main --out /tmp/tail-analysis --freeze /path/to/archive/protocol.json
python3 scripts/diagnose-tail-paint.py /path/to/archive/main --out /tmp/stall-paint-timing.csv
```

The archived source/ tree preserves the exact frozen sources and later plotting/
post-pilot diagnostic scripts. It is not a complete independently installable repo;
use the committed project/dependency locks for reproduction. This archive lives
outside raw/ to keep it separate from historical and primary confirmatory cohorts.
