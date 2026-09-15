import numpy as np

from perfgate_analysis.load import to_frame
from perfgate_analysis.noise import cv, robust_cv, summarize, within_between

from .conftest import synthetic_records


def test_robust_cv_ignores_outlier():
    x = np.array([100, 101, 99, 100, 102, 98, 100, 5000])
    assert robust_cv(x) < 0.02
    assert cv(x) > 1


def test_zero_median_gives_nan():
    assert np.isnan(robust_cv(np.zeros(5)))


def test_summary_recovers_sigma():
    df = to_frame(synthetic_records(experiments=10, runs=20, sigma=0.05))
    s = summarize(df)
    lcp = s[s["metric"] == "lcp"].iloc[0]
    assert lcp["n"] == 400
    assert abs(lcp["cv"] - 0.05) < 0.01
    tbt = s[s["metric"] == "tbt"].iloc[0]
    assert tbt["zero_share"] == 1.0


def test_within_between():
    df = to_frame(synthetic_records(experiments=10, runs=20, sigma=0.05))
    wb = within_between(df)
    lcp = wb[wb["metric"] == "lcp"].iloc[0]
    assert abs(lcp["within_robust_cv"] - 0.05) < 0.015
    # medians of 40 iid loads vary far less than single loads
    assert lcp["between_cv_of_medians"] < 0.03
