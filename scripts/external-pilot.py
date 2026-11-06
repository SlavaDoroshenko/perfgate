"""External pilot: verdicts of the frozen candidate and of fixed-threshold checks on real Phanpy changes.

Each job compares one commit with its first parent (or a commit with itself, A/A).
There is no ground truth: the table shows which changes each rule would have blocked.
"""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
from perfgate_analysis.compare import compare_frame
from perfgate_analysis.load import load_runs
from perfgate_analysis.methods import single_run, threshold

ROOT = Path(__file__).resolve().parents[1]
METRICS = ('fcp', 'lcp', 'tbt', 'cls')
BEFORE = {'single load >5%': (single_run(.05), 1), 'median of 3 >5%': (threshold(.05), 3),
          'median of 20 >5%': (threshold(.05), 20)}

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('data', type=Path, help='pilot/external-phanpy/ directory of the data branch')
p.add_argument('--out', type=Path, required=True)
p.add_argument('--freeze', type=Path, default=ROOT/'docs/protocols/browser-candidate-2026-10-30.json')
args = p.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
freeze = json.loads(args.freeze.read_text())
if [n for n, d in freeze['source_sha256'].items() if hashlib.sha256((ROOT/n).read_bytes()).hexdigest() != d]:
    raise SystemExit('Frozen sources changed')
files = sorted(args.data.rglob('*.jsonl'))
df = load_runs(files)

rows = []
for exp, g in df.groupby('experiment'):
    g = g.sort_values('order')
    pair = exp.split('pilot-phanpy-')[1].removesuffix('-abab-devtools')
    r = compare_frame(g, 20)
    row = {'pair': pair, 'aa': pair.startswith('aa-'), 'app_build': g.app_build.iloc[0],
           'cpu_model': g.cpu_model.iloc[0], 'candidate': r['status'],
           'candidate_flagged': ';'.join(m['name'].split('/')[-1] for m in r['metrics'] if m['regression']),
           'issues': '; '.join(r['issues'])}
    for m in r['metrics']:
        name = m['name'].split('/')[-1]
        row[f'{name}_rel'] = m['relative_effect']
        row[f'{name}_abs'] = m['absolute_effect']
    if r['status'] != 'invalid':
        for rule, (method, k) in BEFORE.items():
            fired = []
            for metric in METRICS:
                b = g.loc[g.variant == 'base', metric].to_numpy(float)[:k][None, :]
                pr = g.loc[g.variant == 'pr', metric].to_numpy(float)[:k][None, :]
                if method(b, pr)[0]:
                    fired.append(metric)
            row[rule] = ';'.join(fired) or '-'
    rows.append(row)
jobs = pd.DataFrame(rows).sort_values(['aa', 'pair'])
jobs.to_csv(args.out/'jobs.csv', index=False)
valid = jobs[jobs.candidate != 'invalid']
summary = pd.DataFrame([{'rule': rule, 'changes_blocked': int((valid[~valid.aa][rule] != '-').sum()),
                         'changes': int((~valid.aa).sum()), 'aa_blocked': int((valid[valid.aa][rule] != '-').sum()),
                         'aa': int(valid.aa.sum())} for rule in BEFORE] +
                       [{'rule': 'candidate', 'changes_blocked': int(valid[~valid.aa].candidate.eq('regression').sum()),
                         'changes': int((~valid.aa).sum()), 'aa_blocked': int(valid[valid.aa].candidate.eq('regression').sum()),
                         'aa': int(valid.aa.sum())}])
summary.to_csv(args.out/'summary.csv', index=False)
(args.out/'manifest.json').write_text(json.dumps({
    'policy': freeze['policy'], 'loads': len(df), 'jobs': int(df.experiment.nunique()),
    'invalid_jobs': int((jobs.candidate == 'invalid').sum()), 'failed_loads': int((~df.ok).sum()),
    'data_from': str(df.timestamp.min()), 'data_through': str(df.timestamp.max()),
    'files_sha256': {str(f.relative_to(args.data)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}},
    indent=2) + '\n')
pd.set_option('display.width', 250)
print(jobs[['pair', 'candidate', 'candidate_flagged', *BEFORE, 'fcp_rel', 'lcp_rel', 'tbt_rel', 'cls_abs']].to_string(index=False))
print(summary.to_string(index=False))
