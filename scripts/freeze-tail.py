"""Freeze the exploratory rare-stall protocol before its main pilot acquisition."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / 'docs/protocols/tail-browser-pilot-2026-10-30.json'
if out.exists(): raise SystemExit('Refusing to overwrite a protocol freeze')
previous = json.loads((root / 'docs/protocols/browser-candidate-2026-10-30.json').read_text())
for path, digest in previous['source_sha256'].items():
    if hashlib.sha256((root / path).read_bytes()).hexdigest() != digest:
        raise SystemExit(f'Browser candidate changed: {path}')
paths = sorted(set(previous['source_sha256']) | {
    'scripts/collect-tail.mjs', 'scripts/tail-protocol.mjs', 'scripts/prepare-tail-fixture.mjs',
    'scripts/analyze-tail.py', 'scripts/freeze-tail.py', 'experiments/rare-stalls/probe.js',
    'docs/tail-browser-protocol-2026-10-30.md',
})
manifest = {'protocol': 'tail-browser-pilot-2026-10-30',
            'acquisition_after_utc': datetime.now(timezone.utc).isoformat(),
            'source_commit': subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip(),
            'runs': 20, 'warmup': 2, 'stall_ms': 800, 'seeds': [2026103001, 2026103002],
            'hosted_conditions': ['aa', 'rare', 'dense'], 'local_condition': 'rare', 'local_seed': 2026103001,
            'source_sha256': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}}
out.write_text(json.dumps(manifest, indent=2) + '\n')
print(out)
