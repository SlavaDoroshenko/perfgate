import json
import subprocess
import sys
import pytest
from .conftest import synthetic_records


@pytest.mark.parametrize("case,code,status", [("aa", 0, "no_regression_detected"),
                                              ("regression", 1, "regression"), ("broken", 2, "invalid")])
def test_cli_status_matches_machine_readable_report(tmp_path, case, code, status):
    records = synthetic_records(1, 20, .002)
    for r in records:
        r.update(warmup=2, failedRequests=0, throttling="devtools", plannedRuns=20)
        if case == "regression" and r["variant"] == "pr": r["metrics"]["fcp"] *= 1.1
    if case == "broken": records[0]["error"] = "FAILED_DOCUMENT_REQUEST"
    path = tmp_path / "input.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records))
    out = tmp_path / "report"
    result = subprocess.run([sys.executable, "-m", "perfgate_analysis.compare", str(path),
                             "--out", str(out)], capture_output=True, text=True)
    assert result.returncode == code, result.stderr
    report = json.loads((out / "comparison.json").read_text())
    assert report["status"] == status
    assert (out / "comparison.md").exists()
