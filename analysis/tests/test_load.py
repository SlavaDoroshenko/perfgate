import json

import pytest

from perfgate_analysis.load import app_epoch, load_runs, runner_kind, tree_hash

from .conftest import make_record


def write_jsonl(path, records):
    path.write_text("".join(json.dumps(r) + "\n" for r in records))


def test_loads_and_flattens(tmp_path):
    write_jsonl(tmp_path / "a.jsonl", [make_record(), make_record(variant="pr", order=1)])
    df = load_runs([tmp_path])
    assert len(df) == 2
    assert df["lcp"].tolist() == [1000.0, 1000.0]
    assert df["runner"].iloc[0] == "gha:ubuntu24"
    assert df["is_aa"].all()
    assert df["ok"].all()


def test_injected_experiment_is_not_aa(tmp_path):
    write_jsonl(
        tmp_path / "a.jsonl",
        [make_record(), make_record(variant="pr", inject={"type": "script-delay", "size": 50})],
    )
    df = load_runs([tmp_path])
    assert not df["is_aa"].any()
    assert df["inject"].isna().tolist() == [True, False]
    assert df["inject"].iloc[1] == "script-delay:50"


def test_rejects_invalid_record(tmp_path):
    write_jsonl(tmp_path / "bad.jsonl", [make_record(variant="aa")])
    with pytest.raises(ValueError, match="bad.jsonl:1"):
        load_runs([tmp_path])


def test_local_runner_kind():
    env = make_record()["env"] | {"ci": False, "runnerImage": None, "platform": "darwin", "cpuModel": "Apple M5"}
    assert runner_kind(env) == "local:darwin:Apple M5"


def test_epoch_prefers_recorded_app_build():
    assert app_epoch("demo-spa", "fa45447b5c39", "663e56d0") == "fa45447b5c39"


def test_epoch_falls_back_to_commit_when_git_cannot_resolve():
    assert app_epoch("demo-spa", None, "zzzzzzzzz") == "zzzzzzz"
    assert app_epoch("oss-marked", None, "abcdef123") == "abcdef1"


def test_commits_that_did_not_touch_the_app_share_an_epoch():
    # 663e56d predates --app-build; df7fadf changed other packages only
    if tree_hash("663e56d", "apps/demo-spa") is None:
        pytest.skip("commit history not available (shallow clone)")
    assert app_epoch("demo-heavy", None, "663e56d") == app_epoch("demo-spa", None, "df7fadf") == "fa45447b5c39"
