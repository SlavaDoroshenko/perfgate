"""Evaluate the follow-up cohorts declared in docs/protocols/extensions-2026-11-17.md.

A. the frozen gate on the reserved-layout heavy page (CLS-stable by design);
B. the advisory TBT tail signal (scripts/tail_signal.py) on the 200 confirmatory A/A
   suites, on the A/A jobs of this workflow and on rare-stall jobs;
C. the frozen gate under seeded background CPU load, interleaved vs sequential.

Nothing is tuned here. Sample: the first 100 valid jobs per job type in acquisition
order; later jobs are counted as extra data. Invalid jobs are reported, not dropped
silently.
"""
import argparse
import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path

import numpy as np
import pandas as pd
from perfgate_analysis.compare import MARGINS, Samples, compare_frame, compare_samples
from perfgate_analysis.load import load_runs
from perfgate_analysis.quality import comparison_issues
from perfgate_analysis.rq3 import wilson

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from tail_signal import tail_signal  # noqa: E402

PROTOCOL = ROOT/'docs/protocols/extensions-2026-11-17.json'
TAIL_FREEZE = ROOT/'docs/protocols/tail-browser-pilot-2026-10-30.json'
KEYS = ['cls-aa-reserved', 'cls-ls10-reserved', 'cls-ls25-reserved', 'tail-rare', 'tail-aa',
        'load-aa-abab', 'load-aa-sequential', 'load-sd5-abab', 'load-sd5-sequential', 'load-lt10-abab']
TARGET = {'cls-ls10-reserved': 'cls', 'cls-ls25-reserved': 'cls', 'load-sd5-abab': 'fcp',
          'load-sd5-sequential': 'fcp', 'load-lt10-abab': 'tbt', 'tail-rare': 'tbt'}
PAGES = {'demo-spa', 'demo-heavy', 'demo-static', 'demo-ssr'}

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('data', type=Path, help='root of the data branch checkout')
p.add_argument('--confirmatory', type=Path, default=ROOT/'docs/results/2026-11-11/confirmatory',
               help='output of evaluate-scheduled-cohort.py --confirmatory (fixed A/A sample)')
p.add_argument('--out', type=Path, required=True)
p.add_argument('--per-type', type=int, default=100)
p.add_argument('--boot', type=int, default=5000)
args = p.parse_args()
args.out.mkdir(parents=True, exist_ok=True)

protocol = json.loads(PROTOCOL.read_text())
# The protocol text is pinned as recorded; the amendment was appended afterwards, so the
# Markdown is checked against the recording commit, everything else against the tree.
changed = [n for n, d in protocol['source_sha256'].items()
           if not n.endswith('.md') and hashlib.sha256((ROOT/n).read_bytes()).hexdigest() != d]
if changed:
    raise SystemExit(f'instruments changed since the protocol: {changed}')
tail_freeze = json.loads(TAIL_FREEZE.read_text())
tail_freeze_sha = hashlib.sha256(TAIL_FREEZE.read_bytes()).hexdigest()
store = args.data/'prospective'/protocol['protocol']
files = sorted(store.rglob('*.jsonl'))


def key_of(experiment: str) -> str:
    return next(k for k in KEYS if f'-{k}-' in f'-{experiment}-')


def tail_issues(jsonl: Path, condition: str) -> tuple[list[str], list[float]]:
    """The pilot's validity checks: manifest, slot schedule and trace-confirmed stalls."""
    stem = jsonl.name[:-len('.jsonl')]
    issues, stalls = [], []
    manifest = json.loads((jsonl.parent/f'{stem}.manifest.json').read_text())
    if manifest.get('freeze_sha256') != tail_freeze_sha:
        issues.append('wrong tail freeze')
    if manifest.get('condition') != condition or manifest.get('seed') not in tail_freeze['seeds']:
        issues.append('undeclared condition/seed')
    if not manifest.get('finished') or manifest.get('failures') or manifest.get('completed_slots') != 44:
        issues.append('incomplete acquisition')
    count = {'aa': 0, 'rare': 3}[condition]
    seed = manifest.get('seed')
    ordered = sorted(range(20), key=lambda i: hashlib.sha256(f'{seed}:{i}'.encode()).hexdigest())
    selected = sorted(ordered[:count])
    if manifest.get('selected_indices') != selected:
        issues.append('assignment schedule mismatch')
    with tarfile.open(jsonl.parent/f'{stem}.evidence.tar.gz') as tar:
        evidence = {m.name: json.load(io.BytesIO(tar.extractfile(m).read())) for m in tar.getmembers()}
    for index in range(-2, 20):
        for variant in ('base', 'pr'):
            e = evidence.get(f'{"warmup" if index < 0 else "run"}-{abs(index)}-{variant}.json')
            expected = index >= 0 and variant == 'pr' and index in selected
            if e is None or e['index'] != index or e['variant'] != variant or e['expected'] != expected:
                issues.append('evidence slot mismatch')
                continue
            if e.get('issues') or not e.get('evidence') or e['evidence'].get('issues'):
                issues.append('invalid evidence')
            elif expected:
                d = e['evidence'].get('durationMs')
                if d is None or d < tail_freeze['stall_ms'] - 5:
                    issues.append('missing or short stall')
                else:
                    stalls.append(d)
    return list(dict.fromkeys(issues)), stalls


def gate(g: pd.DataFrame) -> dict:
    """The frozen gate; sequential jobs get the same per-page statistics (protocol, C)."""
    if g['mode'].iloc[0] == 'abab':
        return compare_frame(g, 20)
    issues = comparison_issues(g, tuple(MARGINS), min_runs=20, expected_runs=20, require_network=True)
    if g.throttling.iloc[0] != 'devtools' or not g.warmup.eq(2).all():
        issues.append('devtools and two warmups required')
    if issues:
        return {'status': 'invalid', 'issues': issues, 'metrics': []}
    g = g.sort_values('order')
    samples = [Samples(f'{g.app.iloc[0]}/{m}', g.loc[g.variant == 'base', m].to_numpy(float),
                       g.loc[g.variant == 'pr', m].to_numpy(float), r, a, 'unitless' if m == 'cls' else 'ms')
               for m, (r, a) in MARGINS.items()]
    metrics = compare_samples(samples)
    return {'status': 'regression' if any(m['regression'] for m in metrics) else 'no_regression_detected',
            'issues': [], 'metrics': metrics}


def rel_mad(x: np.ndarray) -> float:
    med = np.median(x)
    return float(np.median(np.abs(x - med)) / med) if med > 0 else float('nan')


def load_share(log: Path, start: pd.Timestamp, end: pd.Timestamp) -> float | None:
    """Fraction of the measured span during which the background load was on."""
    if not log.exists():
        return None
    events = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    marks = [(pd.Timestamp(e['t']), e['event']) for e in events if e['event'] in ('on', 'off', 'stop')]
    if not marks:
        return None
    marks.append((max(end, marks[-1][0]), 'stop'))
    on = pd.Timedelta(0)
    for (t0, ev), (t1, _) in zip(marks, marks[1:]):
        if ev == 'on':
            lo, hi = max(t0, start), min(t1, end)
            if hi > lo:
                on += hi - lo
    return on / (end - start)


# ---- jobs of this workflow
jobs = []
for f in files:
    df = load_runs([f])
    exp = df.experiment.iloc[0]
    key = key_of(exp)
    g = df.copy()
    row = {'experiment': exp, 'key': key, 'run_id': exp.split('-')[0], 'start': g.timestamp.min(),
           'end': g.timestamp.max(), 'cpu_model': g.cpu_model.iloc[0], 'mode': g['mode'].iloc[0]}
    issues = []
    stalls = []
    if key.startswith('tail-'):
        issues, stalls = tail_issues(f, key.split('-')[1])
        row['seed'] = int(exp.split('-')[4])
        row['executed_stalls'] = len(stalls)
    r = gate(g) if not issues else {'status': 'invalid', 'issues': issues, 'metrics': []}
    row['status'] = r['status']
    row['issues'] = '; '.join(r['issues'])
    row['flagged'] = ';'.join(m['name'].split('/')[-1] for m in r['metrics'] if m['regression'])
    for m in r['metrics']:
        name = m['name'].split('/')[-1]
        row[f'{name}_rel'] = m['relative_effect']
        row[f'{name}_abs'] = m['absolute_effect']
    if r['status'] != 'invalid':
        base = g[g.variant == 'base'].sort_values('run_index')
        pr = g[g.variant == 'pr'].sort_values('run_index')
        s = tail_signal({g.app.iloc[0]: (base.tbt.to_numpy(float), pr.tbt.to_numpy(float))})[g.app.iloc[0]]
        row.update(tail_warning=s['warning'], tail_p=s['p_holm'], tbt_mean_diff_ms=s['mean_diff_ms'],
                   tbt_mean_rel=s['mean_rel'])
        for metric in ('fcp', 'lcp', 'tbt', 'cls'):
            row[f'{metric}_base_relmad'] = rel_mad(base[metric].to_numpy(float))
            row[f'{metric}_base_median'] = float(base[metric].median())
    if key.startswith('load-'):
        log = f.parent/f'{exp}.load.log'
        row['load_on_share'] = load_share(log, row['start'], row['end'])
    jobs.append(row)
jobs = pd.DataFrame(jobs).sort_values('start').reset_index(drop=True)

# fixed sample: first N valid jobs per type, in acquisition order
jobs['valid'] = jobs.status.ne('invalid')
jobs['rank'] = jobs[jobs.valid].groupby('key').cumcount()
jobs['in_sample'] = jobs.valid & jobs['rank'].lt(args.per_type)
sample = jobs[jobs.in_sample].copy()
sample['day'] = pd.to_datetime(sample.start, utc=True).dt.date
sample['target_detected'] = [TARGET.get(k, '') in f.split(';') if k in TARGET else None
                             for k, f in zip(sample.key, sample.flagged)]
sample['alarm'] = sample.status.eq('regression')
rng = np.random.default_rng(20261117)


def day_boot(g: pd.DataFrame, column: str) -> float:
    """2.5% quantile of the rate when acquisition days are resampled."""
    days = g.day.unique()
    by = {d: g.loc[g.day == d, column].to_numpy(bool) for d in days}
    rates = []
    for _ in range(args.boot):
        pick = np.concatenate([by[d] for d in rng.choice(days, len(days))])
        rates.append(pick.mean())
    return float(np.quantile(rates, .025))


def summary_row(study, key, measure, column):
    g = sample[sample.key == key]
    allj = jobs[jobs.key == key]
    k, n = int(g[column].sum()), len(g)
    lo, hi = wilson(k, n)
    return {'study': study, 'job': key, 'measure': measure, 'k': k, 'n': n, 'rate': k / n if n else None,
            'wilson_lo': lo, 'wilson_hi': hi, 'day_boot_lo': day_boot(g, column) if n else None,
            'invalid': int((~allj.valid).sum()), 'after_fixed_sample': int((allj.valid & ~allj.in_sample).sum()),
            'days': int(g.day.nunique())}


rows = [
    summary_row('A', 'cls-aa-reserved', 'gate alarm, any metric', 'alarm'),
    summary_row('A', 'cls-ls10-reserved', 'CLS detected', 'target_detected'),
    summary_row('A', 'cls-ls25-reserved', 'CLS detected', 'target_detected'),
    summary_row('B', 'tail-rare', 'tail signal', 'tail_warning'),
    summary_row('B', 'tail-rare', 'gate: TBT detected', 'target_detected'),
    summary_row('B', 'tail-rare', 'gate alarm, any metric', 'alarm'),
    summary_row('B', 'tail-aa', 'tail signal', 'tail_warning'),
    summary_row('B', 'tail-aa', 'gate alarm, any metric', 'alarm'),
    summary_row('B', 'cls-aa-reserved', 'tail signal', 'tail_warning'),
    summary_row('B', 'load-aa-abab', 'tail signal', 'tail_warning'),
    summary_row('C', 'load-aa-abab', 'gate alarm, any metric', 'alarm'),
    summary_row('C', 'load-aa-sequential', 'gate alarm, any metric', 'alarm'),
    summary_row('C', 'load-sd5-abab', 'FCP detected', 'target_detected'),
    summary_row('C', 'load-sd5-sequential', 'FCP detected', 'target_detected'),
    summary_row('C', 'load-lt10-abab', 'TBT detected', 'target_detected'),
]

# ---- B on the 200 confirmatory A/A suites (fixed sample of 11 November)
suites = pd.read_csv(args.confirmatory/'aa_suites.csv')
suites['start'] = pd.to_datetime(suites.start, format='mixed', utc=True)
suites = suites[~suites.status.isin(['invalid', 'incomplete_suite'])].sort_values('start').head(200)
manifest = json.loads((args.confirmatory/'manifest.json').read_text())
run_ids = set(suites.run_id.astype(str))
aa_files = [args.data/n for n in manifest['files_sha256']
            if '-aa-' in n and n.split('/')[-1].split('-')[0] in run_ids]
bad = [n for n, d in manifest['files_sha256'].items()
       if (args.data/n) in set(aa_files) and hashlib.sha256((args.data/n).read_bytes()).hexdigest() != d]
if bad:
    raise SystemExit(f'confirmatory files changed: {bad[:3]}')
aa = load_runs(aa_files)
aa = aa[(aa['mode'] == 'abab') & (aa.throttling == 'devtools') & aa.is_aa & aa.app.isin(PAGES)]
aa['run_id'] = aa.experiment.str.split('-').str[0]
suite_rows, idle = [], []
for run, g in aa.groupby('run_id'):
    pages = {}
    for app, h in g.groupby('app'):
        h = h.sort_values('run_index')
        pages[app] = (h[h.variant == 'base'].tbt.to_numpy(float), h[h.variant == 'pr'].tbt.to_numpy(float))
        if app == 'demo-heavy':
            base = h[h.variant == 'base']
            idle.append({'run_id': run, 'cpu_model': h.cpu_model.iloc[0],
                         **{f'{m}_base_relmad': rel_mad(base[m].to_numpy(float)) for m in ('fcp', 'lcp', 'tbt', 'cls')},
                         **{f'{m}_base_median': float(base[m].median()) for m in ('fcp', 'lcp', 'tbt', 'cls')}})
    s = tail_signal(pages)
    suite_rows.append({'run_id': run, 'start': suites.set_index(suites.run_id.astype(str)).start[run],
                       'pages': len(pages), 'warning': any(v['warning'] for v in s.values()),
                       'warned_pages': ';'.join(a for a, v in s.items() if v['warning']),
                       'min_p_holm': min(v['p_holm'] for v in s.values())})
suite_rows = pd.DataFrame(suite_rows).sort_values('start')
suite_rows['day'] = suite_rows.start.dt.date
if len(suite_rows) != 200 or not suite_rows.pages.eq(4).all():
    raise SystemExit(f'expected 200 four-page suites, got {len(suite_rows)}')
k = int(suite_rows.warning.sum())
lo, hi = wilson(k, 200)
rows.insert(3, {'study': 'B', 'job': 'confirmatory A/A suites', 'measure': 'tail signal, any page', 'k': k, 'n': 200,
                'rate': k / 200, 'wilson_lo': lo, 'wilson_hi': hi, 'day_boot_lo': None, 'invalid': 0,
                'after_fixed_sample': 0, 'days': int(suite_rows.day.nunique())})
summary = pd.DataFrame(rows)


# ---- C2: sequential minus interleaved A/A alarm rate, Newcombe hybrid score interval
def newcombe(k1, n1, k2, n2):
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    return d, d - np.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + np.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


seq = summary.set_index(['job', 'measure']).loc[('load-aa-sequential', 'gate alarm, any metric')]
inter = summary.set_index(['job', 'measure']).loc[('load-aa-abab', 'gate alarm, any metric')]
diff = dict(zip(('difference', 'lo', 'hi'), newcombe(seq.k, seq.n, inter.k, inter.n)))

# ---- per-metric alarms, effects and noise
per_metric = []
for key, g in sample.groupby('key'):
    for metric in ('fcp', 'lcp', 'tbt', 'cls'):
        if f'{metric}_rel' not in g:
            continue
        per_metric.append({'job': key, 'metric': metric,
                           'flagged': int(g.flagged.str.split(';').apply(lambda f: metric in f).sum()),
                           'n': len(g), 'median_rel_effect': float(g[f'{metric}_rel'].median()),
                           'median_abs_effect': float(g[f'{metric}_abs'].median())})
per_metric = pd.DataFrame(per_metric)
idle = pd.DataFrame(idle)
noise = []
for name, g in [('idle demo-heavy (confirmatory A/A)', idle),
                ('load-aa-abab', sample[sample.key == 'load-aa-abab']),
                ('load-aa-sequential', sample[sample.key == 'load-aa-sequential']),
                ('cls-aa-reserved (idle, reserved layout)', sample[sample.key == 'cls-aa-reserved'])]:
    noise.append({'cohort': name, 'jobs': len(g),
                  **{f'{m}_relmad_median': float(g[f'{m}_base_relmad'].median()) for m in ('fcp', 'lcp', 'tbt')},
                  **{f'{m}_median': float(g[f'{m}_base_median'].median()) for m in ('fcp', 'lcp', 'tbt', 'cls')}})
noise = pd.DataFrame(noise)
by_cpu = sample.groupby(['key', 'cpu_model']).agg(
    jobs=('status', 'size'), alarms=('alarm', 'sum'),
    target=('target_detected', lambda s: int(s.fillna(False).sum())),
    tail=('tail_warning', lambda s: int(s.fillna(False).sum()))).reset_index()

jobs.to_csv(args.out/'jobs.csv', index=False)
summary.to_csv(args.out/'summary.csv', index=False)
suite_rows.to_csv(args.out/'tail_confirmatory_suites.csv', index=False)
per_metric.to_csv(args.out/'per_metric.csv', index=False)
noise.to_csv(args.out/'noise.csv', index=False)
by_cpu.to_csv(args.out/'by_cpu.csv', index=False)
out = {
    'protocol': protocol['protocol'], 'protocol_sha256': hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
    'runs': int(jobs.run_id.nunique()), 'jobs': len(jobs), 'invalid_jobs': int((~jobs.valid).sum()),
    'data_from': str(jobs.start.min()), 'data_through': str(jobs.end.max()),
    'loads': int(sum(1 for f in files for _ in f.open())),
    'tail_stalls_executed': int(jobs.executed_stalls.fillna(0).sum()),
    'load_on_share_median': float(jobs.load_on_share.median()),
    'load_on_share_range': [float(jobs.load_on_share.min()), float(jobs.load_on_share.max())],
    'c2_sequential_minus_interleaved': diff,
    'files_sha256': {str(f.relative_to(args.data)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
}
(args.out/'manifest.json').write_text(json.dumps(out, indent=2, default=str) + '\n')
pd.set_option('display.width', 200)
print(json.dumps({k: v for k, v in out.items() if k != 'files_sha256'}, indent=2, default=str))
print(summary.to_string(index=False))
print(per_metric.to_string(index=False))
print(noise.to_string(index=False))
print(by_cpu.to_string(index=False))
