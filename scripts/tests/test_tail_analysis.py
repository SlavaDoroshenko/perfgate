"""Whole-job rejection is essential when one rare event is lost."""
import importlib.util
import json
import hashlib
from pathlib import Path

spec = importlib.util.spec_from_file_location('tail_analysis', Path(__file__).parents[1] / 'analyze-tail.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def setup_manifest(tmp_path):
    freeze = tmp_path / 'freeze.json'
    freeze.write_text(json.dumps({'seeds': [2026103001], 'stall_ms': 800, 'acquisition_after_utc': '2026-01-01T00:00:00Z'}))
    job = tmp_path / 'job'; job.mkdir()
    manifest = {'experiment': 'test-tail', 'condition': 'rare', 'seed': 2026103001,
                'env': {'platform': 'linux'}, 'acquisition_role': 'pilot',
                'freeze_sha256': hashlib.sha256(freeze.read_bytes()).hexdigest(),
                'completed_slots': 44, 'started': '2026-10-30T00:00:00Z', 'finished': '2026-10-30T01:00:00Z',
                'failures': [], 'selected_indices': sorted(sorted(range(20), key=lambda i: hashlib.sha256(f'2026103001:{i}'.encode()).hexdigest())[:3]),
                'app_build': 'test-build'}
    (job / 'manifest.json').write_text(json.dumps(manifest))
    return job, freeze, manifest


def test_missing_raw_series_is_invalid_not_quiet(tmp_path):
    job, freeze, _ = setup_manifest(tmp_path)
    result, methods, gate = module.analyze(job, freeze)
    assert not result['valid']
    assert methods == [] and gate is None


def test_incomplete_job_is_explicitly_reported(tmp_path):
    job, freeze, manifest = setup_manifest(tmp_path)
    del manifest['finished']; manifest['completed_slots'] = 43
    (job / 'manifest.json').write_text(json.dumps(manifest))
    result, _, _ = module.analyze(job, freeze)
    assert 'incomplete acquisition' in result['issues']
    assert 'expected 44 slots' in result['issues']


def test_changed_assignment_cannot_be_silently_analyzed(tmp_path):
    job, freeze, manifest = setup_manifest(tmp_path)
    manifest['selected_indices'] = []
    (job / 'manifest.json').write_text(json.dumps(manifest))
    result, _, _ = module.analyze(job, freeze)
    assert 'assignment schedule mismatch' in result['issues']
