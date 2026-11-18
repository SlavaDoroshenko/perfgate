import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tail_signal import holm, tail_signal  # noqa: E402


def test_holm_matches_step_down():
    assert holm([0.01, 0.04, 0.03]) == [0.03, 0.06, 0.06]


def test_rare_stalls_warn_while_quiet_pages_do_not():
    rng = np.random.default_rng(1)
    base = rng.normal(340, 5, 20)
    rare = rng.normal(340, 5, 20)
    rare[[2, 12, 14]] += 800
    quiet = rng.normal(340, 5, 20)
    assert tail_signal({"rare": (base, rare)})["rare"]["warning"]
    assert not tail_signal({"quiet": (base, quiet)})["quiet"]["warning"]


def test_small_mean_rise_is_below_the_margin():
    base = np.full(20, 300.0) + np.arange(20) % 3
    pr = base + 15  # significant, but 15 ms < max(10%, 20 ms)
    assert not tail_signal({"p": (base, pr)})["p"]["warning"]


def test_tail_note_writes_tail_json_beside_the_loads(tmp_path):
    import json
    import subprocess
    rng = np.random.default_rng(2)
    rows = []
    for variant in ("base", "pr"):
        tbt = rng.normal(340, 5, 20)
        if variant == "pr":
            tbt[[2, 12, 14]] += 800
        rows += [{"app": "heavy", "variant": variant, "error": None, "metrics": {"tbt": float(x)}} for x in tbt]
    comparison = tmp_path / "comparison"
    comparison.mkdir()
    (comparison / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    note = Path(__file__).resolve().parents[1] / "tail" / "tail-note.py"
    subprocess.run([sys.executable, str(note), str(tmp_path)], check=True)
    out = json.loads((comparison / "tail.json").read_text())
    assert out["schema"] == "perfgate-tail/1"
    assert out["pages"][0]["warning"] and out["pages"][0]["n"] == 20
