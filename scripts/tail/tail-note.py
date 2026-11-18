"""Advisory rare-long-task note for a perfgate report directory (tail.json).

Applies the tail signal of scripts/tail_signal.py, unchanged, to the loads of one
comparison: per page, one-sided Welch t-test on TBT, Holm over the pages, a warning
when the adjusted p < 0.05 and mean TBT rose by more than max(10%, 20 ms). The note
never changes the verdict. Evaluation: docs/extensions-2026-11-18.md (no warning on
500 unchanged checks; 67 of 100 jobs with 3 of 20 stalled loads warned).

Usage: python tail-note.py REPORT_DIR   (the --out directory of perfgate compare or
compare-refs). Exit code 0 also when there is nothing to report.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tail_signal import ABSOLUTE_MS, ALPHA, RELATIVE, tail_signal  # noqa: E402


def runs_file(directory: Path) -> Path | None:
    for candidate in (directory/'runs.jsonl', directory/'comparison'/'runs.jsonl'):
        if candidate.is_file():
            return candidate
    return None


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 3
    runs = runs_file(Path(sys.argv[1]))
    if runs is None:
        print('tail note: no runs.jsonl, skipped', file=sys.stderr)
        return 0
    loads = {}
    for line in runs.read_text().splitlines():
        r = json.loads(line) if line.strip() else None
        if not r or r.get('error') or (r.get('metrics') or {}).get('tbt') is None:
            continue
        loads.setdefault(r['app'], {'base': [], 'pr': []})[r['variant']].append(float(r['metrics']['tbt']))
    pages = {app: (np.array(v['base']), np.array(v['pr'])) for app, v in loads.items()
             if len(v['base']) >= 5 and len(v['base']) == len(v['pr'])}
    out = {'schema': 'perfgate-tail/1', 'rule': {'test': 'one-sided Welch t-test on TBT, Holm over pages',
                                                  'alpha': ALPHA, 'relative': RELATIVE, 'absolute_ms': ABSOLUTE_MS},
           'pages': []}
    if pages:
        for app, row in tail_signal(pages).items():
            base, pr = pages[app]
            out['pages'].append({'name': app, 'n': len(base), 'base_mean': row['base_mean'], 'pr_mean': row['pr_mean'],
                                 'base_median': float(np.median(base)), 'pr_median': float(np.median(pr)),
                                 'p_holm': row['p_holm'], 'warning': row['warning']})
    target = runs.parent/'tail.json'
    target.write_text(json.dumps(out, indent=2, allow_nan=False) + '\n')
    warned = [p['name'] for p in out['pages'] if p['warning']]
    print(f'tail note: {", ".join(warned) if warned else "no warning"} ({target})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
