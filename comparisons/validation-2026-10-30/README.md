# Validation pilot, 30 October 2026

Source: c91deb072204fe440e50ffd529deecb7128b1845 (research/comparison-mvp).
The candidate was frozen before these measurements; protocol.json contains exact source hashes.

- prospective: 1,320 measured loads / 33 jobs, workflows 40974119962 and 40974124046; store=false. No failed loads or invalid jobs. One four-page A/A suite is quiet. This is a pilot, not the completed confirmatory cohort.
- local: 60 measured loads, two A/A checks and one injected script-delay check.
- refs: 20 measured loads, same-commit comparison through independent builds; cleanup_issues is empty.
- action-smoke: 40 measured loads, hosted Action A/A and injected checks (workflow 40973404648).

Raw JSONL is copied byte-for-byte. Absolute workstation/temporary paths in JSON metadata are replaced by placeholders. Logs are omitted. These additional adapter/timing fields require the source revision above, rather than the old main-branch schema.

Reproduce the prospective summary from a checkout of that source plus scripts/summarize-pilot.py in the validation follow-up commit:

```sh
PYTHONPATH=analysis analysis/.venv/bin/python scripts/summarize-pilot.py /path/to/this/archive/prospective --out /tmp/pilot-analysis
```

Inspect prospective/analysis/jobs.csv: nominal injection labels do not guarantee the measured target effect. In particular, nominal +25% layout-shift measured only +0.25% CLS in this pilot. A +5% long-task page alarm came from LCP, not TBT. Do not count these as successful target detections.

This archive deliberately lives outside raw/ and is not automatically added to the historical discovery corpus.
