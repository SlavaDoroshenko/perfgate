"""Before/after on identical jobs: fixed-threshold checks as used today vs the frozen candidate.

"Before" rules are the common practice the thesis compares against, defined before this
evaluation (methods.single_run / methods.threshold, as in RQ2): one load per variant,
the Lighthouse CI default of three loads, and the same twenty loads the candidate uses,
each against a 5% relative margin on any of FCP/LCP/TBT/CLS. "After" is the frozen
candidate (compare.compare_frame), unchanged. Every rule sees the same loads in their
recorded ABAB order; a rule using k loads takes the first k of each variant.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from perfgate_analysis.compare import compare_frame
from perfgate_analysis.load import load_runs
from perfgate_analysis.methods import single_run, threshold
from perfgate_analysis.power import injected_jobs, TARGET
from perfgate_analysis.quality import comparison_issues
from perfgate_analysis.rq3 import wilson

ROOT = Path(__file__).resolve().parents[1]
METRICS = ('fcp', 'lcp', 'tbt', 'cls')
PAGES = {'demo-spa', 'demo-heavy', 'demo-static', 'demo-ssr'}
BEFORE = {'single load >5%': (single_run(.05), 1), 'median of 3 >5%': (threshold(.05), 3),
          'median of 20 >5%': (threshold(.05), 20)}

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('raw', type=Path)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--through', required=True)
p.add_argument('--freeze', type=Path, default=ROOT/'docs/protocols/browser-candidate-2026-10-30.json')
args = p.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
freeze = json.loads(args.freeze.read_text())
if [n for n, d in freeze['source_sha256'].items() if hashlib.sha256((ROOT/n).read_bytes()).hexdigest() != d]:
    raise SystemExit('Frozen sources changed')
cutoff = pd.Timestamp(freeze['acquisition_after_utc'])
days = sorted(d for d in args.raw.iterdir() if d.is_dir() and d.name[:4].isdigit() and d.name >= str(cutoff.date()))
df = load_runs([f for d in days for f in sorted(d.glob('*-abab-devtools.jsonl')) if '-aa-' in f.name or '-injected-' in f.name])
span = df.groupby('experiment').timestamp.agg(['min', 'max'])
keep = span.index[(span['min'] > cutoff) & (span['max'] <= pd.Timestamp(args.through))]
df = df[df.experiment.isin(keep)]
df['run_id'] = df.experiment.str.split('-').str[0]

rows = []
for exp, g in df.groupby('experiment'):
    if comparison_issues(g, METRICS, min_runs=20, expected_runs=20, require_network=True):
        continue
    g = g.sort_values('order')
    row = {'experiment': exp, 'run_id': g.run_id.iloc[0], 'app': g.app.iloc[0], 'is_aa': bool(g.is_aa.iloc[0])}
    for name, (rule, k) in BEFORE.items():
        for m in METRICS:
            b = g.loc[g.variant == 'base', m].to_numpy(float)[:k][None, :]
            pr = g.loc[g.variant == 'pr', m].to_numpy(float)[:k][None, :]
            row[f'{name}|{m}'] = bool(rule(b, pr)[0])
    r = compare_frame(g, 20)
    for mm in r['metrics']:
        row[f'candidate|{mm["name"].split("/")[-1]}'] = mm['regression']
    rows.append(row)
jobs = pd.DataFrame(rows)
RULES = [*BEFORE, 'candidate']
for rule in RULES:
    jobs[f'{rule}|any'] = jobs[[f'{rule}|{m}' for m in METRICS]].any(axis=1)

out = []
# A/A: whole four-page check. The candidate uses one Holm family over the suite.
aa = jobs[jobs.is_aa]
complete = aa.groupby('run_id').app.agg(set).loc[lambda s: s.map(lambda a: a == PAGES)].index
suite_any = aa[aa.run_id.isin(complete)].groupby('run_id')[[f'{r}|any' for r in BEFORE]].any()
suite_cand = {run: compare_frame(df[(df.run_id == run) & df.is_aa], 20)['status'] == 'regression' for run in complete}
for rule in RULES:
    alarms = suite_any[f'{rule}|any'] if rule in BEFORE else pd.Series(suite_cand)
    k, n = int(alarms.sum()), len(alarms)
    out.append({'cohort': 'A/A four-page check', 'case': '', 'rule': rule, 'jobs': n, 'hits': k,
                'rate': k / n, 'wilson_lo': wilson(k, n)[0], 'wilson_hi': wilson(k, n)[1]})
inj = injected_jobs(df).groupby('experiment')[['kind', 'pct']].first()
cases = jobs[~jobs.is_aa].join(inj, on='experiment', how='inner')
for (kind, pct), g in cases.groupby(['kind', 'pct']):
    for rule in RULES:
        hit = g[f'{rule}|{TARGET[kind]}']
        k, n = int(hit.sum()), len(hit)
        out.append({'cohort': 'injected, target metric', 'case': f'{kind} {pct:g}%', 'rule': rule, 'jobs': n,
                    'hits': k, 'rate': k / n, 'wilson_lo': wilson(k, n)[0], 'wilson_hi': wilson(k, n)[1]})
summary = pd.DataFrame(out)
jobs.to_csv(args.out/'jobs.csv', index=False)
summary.to_csv(args.out/'summary.csv', index=False)
wide = summary.assign(cell=[f'{h}/{n}' for h, n in zip(summary.hits, summary.jobs)]) \
    .pivot_table(index=['cohort', 'case'], columns='rule', values='cell', aggfunc='first')[RULES]
(args.out/'table.md').write_text(wide.to_markdown() + '\n')
print(wide.to_string())
