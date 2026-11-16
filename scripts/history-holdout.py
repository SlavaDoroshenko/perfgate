"""History detector on a temporal hold-out (docs/protocols/history-holdout-2026-11-17.md).

Windows lie entirely after the 18 October snapshot; jobs before it are only the past for
the machine adjustment. The detector code is the frozen analysis/perfgate_analysis/history.py.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from perfgate_analysis.history import CpdConfig, SERIES_KEY, e_divisive, job_series, online_rates, past_adjusted
from perfgate_analysis.load import filter_protocol, load_runs
from perfgate_analysis.rq3 import wilson

ROOT = Path(__file__).resolve().parents[1]
CUTOFF = pd.Timestamp('2026-10-18 16:45:03', tz='UTC')
PAGES = ('demo-heavy', 'demo-spa', 'demo-static', 'demo-ssr')
METRICS = ('fcp', 'lcp', 'tbt')
STEPS = np.array([0.0, 0.01, 0.02, 0.03, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3])

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('data', type=Path, help='checkout of the data branch')
p.add_argument('--out', type=Path, required=True)
p.add_argument('--freeze', type=Path, default=ROOT/'docs/protocols/browser-candidate-2026-10-30.json')
args = p.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
freeze = json.loads(args.freeze.read_text())
if [n for n, d in freeze['source_sha256'].items() if hashlib.sha256((ROOT/n).read_bytes()).hexdigest() != d]:
    raise SystemExit('Frozen sources changed')

scheduled = [f for d in sorted((args.data/'raw').iterdir()) if d.is_dir() and d.name[:4].isdigit()
             for f in sorted(d.glob('*-aa-*-abab-devtools.jsonl'))]
candidate = sorted((args.data/'prospective/browser-candidate-2026-10-30').rglob('*-aa-*-abab-devtools.jsonl'))
df = load_runs(scheduled + candidate)
df['source'] = df.experiment.isin({f.stem for f in candidate}).map({True: 'candidate', False: 'scheduled'})
df = filter_protocol(df[df.app.isin(PAGES) & (df.throttling == 'devtools') & (df['mode'] == 'abab')], 2, None)

rows, disjoint, sizes = [], [], []
for cohort, data in (('scheduled', df[df.source == 'scheduled']), ('pooled', df)):
    for metric in METRICS:
        series = job_series(data, metric)
        for key, s in series.groupby([*SERIES_KEY, 'epoch']):
            s = s.sort_values('timestamp').reset_index(drop=True)
            if s['value'].median() == 0:
                continue
            train = int((s.timestamp <= CUTOFF).sum())
            held = len(s) - train
            for window in (20, 40):
                cfg = CpdConfig(window=window)
                sizes.append({'cohort': cohort, 'app': key[0], 'epoch': key[3], 'metric': metric, 'window': window,
                              'past_jobs': train, 'holdout_jobs': held,
                              'holdout_from': s.timestamp[train] if held else None, 'holdout_to': s.timestamp.iloc[-1]})
                if train < 12 or held < window:
                    continue
                for r in online_rates(s, STEPS, cfg, np.random.default_rng(cfg.seed), train):
                    rows.append({'cohort': cohort, 'app': key[0], 'epoch': key[3], 'metric': metric,
                                 'window': window, 'jobs': held, **r})
                # disjoint windows: the hold-out cut into consecutive non-overlapping windows
                for i in range(train, len(s) - window + 1, window):
                    w, past = s.iloc[i:i + window], s.iloc[:i]
                    values = past_adjusted(w, w['value'].to_numpy(float), past, 'bench-guarded')
                    k, pval = e_divisive(values, cfg, np.random.default_rng(cfg.seed + i))
                    disjoint.append({'cohort': cohort, 'app': key[0], 'metric': metric, 'window': window,
                                     'start': w.timestamp.iloc[0], 'end': w.timestamp.iloc[-1],
                                     'p': pval, 'alarm': bool(pval < cfg.alpha)})

rates = pd.DataFrame(rows)
rates.to_csv(args.out/'rates.csv', index=False)
pd.DataFrame(sizes).to_csv(args.out/'series.csv', index=False)
dis = pd.DataFrame(disjoint)
dis.to_csv(args.out/'disjoint_windows.csv', index=False)

summary = []
keys = ['cohort', 'app', 'metric', 'window', 'shape', 'series', 'detector']
for key, g in rates.groupby(keys):
    g = g.sort_values('step')
    hit = g[(g.step > 0) & (g.rate >= 0.8)]
    summary.append({**dict(zip(keys, key)), 'windows': int(g.windows.iloc[0]),
                    'false_alarm_rate': float(g.loc[g.step == 0, 'rate'].iloc[0]),
                    'mde': float(hit.step.iloc[0]) if len(hit) else float('nan')})
summary = pd.DataFrame(summary)
summary.to_csv(args.out/'summary.csv', index=False)

primary = summary[(summary.series == 'bench-guarded') & (summary.detector == 'e-divisive')]
wide = primary.pivot_table(index=['cohort', 'app', 'metric', 'window', 'windows'], columns='shape',
                           values=['false_alarm_rate', 'mde'], aggfunc='first')
print(wide.to_string())
dis_summary = []
for key, g in dis.groupby(['cohort', 'app', 'metric', 'window']):
    k, n = int(g.alarm.sum()), len(g)
    lo, hi = wilson(k, n)
    dis_summary.append({**dict(zip(['cohort', 'app', 'metric', 'window'], key)), 'windows': n, 'alarms': k,
                        'wilson_lo': lo, 'wilson_hi': hi, 'calibrated_for_blocking': bool(hi <= 0.05)})
dis_summary = pd.DataFrame(dis_summary)
dis_summary.to_csv(args.out/'disjoint_summary.csv', index=False)
print(dis_summary.to_string())
