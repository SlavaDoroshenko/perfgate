import numpy as np
import pandas as pd

from perfgate_analysis.history import CpdConfig, cpu_adjusted, detection_rates, e_divisive

CFG = CpdConfig(window=20, permutations=99)


def test_finds_a_clear_step():
    rng = np.random.default_rng(1)
    x = np.r_[rng.normal(100, 1, 15), rng.normal(110, 1, 15)]
    k, p = e_divisive(x, CFG, rng)
    assert abs(k - 15) <= 1
    assert p < 0.05


def test_quiet_series_is_not_flagged_often():
    rng = np.random.default_rng(2)
    flagged = [e_divisive(rng.normal(100, 1, 20), CFG, rng)[1] < 0.05 for _ in range(40)]
    assert np.mean(flagged) < 0.15


def test_power_grows_with_step():
    rng = np.random.default_rng(3)
    values = rng.normal(1000, 10, 30)
    rates = detection_rates(values, np.array([0.0, 0.05]), CFG, rng)
    assert rates[1] > 0.9
    assert rates[0] < 0.3


def test_cpu_adjustment_removes_hardware_levels():
    s = pd.DataFrame({"cpu_model": ["a", "b", "a", "b"], "value": [100.0, 120.0, 102.0, 118.0]})
    adj = cpu_adjusted(s)
    assert np.allclose(adj, [100 / 101, 120 / 119, 102 / 101, 118 / 119])
