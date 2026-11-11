"""Sensitivity of the confirmatory cohort to runner CPU and to clustering by day.

Reads the tables written by evaluate-scheduled-cohort.py --confirmatory and does not
change the result: the fixed samples are re-selected the same way (first N by start),
then split by CPU model and resampled by acquisition day.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

p = argparse.ArgumentParser()
p.add_argument('results', type=Path, help='output directory of evaluate-scheduled-cohort.py --confirmatory')
p.add_argument('--per-case', type=int, default=100)
p.add_argument('--boot', type=int, default=5000)
args = p.parse_args()

PRIMARY = [('script-delay', 5.0), ('lcp-delay', 5.0), ('long-task', 10.0),
           ('layout-shift', 10.0), ('layout-shift', 25.0)]
rng = np.random.default_rng(0)

inj = pd.read_csv(args.results/'injected_jobs.csv')
inj['start'] = pd.to_datetime(inj.start, format='mixed', utc=True)
inj = inj[inj.status != 'invalid']
rows = []
for kind, pct in PRIMARY:
    g = inj[(inj.kind == kind) & (inj.pct == pct)].sort_values('start').head(args.per_case).copy()
    g['day'] = g.start.dt.date
    days = g.day.unique()
    by_day = {d: g[g.day == d].target_detected.to_numpy() for d in days}
    boot = [np.concatenate([by_day[d] for d in rng.choice(days, len(days))]).mean() for _ in range(args.boot)]
    for cpu, c in g.groupby('cpu_model'):
        rows.append({'kind': kind, 'nominal_pct': pct, 'cpu_model': cpu, 'jobs': len(c),
                     'target_detections': int(c.target_detected.sum()),
                     'spurious_other_metric': int((c.any_detected & ~c.target_detected).sum())})
    rows.append({'kind': kind, 'nominal_pct': pct, 'cpu_model': 'ALL', 'jobs': len(g),
                 'target_detections': int(g.target_detected.sum()),
                 'spurious_other_metric': int((g.any_detected & ~g.target_detected).sum()),
                 'days': len(days), 'day_cluster_bootstrap_lo': float(np.quantile(boot, 0.025))})
cases = pd.DataFrame(rows)
cases.to_csv(args.results/'sensitivity_injected.csv', index=False)

jobs = pd.read_csv(args.results/'jobs.csv')
aa = jobs[jobs.is_aa & (jobs.status != 'invalid')]
cls = aa.groupby(['app', 'cpu_model']).agg(
    jobs=('status', 'size'), page_alarms=('status', lambda s: int(s.eq('regression').sum())),
    nonzero_cls_diff=('cls_abs', lambda s: int(s.ne(0).sum())), max_abs_cls_diff=('cls_abs', lambda s: float(s.abs().max())))
cls.to_csv(args.results/'sensitivity_aa_by_cpu.csv')

print(cases.to_string(index=False))
print(cls.to_string())
