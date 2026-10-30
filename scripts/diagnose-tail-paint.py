"""Post-pilot diagnostic: locate assigned stalls relative to the trace's FCP event."""
import argparse
import csv
import gzip
import json
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('root', type=Path); p.add_argument('--out', type=Path, required=True)
a = p.parse_args(); rows = []
for path in sorted(a.root.rglob('run-*-pr.json')):
    record = json.loads(path.read_text())
    if not record['expected']: continue
    events = json.loads(gzip.decompress(path.with_suffix('.trace.json.gz').read_bytes()))['traceEvents']
    paint = [e for e in events if e['name'] == 'firstContentfulPaint']
    if len(paint) != 1: raise SystemExit(f'Ambiguous FCP: {path}')
    marks = {e['name']: e['ts'] for e in record['evidence']['marks']}
    rows.append({'experiment': record['record']['experimentId'], 'run_index': record['index'],
                 'stall_start_after_fcp_ms': (marks['perfgate-stall-start'] - paint[0]['ts']) / 1000,
                 'stall_end_after_fcp_ms': (marks['perfgate-stall-end'] - paint[0]['ts']) / 1000,
                 'tbt': record['record']['metrics']['tbt']})
if not rows: raise SystemExit('No assigned stalls')
a.out.parent.mkdir(parents=True, exist_ok=True)
with a.out.open('w', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=rows[0].keys()); writer.writeheader()
    writer.writerows(sorted(rows, key=lambda r: (r['experiment'], r['run_index'])))
print(json.dumps({'stalls': len(rows), 'start_before_fcp': sum(r['stall_start_after_fcp_ms'] < 0 for r in rows),
                  'end_before_fcp': sum(r['stall_end_after_fcp_ms'] < 0 for r in rows)}))
