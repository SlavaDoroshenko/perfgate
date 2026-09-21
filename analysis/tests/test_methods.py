import numpy as np

from perfgate_analysis.methods import (
    bootstrap_ratio,
    default_methods,
    mann_whitney,
    significant_and_large,
    single_run,
    threshold,
    welch_t,
)


def samples(shift, reps=400, n=20, sigma=0.03, seed=3):
    rng = np.random.default_rng(seed)
    base = rng.normal(1000, sigma * 1000, (reps, n))
    pr = rng.normal(1000 * (1 + shift), sigma * 1000, (reps, n))
    return base, pr


def test_tests_hold_nominal_false_alarm_rate():
    base, pr = samples(0.0)
    for m in [mann_whitney(), welch_t(), bootstrap_ratio()]:
        assert 0.01 < m(base, pr).mean() < 0.10, m.name


def test_tests_detect_a_five_percent_regression():
    base, pr = samples(0.05)
    for m in [mann_whitney(), welch_t(), bootstrap_ratio()]:
        assert m(base, pr).mean() > 0.9, m.name


def test_single_run_is_noisier_than_the_median_rule():
    base, pr = samples(0.0)
    assert single_run(0.02)(base, pr).mean() > threshold(0.02)(base, pr).mean()


def test_effect_size_gate_suppresses_tiny_differences():
    # the situation measured on the runners: spread of 0.3%, true shift of 0.3%.
    # The test sees it easily, but nobody would fail a build for it.
    base, pr = samples(0.003, sigma=0.003)
    assert mann_whitney()(base, pr).mean() > 0.5
    assert significant_and_large(min_effect=0.01)(base, pr).mean() == 0


def test_zero_baseline_never_flags():
    zeros = np.zeros((10, 20))
    for m in default_methods():
        assert not m(zeros, zeros).any(), m.name


def test_methods_have_unique_names():
    names = [m.name for m in default_methods()]
    assert len(names) == len(set(names))
