import json
import numpy as np

from perfgate_analysis.compare import Samples, compare_frame, compare_samples, markdown
from perfgate_analysis.load import to_frame
from .conftest import synthetic_records


def browser_frame(shift=0):
    records = synthetic_records(1, 20, .002)
    for r in records:
        r.update(warmup=2, failedRequests=0, throttling="devtools", plannedRuns=20, warmupErrors=0)
        if r["variant"] == "pr": r["metrics"]["fcp"] *= 1 + shift
    return to_frame(records)


def test_detects_regression_and_emits_finite_report():
    result = compare_frame(browser_frame(.1), boots=99)
    assert result["status"] == "regression"
    assert next(m for m in result["metrics"] if m["name"].endswith("/fcp"))["regression"]
    json.dumps(result, allow_nan=False)
    assert "candidate" in markdown(result)


def test_no_difference_is_not_claimed_equivalent():
    result = compare_frame(browser_frame(), boots=99)
    assert result["status"] == "no_regression_detected"
    assert any("equivalence" in x for x in result["limitations"])


def test_zero_baseline_uses_absolute_effect():
    result = compare_samples([Samples("memory", np.zeros(20), np.full(20, 10.), .05, 5., "MB")], boots=99)
    assert result[0]["relative_effect"] is None
    assert result[0]["regression"]


def test_small_absolute_tbt_does_not_block():
    result = compare_samples([Samples("tbt", np.zeros(20), np.full(20, 3.), .05, 5., "ms")], boots=99)
    assert not result[0]["regression"]


def test_missing_page_or_metric_makes_whole_check_invalid():
    df = browser_frame(.1)
    df.loc[0, "cls"] = float("nan")
    result = compare_frame(df, boots=99)
    assert result["status"] == "invalid" and not result["metrics"]


def test_failed_warmup_and_truncated_tail_rejected():
    df = browser_frame()
    df["warmup_errors"] = 1
    assert compare_frame(df, boots=99)["status"] == "invalid"
    df["warmup_errors"] = 0
    assert compare_frame(df[df.run_index < 10], runs=10, boots=99)["status"] == "invalid"


def test_cannot_pool_repeated_experiments_as_one_page():
    import pandas as pd
    a = browser_frame(); b = browser_frame(); b["experiment"] = "repeat"
    assert compare_frame(pd.concat([a, b]), boots=99)["status"] == "invalid"


def test_family_order_does_not_change_intervals():
    a = Samples("a", np.arange(20.), np.arange(20.) + 2, .01, 0, "ms")
    b = Samples("b", np.arange(20.), np.arange(20.), .01, 0, "ms")
    x = {r["name"]: r for r in compare_samples([a, b], boots=99)}
    y = {r["name"]: r for r in compare_samples([b, a], boots=99)}
    assert x == y
