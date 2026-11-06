"""Evaluate the frozen candidate on scheduled main-branch jobs acquired after the freeze.

The scheduled noise and regression workflows kept collecting at the freeze git_head.
Their measurement path (lighthouse/extract/plan) is byte-identical to the frozen
collector; only the metadata recorder differs (no planned_runs, warmup or duration
fields). This script applies the frozen policy unchanged and reports every job,
including invalid ones. It does not tune anything and cannot replace the predeclared
sample targets; it reports how far the cohort has progressed toward them.
"""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
from perfgate_analysis.compare import compare_frame
from perfgate_analysis.load import load_runs
from perfgate_analysis.power import injected_jobs, TARGET
from perfgate_analysis.rq3 import wilson

ROOT = Path(__file__).resolve().parents[1]
PAGES = {'demo-spa', 'demo-heavy', 'demo-static', 'demo-ssr'}
# Measurement code that must match the frozen collector for the cohort to count.
MEASUREMENT = ('packages/collector/src/lighthouse.ts', 'packages/collector/src/extract.ts',
               'packages/collector/src/plan.ts')

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('raw', type=Path, help='raw/ directory of the data branch')
p.add_argument('--out', type=Path, required=True)
p.add_argument('--freeze', type=Path, default=ROOT/'docs/protocols/browser-candidate-2026-10-30.json')
p.add_argument('--candidate', type=Path, help='prospective/<policy>/ directory of the data branch (amendment of 6 November)')
p.add_argument('--confirmatory', action='store_true',
               help='keep only the first 200 complete suites and first 100 valid jobs per case, in acquisition order (amendment b)')
p.add_argument('--through', help='ignore loads after this UTC timestamp (fixed cutoff)')
args = p.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
freeze = json.loads(args.freeze.read_text())
mismatches = [n for n, d in freeze['source_sha256'].items() if hashlib.sha256((ROOT/n).read_bytes()).hexdigest() != d]
if mismatches:
    raise SystemExit(f'Frozen sources changed: {mismatches}')
cutoff = pd.Timestamp(freeze['acquisition_after_utc'])

days = sorted(d for d in args.raw.iterdir() if d.is_dir() and d.name[:4].isdigit() and d.name >= str(cutoff.date()))
files = [f for d in days for f in sorted(d.glob('*.jsonl')) if '-aa-' in f.name or '-injected-' in f.name]
candidate = sorted(args.candidate.rglob('*.jsonl')) if args.candidate else []
df = load_runs(files + candidate)
df['source'] = df.experiment.isin({f.stem for f in candidate}).map({True: 'candidate', False: 'scheduled'})
files = files + candidate
# a job counts only if all of its loads were acquired after the freeze
first = df.groupby('experiment').timestamp.transform('min')
df = df[first > cutoff]
if args.through:
    last = df.groupby('experiment').timestamp.transform('max')
    df = df[last <= pd.Timestamp(args.through)]
heads = sorted(df.git_sha.dropna().unique()) if 'git_sha' in df else []
df['run_id'] = df.experiment.str.split('-').str[0]

jobs = []
for exp, g in df.groupby('experiment'):
    eligible = g['mode'].iloc[0] == 'abab' and g.throttling.iloc[0] == 'devtools'
    if not eligible:
        continue
    r = compare_frame(g, 20)
    fired = [m['name'].split('/')[-1] for m in r['metrics'] if m['regression']]
    jobs.append({'experiment': exp, 'source': g.source.iloc[0], 'run_id': g.run_id.iloc[0], 'app': g.app.iloc[0],
                 'label': g.label.iloc[0], 'is_aa': bool(g.is_aa.iloc[0]),
                 'inject': g.inject.dropna().iloc[0] if g.inject.notna().any() else None,
                 'start': g.timestamp.min(), 'cpu_model': g.cpu_model.iloc[0],
                 'status': r['status'], 'issues': '; '.join(r['issues']), 'flagged': ';'.join(fired),
                 **{f'{m["name"].split("/")[-1]}_rel': m['relative_effect'] for m in r['metrics']},
                 **{f'{m["name"].split("/")[-1]}_abs': m['absolute_effect'] for m in r['metrics']}})
jobs = pd.DataFrame(jobs)

# Four-page A/A suites: one per scheduled noise run, one Holm family over the suite.
suites = []
aa = df[df.is_aa & (df['mode'] == 'abab') & (df.throttling == 'devtools')]
for run, g in aa.groupby('run_id'):
    complete = set(g.app) == PAGES and g.groupby('app').experiment.nunique().eq(1).all()
    r = compare_frame(g, 20) if complete else None
    suites.append({'run_id': run, 'source': g.source.iloc[0], 'start': g.timestamp.min(), 'pages': len(set(g.app)),
                   'cpu_models': ';'.join(sorted(g.cpu_model.dropna().unique())),
                   'status': r['status'] if r else 'incomplete_suite',
                   'issues': '; '.join(r['issues']) if r else 'missing pages',
                   'flagged': ';'.join(m['name'] for m in r['metrics'] if m['regression']) if r else ''})
suites = pd.DataFrame(suites)

inj = injected_jobs(df, include_invalid=True).groupby('experiment')[['kind', 'pct']].first()
cases = jobs[jobs.label == 'injected'].join(inj, on='experiment')
cases['target'] = cases.kind.map(TARGET)
cases['target_detected'] = [t in f.split(';') for t, f in zip(cases.target, cases.flagged)]
cases['any_detected'] = cases.status.eq('regression')
cases['measured_target_rel'] = [row.get(f'{t}_rel') for t, (_, row) in zip(cases.target, cases.iterrows())]
cases['measured_target_abs'] = [row.get(f'{t}_abs') for t, (_, row) in zip(cases.target, cases.iterrows())]

rows = []
valid_suites = suites[suites.status != 'incomplete_suite']
valid_suites = valid_suites[valid_suites.status != 'invalid']
if args.confirmatory:
    valid_suites = valid_suites.sort_values('start').head(freeze['prospective_aa_complete_suites'])
k, n = int(valid_suites.status.eq('regression').sum()), len(valid_suites)
lo, hi = wilson(k, n) if n else (float('nan'), float('nan'))
rows.append({'cohort': 'A/A four-page suite', 'kind': None, 'nominal_pct': None, 'jobs': n, 'invalid': int(len(suites) - n),
             'alarms_or_target_detections': k, 'rate': k / n if n else None, 'wilson_lo': lo, 'wilson_hi': hi,
             'any_metric_detections': None, 'median_measured_target_rel': None,
             'from_candidate_workflow': int(valid_suites.source.eq('candidate').sum()),
             'predeclared_target_jobs': freeze['prospective_aa_complete_suites']})
for (kind, pct), g in cases.groupby(['kind', 'pct']):
    v = g[g.status != 'invalid']
    if args.confirmatory:
        v = v.sort_values('start').head(freeze['prospective_jobs_per_primary_injection'])
    k, n = int(v.target_detected.sum()), len(v)
    lo, hi = wilson(k, n) if n else (float('nan'), float('nan'))
    rows.append({'cohort': 'injected', 'kind': kind, 'nominal_pct': pct, 'jobs': n, 'invalid': int(len(g) - n),
                 'alarms_or_target_detections': k, 'rate': k / n if n else None, 'wilson_lo': lo, 'wilson_hi': hi,
                 'any_metric_detections': int(v.any_detected.sum()),
                 'median_measured_target_rel': float(v.measured_target_rel.median()) if n else None,
                 'from_candidate_workflow': int(v.source.eq('candidate').sum()),
                 'predeclared_target_jobs': freeze['prospective_jobs_per_primary_injection']})
summary = pd.DataFrame(rows)

# Per-page A/A alarms (each page tested alone, Holm over its four metrics): secondary.
per_page = jobs[jobs.is_aa].groupby('app').agg(
    jobs=('status', lambda s: int(s.ne('invalid').sum())), alarms=('status', lambda s: int(s.eq('regression').sum())))

jobs.to_csv(args.out/'jobs.csv', index=False)
suites.to_csv(args.out/'aa_suites.csv', index=False)
cases.to_csv(args.out/'injected_jobs.csv', index=False)
summary.to_csv(args.out/'summary.csv', index=False)
per_page.to_csv(args.out/'aa_per_page.csv')
manifest = {
    'policy': freeze['policy'], 'freeze_sha256': hashlib.sha256(args.freeze.read_bytes()).hexdigest(),
    'source': 'scheduled main-branch noise/regressions workflows (raw/) and, if given, the candidate workflow (prospective/)',
    'candidate_files': len(candidate),
    'collector_git_heads': heads, 'freeze_git_head': freeze['git_head'],
    'measurement_sources_sha256': {m: hashlib.sha256((ROOT/m).read_bytes()).hexdigest() for m in MEASUREMENT},
    'deviation': 'metadata recorder differs from the frozen collector (no planned_runs/warmup/duration fields); '
                 'measurement sources are identical to the frozen ones',
    'acquisition_after_utc': str(cutoff), 'data_from': str(df.timestamp.min()), 'data_through': str(df.timestamp.max()),
    'loads': len(df), 'jobs_all_protocols': int(df.experiment.nunique()), 'failed_loads': int((~df.ok).sum()),
    'aa_suites_complete': int(len(valid_suites)), 'aa_suite_alarms': int(valid_suites.status.eq('regression').sum()),
    'files_sha256': {str(f.relative_to(args.raw.parent)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files
                     if f.stem in set(df.experiment)},
}
(args.out/'manifest.json').write_text(json.dumps(manifest, indent=2, default=str) + '\n')
print(json.dumps({k: v for k, v in manifest.items() if k != 'files_sha256'}, indent=2, default=str))
print(summary.to_string(index=False))
print(per_page.to_string())
