"""History records and the static dashboard (scripts/history/perfgate_history.py)."""
import importlib.util
import json
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location('perfgate_history', ROOT / 'scripts/history/perfgate_history.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
FIXTURES = ROOT / 'scripts/comment/fixtures'


def run_line(variant, order, cpu='AMD EPYC 7763 64-Core Processor', bench=1000.0, app='demo-heavy', error=None):
    return {'schemaVersion': 1, 'app': app, 'variant': variant, 'order': order, 'mode': 'abab',
            'throttling': 'devtools', 'benchmarkIndex': bench, 'error': error, 'gitSha': 'f' * 40,
            'timestamp': f'2026-11-10T08:{order:02d}:00.000Z',
            'env': {'cpuModel': cpu, 'chromeVersion': '153.0.0.0', 'chromeBinaryVersion': '153.0.8010.47',
                    'lighthouseVersion': '13.4.1', 'runnerImage': 'ubuntu24'}}


def report(tmp_path, fixture='regression', name='perfgate-1', runs=None):
    d = tmp_path / name
    d.mkdir(parents=True)
    if fixture:
        (d / 'comparison.json').write_text((FIXTURES / f'{fixture}.json').read_text())
    lines = runs if runs is not None else [run_line('base', 0, bench=900), run_line('pr', 1, bench=1100),
                                           run_line('pr', 3, bench=1300, error='timeout')]
    (d / 'runs.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in lines))
    return d


def test_record_has_verdict_effects_and_environment(tmp_path):
    [r] = module.build_records(report(tmp_path), commit='a' * 40, base_commit='b' * 40,
                               run_url='https://github.com/o/r/actions/runs/1', commit_url='javascript:alert(1)')
    assert r['page'] == 'demo-heavy' and r['status'] == 'regression'
    assert r['commit'] == 'a' * 40 and r['base_commit'] == 'b' * 40
    assert r['measured_at'] == '2026-11-10T08:00:00.000Z'
    assert set(r['metrics']) == {'fcp', 'lcp', 'tbt', 'cls'}
    assert r['metrics']['fcp']['regression'] and not r['metrics']['lcp']['regression']
    assert r['metrics']['tbt']['relative_effect'] is None
    # only successful loads of the measured commit give the machine score
    assert r['env']['benchmark_index'] == 1100
    assert r['env']['cpu_model'].startswith('AMD EPYC 7763') and r['env']['chrome_binary_version'] == '153.0.8010.47'
    assert r['run_url'].startswith('https://') and r['commit_url'] is None
    json.dumps(r, allow_nan=False)


def test_failed_reports_are_recorded_not_dropped(tmp_path):
    [invalid] = module.build_records(report(tmp_path, 'broken'))
    assert invalid['status'] == 'invalid' and invalid['metrics'] == {} and invalid['issues']
    assert invalid['page'] == 'demo-heavy' and invalid['commit'] == 'f' * 40
    [crashed] = module.build_records(report(tmp_path, None, name='crashed', runs=[]), page='home')
    assert crashed['status'] == 'error' and crashed['page'] == 'home'


def test_record_cli_appends_one_line_per_page(tmp_path):
    report(tmp_path / 'reports', name='a')
    report(tmp_path / 'reports', 'aa', name='b')
    out = tmp_path / 'history.jsonl'
    assert module.main(['record', '--reports', str(tmp_path / 'reports'), '--out', str(out), '--commit', 'c1']) == 0
    assert module.main(['record', '--reports', str(tmp_path / 'reports'), '--out', str(out), '--commit', 'c2']) == 0
    lines = out.read_text().splitlines()
    assert len(lines) == 4
    assert module.main(['record', '--reports', str(tmp_path / 'empty'), '--out', str(out)]) == 1


def history(values, bench=None, chrome='153.0.8010.47', page='home', start=0):
    records = []
    for i, v in enumerate(values):
        records.append({'schema_version': 1, 'commit': f'{start + i:040x}', 'page': page,
                        'measured_at': f'2026-11-{1 + (start + i) // 24:02d}T{(start + i) % 24:02d}:00:00Z',
                        'status': 'no_regression_detected', 'policy': 'browser-candidate-2026-10-30',
                        'runs_per_variant': 20, 'issues': [],
                        'metrics': {'fcp': {'pr_median': float(v), 'relative_effect': 0.0, 'regression': False}},
                        'env': {'cpu_model': 'cpu', 'chrome_version': chrome, 'throttling': 'devtools',
                                'benchmark_index': None if bench is None else float(bench[i])}})
    return records


def test_change_point_warns_on_a_step_and_not_without_one():
    rng = np.random.default_rng(1)
    noise = 1 + rng.normal(0, 0.003, 30)
    step = module.change_point(history(1000 * noise * np.r_[np.ones(20), np.full(10, 1.05)]), 'fcp')
    assert step['checked'] and step['warning'] and step['p'] < 0.05
    assert 0.03 < step['change'] < 0.07
    assert step['commit'] == f'{20:040x}'
    flat = module.change_point(history(np.full(30, 1000.0)), 'fcp')
    assert flat['checked'] and not flat['warning']
    # an improvement is not a warning
    faster = module.change_point(history(1000 * noise * np.r_[np.ones(20), np.full(10, 0.95)]), 'fcp')
    assert faster['p'] < 0.05 and not faster['warning']


def test_change_point_needs_comparable_points():
    few = module.change_point(history(np.full(8, 1000.0)), 'fcp')
    assert not few['checked'] and '8 of 12' in few['reason']
    # a browser update starts a new series: the step at the update is not examined
    mixed = history(np.full(20, 1000.0)) + history(np.full(8, 1100.0), chrome='154.0.0.0', start=20)
    assert not module.change_point(mixed, 'fcp')['checked']
    assert module.change_point(history(np.zeros(20)), 'fcp')['reason'] == 'median is zero'


def test_first_valid_attempt_per_run_is_used():
    a, b, c, d = history([1000, 2000, 3000, 4000])
    b['commit'] = c['commit'] = d['commit'] = a['commit']
    run = 'https://github.com/o/r/actions/runs/7'
    for i, r in enumerate((a, b, c), 1):
        r['run_url'] = f'{run}/attempts/{i}'
    a['status'] = 'invalid'
    # a separate run of the same commit is a separate measurement
    d['run_url'] = 'https://github.com/o/r/actions/runs/8/attempts/1'
    assert module.first_valid([a, b, c, d]) == [b, d]


def test_dashboard_is_self_contained_and_escaped(tmp_path):
    rng = np.random.default_rng(2)
    records = history(1000 * (1 + rng.normal(0, 0.003, 30)) * np.r_[np.ones(20), np.full(10, 1.05)])
    records[3]['status'] = 'invalid'
    records[5]['metrics']['fcp']['regression'] = True
    evil = history([1000], page='<script>alert(1)</script>')[0]
    evil['env']['cpu_model'] = '<img src=x onerror=alert(1)>'
    path = tmp_path / 'history.jsonl'
    path.write_text(''.join(json.dumps(r) + '\n' for r in [*records, evil]) + 'not json\n')
    out, summary = tmp_path / 'site/index.html', tmp_path / 'summary.md'
    assert module.main(['dashboard', '--history', str(path), '--out', str(out), '--summary', str(summary)]) == 0
    page = out.read_text()
    assert '<script' not in page and '<img' not in page and '&lt;script&gt;' in page
    assert not re.search(r'(src|href)="(?!https://)', page)
    assert 'possible change' in page and 'advisory' in page.lower()
    assert 'home FCP: possible change' in summary.read_text()
    # deterministic: the same history renders the same page
    assert module.render(module.load_history(path))[0] == page


def test_empty_history_renders(tmp_path):
    page, warnings = module.render(module.load_history(tmp_path / 'missing.jsonl'))
    assert 'No history records yet' in page and warnings == []
