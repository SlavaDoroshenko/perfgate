"""Record source hashes and a prospective acquisition boundary before examining later data."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--out", type=Path, required=True)
parser.add_argument("--exploration-data-sha", required=True)
args = parser.parse_args()
if args.out.exists():
    parser.error("refusing to overwrite a protocol freeze")
files = sorted([*ROOT.glob("analysis/perfgate_analysis/*.py"), *ROOT.glob("packages/collector/src/*.ts"),
                ROOT / "schema/run.schema.json", ROOT / "analysis/uv.lock", ROOT / "pnpm-lock.yaml",
                ROOT / "docs/research-completion.md", ROOT / "docs/compare.md"])
result = {
    "policy": "browser-candidate-2026-10-30",
    "acquisition_after_utc": datetime.now(timezone.utc).isoformat(),
    "exploration_data_sha": args.exploration_data_sha,
    "git_head": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
    "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
    "primary_runs": 20, "secondary_runs": 10,
    "prospective_aa_complete_suites": 200, "prospective_jobs_per_primary_injection": 100,
    "local_smoke_tests_are_not_confirmatory": True,
    "status": "frozen candidate; acquisition and evaluation pending",
}
args.out.parent.mkdir(parents=True, exist_ok=True)
args.out.write_text(json.dumps(result, indent=2) + "\n")
print(args.out)
