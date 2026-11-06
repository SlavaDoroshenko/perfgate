import pytest

from perfgate_analysis.load import to_frame
from perfgate_analysis.quality import comparison_issues, valid_comparisons
from perfgate_analysis.rq3 import job_stats
from perfgate_analysis.power import _series
from .conftest import synthetic_records


def frame():
    return to_frame(synthetic_records(2, 20, .01))


@pytest.mark.parametrize("damage", ["failure", "missing", "duplicate", "metric", "protocol", "order"])
def test_invalid_job_is_excluded_whole(damage):
    df = frame()
    if damage == "failure": df.loc[0, "ok"] = False
    elif damage == "missing": df = df.drop(index=0)
    elif damage == "duplicate": df.loc[2, "run_index"] = 0
    elif damage == "metric": df.loc[0, "fcp"] = float("nan")
    elif damage == "protocol": df.loc[0, "chrome"] = "other"
    elif damage == "order": df.loc[0, "order"] = 200
    clean, rejected = valid_comparisons(df, ("fcp",), expected_runs=20)
    assert clean.experiment.unique().tolist() == ["exp-1"]
    assert rejected.experiment.tolist() == ["exp-0"]


def test_requested_size_cannot_shrink_silently():
    df = to_frame(synthetic_records(1, 5, .01))
    assert job_stats(df, metrics=("fcp",), loads=20).empty
    assert _series(df, "fcp", 20) is None


def test_failure_cannot_shift_sample_indices():
    df = frame().query("experiment == 'exp-0'")
    df.loc[0, "ok"] = False
    assert _series(df, "fcp", 10) is None


def test_network_status_required_only_in_strict_mode():
    df = frame().query("experiment == 'exp-0'")
    assert not comparison_issues(df, ("fcp",))
    assert "network status unknown" in comparison_issues(df, ("fcp",), require_network=True)
