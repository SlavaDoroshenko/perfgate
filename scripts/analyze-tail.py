"""Analyze fixed rare-stall pilot jobs, retaining invalid/incomplete experiments."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from perfgate_analysis.load import load_runs
from perfgate_analysis.quality import comparison_issues
from perfgate_analysis.compare import compare_frame
from perfgate_analysis.methods import default_methods, permutation_mean


def analyze(directory, freeze):
    manifest = json.loads((directory / 'manifest.json').read_text())
    summary = {'experiment': manifest['experiment'], 'condition': manifest['condition'],
               'seed': manifest['seed'], 'platform': manifest['env']['platform'],
               'runner': manifest['env'].get('runnerName'), 'valid': False}
    issues = []
    if manifest.get('acquisition_role') != 'pilot': issues.append('not a main pilot job')
    if manifest.get('freeze_sha256') != hashlib.sha256(freeze.read_bytes()).hexdigest(): issues.append('wrong protocol freeze')
    if not manifest.get('finished'): issues.append('incomplete acquisition')
    if manifest.get('failures'): issues.append('recorded acquisition failures')
    if manifest.get('completed_slots') != 44: issues.append('expected 44 slots including warmups')
    frozen = json.loads(freeze.read_text())
    if pd.Timestamp(manifest['started']) <= pd.Timestamp(frozen['acquisition_after_utc']): issues.append('acquired before freeze')
    condition = manifest['condition']; seed = manifest['seed']
    count = {'aa': 0, 'rare': 3, 'dense': 20}.get(condition)
    if count is None or seed not in frozen['seeds']: issues.append('undeclared condition/seed')
    ordered = sorted(range(20), key=lambda index: hashlib.sha256(f'{seed}:{index}'.encode()).hexdigest())
    selected = sorted(ordered[:count]) if count is not None else []
    if manifest.get('selected_indices') != selected: issues.append('assignment schedule mismatch')
    durations = []
    try:
        df = load_runs([directory / 'runs.jsonl'])
        issues.extend(comparison_issues(df, ('fcp', 'lcp', 'tbt', 'cls'), expected_runs=20, require_network=True))
        records = [json.loads(line) for line in (directory / 'runs.jsonl').read_text().splitlines()]
        if any(r['experimentId'] != manifest['experiment'] or r.get('appBuild') != manifest['app_build'] for r in records):
            issues.append('record experiment/build differs from manifest')
        by_slot = {(r['runIndex'], r['variant']): r for r in records}
        for index in range(-2, 20):
            for variant in ['base', 'pr']:
                name = f'{"warmup" if index < 0 else "run"}-{abs(index)}-{variant}.json'
                e = json.loads((directory / 'evidence' / name).read_text())
                expected = index >= 0 and variant == 'pr' and index in selected
                if e['index'] != index or e['variant'] != variant or e['expected'] != expected: issues.append(f'{name}: wrong slot/assignment')
                if e.get('issues') or not e.get('evidence') or e['evidence'].get('issues'): issues.append(f'{name}: invalid evidence')
                if index >= 0 and e['record'] != by_slot.get((index, variant)): issues.append(f'{name}: record/evidence mismatch')
                if expected:
                    duration = e['evidence']['durationMs']
                    if duration is None or duration < frozen['stall_ms'] - 5: issues.append(f'{name}: missing/short stall')
                    else: durations.append(duration)
    except (OSError, ValueError, KeyError, TypeError) as error:
        issues.append(str(error)); df = pd.DataFrame()
    summary['issues'] = '; '.join(dict.fromkeys(issues))
    if issues: return summary, [], None
    summary['valid'] = True
    gate = compare_frame(df, 20)
    if gate['status'] == 'invalid':
        summary['valid'] = False; summary['issues'] = '; '.join(gate['issues']); return summary, [], gate
    summary['gate_status'] = gate['status']
    summary['gate_target_tbt'] = next(m['regression'] for m in gate['metrics'] if m['name'].endswith('/tbt'))
    summary['gate_flagged_metrics'] = ';'.join(m['name'] for m in gate['metrics'] if m['regression'])
    arrays = {}
    for variant in ['base', 'pr']:
        values = df[df.variant == variant].sort_values('run_index').tbt.to_numpy(float)
        arrays[variant] = values
        for name, value in [('mean', np.mean(values)), ('median', np.median(values)), ('p95', np.quantile(values, .95)), ('max', np.max(values))]:
            summary[f'{variant}_tbt_{name}'] = float(value)
    for stat in ['mean', 'median']:
        b, p = summary[f'base_tbt_{stat}'], summary[f'pr_tbt_{stat}']
        summary[f'tbt_{stat}_absolute_change'] = p - b
        summary[f'tbt_{stat}_relative_change'] = p / b - 1 if b else None
    summary['executed_stalls'] = len(durations)
    summary['stall_duration_min_ms'] = min(durations) if durations else None
    summary['stall_duration_max_ms'] = max(durations) if durations else None
    summary['measurement_and_warmup_seconds'] = float((df.duration_ms.sum() + df.warmup_duration_ms.iloc[0]) / 1000)
    decisions = [{'experiment': manifest['experiment'], 'condition': condition, 'seed': seed,
                  'method': method.name, 'detected': bool(method(arrays['base'][None, :], arrays['pr'][None, :])[0])}
                 for method in [*default_methods(), permutation_mean()]]
    return summary, decisions, gate


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--freeze', type=Path, default=Path('docs/protocols/tail-browser-pilot-2026-10-30.json'))
    args = p.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    summaries, methods = [], []
    for manifest in sorted(args.root.rglob('manifest.json')):
        raw = json.loads(manifest.read_text())
        if raw.get('protocol') != 'tail-browser-pilot-2026-10-30': continue
        row, decisions, gate = analyze(manifest.parent, args.freeze)
        summaries.append(row); methods.extend(decisions)
        if gate: (args.out / f"{row['experiment']}-gate.json").write_text(json.dumps(gate, indent=2, allow_nan=False) + '\n')
    if not summaries: raise SystemExit('No pilot manifests found')
    pd.DataFrame(summaries).to_csv(args.out / 'jobs.csv', index=False)
    pd.DataFrame(methods).to_csv(args.out / 'methods.csv', index=False)
    print(pd.DataFrame(summaries).to_string(index=False))
