"""Calibration of the rule in scripts/tail_exceedance.py on data already collected.

Exploratory: the rule's constants were chosen by looking at these numbers, so they are
not a test of the rule. The test is the follow-up cohort of
docs/protocols/followup-2026-11-19.md. Every variant that was looked at is printed, not
only the chosen one.

Data: the 200 four-page A/A suites of the confirmatory sample (11 November) and the
first 100 jobs of tail-rare, tail-aa, cls-aa-reserved and load-aa-abab of the
extensions cohort (17 November).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from perfgate_analysis.load import load_runs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from tail_exceedance import tail_exceedance  # noqa: E402

PAGES = {'demo-spa', 'demo-heavy', 'demo-static', 'demo-ssr'}
JOBS = ['tail-rare', 'tail-aa', 'cls-aa-reserved', 'load-aa-abab']
# (relative, absolute ms, rule) looked at; the chosen one is (0.20, 100, '>=2 PR, 0 base')
VARIANTS = [(r, a, rule) for r in (0.0, 0.10, 0.20, 0.25) for a in (50, 100)
            for rule in ('>=1 PR, 0 base', '>=2 PR, 0 base', 'PR >= base + 2')]

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('data', type=Path, help='root of the data branch checkout')
p.add_argument('--out', type=Path, required=True)
args = p.parse_args()


def warns(base, pr, rel, ab, rule):
    t = np.median(base) + max(ab, rel * np.median(base))
    cp, cb = int((pr > t).sum()), int((base > t).sum())
    return {'>=1 PR, 0 base': cp >= 1 and cb == 0, '>=2 PR, 0 base': cp >= 2 and cb == 0,
            'PR >= base + 2': cp >= cb + 2}[rule]


def split(g):
    g = g.sort_values('run_index')
    return g[g.variant == 'base'].tbt.to_numpy(float), g[g.variant == 'pr'].tbt.to_numpy(float)


conf = ROOT/'docs/results/2026-11-11/confirmatory'
suites = pd.read_csv(conf/'aa_suites.csv')
suites['start'] = pd.to_datetime(suites.start, format='mixed', utc=True)
suites = suites[~suites.status.isin(['invalid', 'incomplete_suite'])].sort_values('start').head(200)
run_ids = set(suites.run_id.astype(str))
files = [args.data/n for n in json.loads((conf/'manifest.json').read_text())['files_sha256']
         if '-aa-' in n and n.split('/')[-1].split('-')[0] in run_ids]
aa = load_runs(files)
aa = aa[(aa['mode'] == 'abab') & (aa.throttling == 'devtools') & aa.is_aa & aa.app.isin(PAGES)]
aa['run_id'] = aa.experiment.str.split('-').str[0]
suite_pages = [[split(h) for _, h in g.groupby('app')] for _, g in aa.groupby('run_id')]
if len(suite_pages) != 200 or any(len(s) != 4 for s in suite_pages):
    raise SystemExit('expected 200 four-page suites')

store = args.data/'prospective/extensions-2026-11-17'
jobs = {}
for key in JOBS:
    fs = sorted(store.rglob(f'*-{key}-*.jsonl'), key=lambda f: load_runs([f]).timestamp.min())[:100]
    jobs[key] = [split(load_runs([f])) for f in fs]

rows = []
for rel, ab, rule in VARIANTS:
    row = {'relative': rel, 'absolute_ms': ab, 'rule': rule,
           'confirmatory_suites': sum(any(warns(b, q, rel, ab, rule) for b, q in s) for s in suite_pages)}
    for key, pages in jobs.items():
        row[key] = sum(warns(b, q, rel, ab, rule) for b, q in pages)
    rows.append(row)
table = pd.DataFrame(rows)
# the module itself, on the same data, must agree with the chosen row
chosen = table[(table.relative == 0.20) & (table.absolute_ms == 100) & (table.rule == '>=2 PR, 0 base')].iloc[0]
module = sum(tail_exceedance({'p': pq})['p']['warning'] for pq in jobs['tail-rare'])
if module != chosen['tail-rare']:
    raise SystemExit('module and calibration disagree')
args.out.mkdir(parents=True, exist_ok=True)
table.to_csv(args.out/'tail_exceedance_calibration.csv', index=False)
print(f'jobs per type: { {k: len(v) for k, v in jobs.items()} }, suites: {len(suite_pages)}')
print(table.to_string(index=False))
