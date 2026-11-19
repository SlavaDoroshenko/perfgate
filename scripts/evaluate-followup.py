"""Evaluate the follow-up cohort declared in docs/protocols/followup-2026-11-19.md.

B2. the count rule of scripts/tail_exceedance.py on rare-stall jobs and on A/A jobs;
C1. the frozen gate on interleaved A/A under background load, larger fixed sample;
C3. TBT +10% under load with 60 loads per variant, and with the load and the browser on
    separate vCPUs (20 loads, the frozen gate).

Nothing is tuned here. Sample: the first N valid jobs per job type in acquisition order
(N from the protocol); later jobs are counted as extra data. Invalid jobs are reported,
not dropped silently.
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
from tail_exceedance import tail_exceedance  # noqa: E402
from tail_signal import tail_signal  # noqa: E402

PROTOCOL = ROOT/'docs/protocols/followup-2026-11-19.json'
TAIL_FREEZE = ROOT/'docs/protocols/tail-browser-pilot-2026-10-30.json'
TIMING = ('fcp', 'lcp', 'tbt')

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('data', type=Path, help='root of the data branch checkout')
p.add_argument('--out', type=Path, required=True)
p.add_argument('--boot', type=int, default=5000)
p.add_argument('--no-hash-check', action='store_true', help='for testing the script on other data only')
args = p.parse_args()
args.out.mkdir(parents=True, exist_ok=True)

protocol = json.loads(PROTOCOL.read_text())
changed = [n for n, d in protocol['source_sha256'].items()
           if not n.endswith('.md') and hashlib.sha256((ROOT/n).read_bytes()).hexdigest() != d]
if changed and not args.no_hash_check:
    raise SystemExit(f'instruments changed since the protocol: {changed}')
SAMPLE = protocol['sample_per_type']
KEYS = sorted(SAMPLE, key=len, reverse=True)
tail_freeze = json.loads(TAIL_FREEZE.read_text())
tail_freeze_sha = hashlib.sha256(TAIL_FREEZE.read_bytes()).hexdigest()
store = args.data/'prospective'/protocol['protocol']
files = sorted(store.rglob('*.jsonl'))


def key_of(experiment: str) -> str:
    return next(k for k in KEYS if f'-{k}-r' in f'-{experiment}')


def tail_issues(jsonl: Path, condition: str) -> tuple[list[str], int]:
    """The pilot's validity checks: manifest, slot schedule and trace-confirmed stalls."""
    stem = jsonl.name[:-len('.jsonl')]
    issues, stalls = [], 0
    manifest = json.loads((jsonl.parent/f'{stem}.manifest.json').read_text())
    if manifest.get('freeze_sha256') != tail_freeze_sha:
        issues.append('wrong tail freeze')
    if manifest.get('condition') != condition or manifest.get('seed') not in tail_freeze['seeds']:
        issues.append('undeclared condition/seed')
    if not manifest.get('finished') or manifest.get('failures') or manifest.get('completed_slots') != 44:
        issues.append('incomplete acquisition')
    seed = manifest.get('seed')
    ordered = sorted(range(20), key=lambda i: hashlib.sha256(f'{seed}:{i}'.encode()).hexdigest())
    selected = sorted(ordered[:{'aa': 0, 'rare': 3}[condition]])
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
                    stalls += 1
    return list(dict.fromkeys(issues)), stalls


def gate(g: pd.DataFrame, runs: int) -> dict:
    """The frozen gate at 20 loads; at 60 loads the same per-page statistics (protocol, C3)."""
    if runs == 20:
        return compare_frame(g, 20)
    issues = comparison_issues(g, tuple(MARGINS), min_runs=runs, expected_runs=runs, require_network=True)
    if g['mode'].iloc[0] != 'abab' or g.throttling.iloc[0] != 'devtools' or not g.warmup.eq(2).all():
        issues.append('abab, devtools and two warmups required')
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


def pinned_ok(cpu_txt: Path) -> bool | None:
    """The load generator ran on vCPUs 2,3 only (taskset output recorded by the workflow)."""
    if not cpu_txt.exists():
        return None
    line = next((x for x in cpu_txt.read_text().splitlines() if x.startswith('load affinity:')), '')
    return line.rstrip().endswith('list: 2,3')


jobs = []
for f in files:
    df = load_runs([f])
    exp = df.experiment.iloc[0]
    key = key_of(exp)
    runs = protocol['runs_per_variant'].get(key, 20)
    row = {'experiment': exp, 'key': key, 'run_id': exp.split('-')[0], 'start': df.timestamp.min(),
           'end': df.timestamp.max(), 'cpu_model': df.cpu_model.iloc[0], 'runs': runs}
    issues = []
    if key.startswith('tail-'):
        issues, row['executed_stalls'] = tail_issues(f, key.split('-')[1])
    if key.startswith('pin-'):
        row['pinned'] = pinned_ok(f.parent/f'{exp}.cpu.txt')
        if row['pinned'] is not True:
            issues.append('load generator affinity not recorded as 2,3')
    r = gate(df, runs) if not issues else {'status': 'invalid', 'issues': issues, 'metrics': []}
    row['status'] = r['status']
    row['issues'] = '; '.join(r['issues'])
    row['flagged'] = ';'.join(m['name'].split('/')[-1] for m in r['metrics'] if m['regression'])
    for m in r['metrics']:
        name = m['name'].split('/')[-1]
        row[f'{name}_rel'] = m['relative_effect']
    if r['status'] != 'invalid':
        base = df[df.variant == 'base'].sort_values('run_index')
        pr = df[df.variant == 'pr'].sort_values('run_index')
        pages = {'p': (base.tbt.to_numpy(float), pr.tbt.to_numpy(float))}
        e = tail_exceedance(pages)['p']
        row.update(tail_warning=e['warning'], slow_pr=e['slow_pr'], slow_base=e['slow_base'],
                   welch_warning=tail_signal(pages)['p']['warning'])
        for metric in TIMING:
            row[f'{metric}_base_relmad'] = rel_mad(base[metric].to_numpy(float))
    jobs.append(row)
jobs = pd.DataFrame(jobs).sort_values('start').reset_index(drop=True)

jobs['valid'] = jobs.status.ne('invalid')
jobs['rank'] = jobs[jobs.valid].groupby('key').cumcount()
jobs['in_sample'] = jobs.valid & (jobs['rank'] < jobs.key.map(SAMPLE))
sample = jobs[jobs.in_sample].copy()
sample['day'] = pd.to_datetime(sample.start, utc=True).dt.date
flags = sample.flagged.str.split(';')
sample['alarm'] = sample.status.eq('regression')
sample['timing_alarm'] = flags.apply(lambda f: any(m in f for m in TIMING))
sample['tbt_detected'] = flags.apply(lambda f: 'tbt' in f)
rng = np.random.default_rng(20261119)


def day_boot(g: pd.DataFrame, column: str) -> list[float]:
    """2.5% and 97.5% quantiles of the rate when acquisition days are resampled."""
    days = g.day.unique()
    by = {d: g.loc[g.day == d, column].to_numpy(bool) for d in days}
    rates = [np.concatenate([by[d] for d in rng.choice(days, len(days))]).mean() for _ in range(args.boot)]
    return [float(np.quantile(rates, .025)), float(np.quantile(rates, .975))]


def summary_row(study, key, measure, column, target=''):
    g = sample[sample.key == key]
    allj = jobs[jobs.key == key]
    k, n = int(g[column].sum()), len(g)
    lo, hi = wilson(k, n) if n else (None, None)
    met = None
    if n and target.startswith('lower'):
        met = lo >= float(target.split()[-1])
    elif n and target.startswith('upper'):
        met = hi <= float(target.split()[-1])
    boot = day_boot(g, column) if n else [None, None]
    return {'study': study, 'job': key, 'measure': measure, 'k': k, 'n': n, 'planned_n': SAMPLE[key],
            'rate': k / n if n else None, 'wilson_lo': lo, 'wilson_hi': hi,
            'day_boot_lo': boot[0], 'day_boot_hi': boot[1], 'target': target, 'met': met,
            'invalid': int((~allj.valid).sum()), 'after_fixed_sample': int((allj.valid & ~allj.in_sample).sum()),
            'days': int(g.day.nunique())}


summary = pd.DataFrame([
    summary_row('B2', 'tail-rare', 'count rule warns', 'tail_warning', 'lower >= 0.80'),
    summary_row('B2', 'tail-aa', 'count rule warns', 'tail_warning', 'upper <= 0.05'),
    summary_row('B2', 'load-aa', 'count rule warns', 'tail_warning', 'upper <= 0.05'),
    summary_row('B2', 'pin-aa', 'count rule warns', 'tail_warning', 'upper <= 0.05'),
    summary_row('B2', 'tail-rare', 'old Welch rule warns (reference)', 'welch_warning'),
    summary_row('B2', 'tail-rare', 'gate: TBT detected (reference)', 'tbt_detected'),
    summary_row('C1', 'load-aa', 'gate alarm, any metric', 'alarm', 'upper <= 0.05'),
    summary_row('C1', 'load-aa', 'gate alarm, FCP/LCP/TBT', 'timing_alarm'),
    summary_row('C3', 'load-lt10-r60', 'TBT detected, 60 loads', 'tbt_detected', 'lower >= 0.80'),
    summary_row('C3', 'pin-lt10', 'TBT detected, separate vCPUs', 'tbt_detected', 'lower >= 0.80'),
    summary_row('C3', 'pin-aa', 'gate alarm, any metric, separate vCPUs', 'alarm', 'upper <= 0.05'),
    summary_row('C3', 'pin-aa', 'gate alarm, FCP/LCP/TBT, separate vCPUs', 'timing_alarm'),
])

per_metric = pd.DataFrame([
    {'job': key, 'metric': m, 'flagged': int(flags[sample.key == key].apply(lambda f: m in f).sum()),
     'n': int((sample.key == key).sum()), 'median_rel_effect': float(g[f'{m}_rel'].median())}
    for key, g in sample.groupby('key') for m in ('fcp', 'lcp', 'tbt', 'cls') if f'{m}_rel' in g])
noise = sample.groupby('key')[[f'{m}_base_relmad' for m in TIMING]].median().reset_index()
by_cpu = sample.groupby(['key', 'cpu_model']).agg(
    jobs=('status', 'size'), alarms=('alarm', 'sum'), tbt=('tbt_detected', 'sum'),
    tail=('tail_warning', lambda s: int(s.fillna(False).sum()))).reset_index()

jobs.to_csv(args.out/'jobs.csv', index=False)
summary.to_csv(args.out/'summary.csv', index=False)
per_metric.to_csv(args.out/'per_metric.csv', index=False)
noise.to_csv(args.out/'noise.csv', index=False)
by_cpu.to_csv(args.out/'by_cpu.csv', index=False)
out = {
    'protocol': protocol['protocol'], 'protocol_sha256': hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
    'runs': int(jobs.run_id.nunique()), 'jobs': len(jobs), 'invalid_jobs': int((~jobs.valid).sum()),
    'data_from': str(jobs.start.min()), 'data_through': str(jobs.end.max()),
    'loads': int(sum(1 for f in files for _ in f.open())),
    'tail_stalls_executed': int(jobs.get('executed_stalls', pd.Series(dtype=float)).fillna(0).sum()),
    'files_sha256': {str(f.relative_to(args.data)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
}
(args.out/'manifest.json').write_text(json.dumps(out, indent=2, default=str) + '\n')
pd.set_option('display.width', 220)
print(json.dumps({k: v for k, v in out.items() if k != 'files_sha256'}, indent=2, default=str))
print(summary.drop(columns=['day_boot_lo', 'day_boot_hi']).to_string(index=False))
print(per_metric.to_string(index=False))
print(noise.to_string(index=False))
print(by_cpu.to_string(index=False))
