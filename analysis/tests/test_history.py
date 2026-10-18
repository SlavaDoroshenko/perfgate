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


def test_past_adjustment_uses_only_earlier_jobs():
    from perfgate_analysis.history import past_adjusted

    past = pd.DataFrame({"cpu_model": ["a", "a", "a", "b"], "value": [100.0, 100, 100, 130], "bench": [1.0] * 4})
    window = pd.DataFrame({"cpu_model": ["a", "b", "c"], "bench": [1.0] * 3})
    adj = past_adjusted(window, np.array([110.0, 130, 100]), past, "cpu")
    # "a" has its own reference; "b" (one job) and the unseen "c" fall back to the overall median
    assert np.allclose(adj, [1.1, 130 / 100, 1.0])


def test_bench_adjustment_removes_a_machine_speed_slope():
    from perfgate_analysis.history import past_adjusted

    rng = np.random.default_rng(5)
    bench = rng.uniform(1500, 2500, 40)
    past = pd.DataFrame({"bench": bench, "value": 2e6 / bench, "cpu_model": "x"})
    window = pd.DataFrame({"bench": [1500.0, 2500.0], "cpu_model": "x"})
    adj = past_adjusted(window, 2e6 / window["bench"].to_numpy(), past, "bench")
    assert np.allclose(adj[0], adj[1], rtol=1e-6)


def test_mozilla_t_sees_a_step_and_not_noise():
    from perfgate_analysis.history import MOZILLA_T, welch_split

    rng = np.random.default_rng(6)
    assert welch_split(np.r_[rng.normal(100, 1, 10), rng.normal(110, 1, 10)], 4) > MOZILLA_T
    assert welch_split(rng.normal(100, 1, 20), 4) < MOZILLA_T


def test_batched_permutations_match_reference():
    from perfgate_analysis.history import _energy_split

    x = np.random.default_rng(9).normal(size=20)
    seed = 123
    k, q = _energy_split(x, CFG.min_size)
    rng = np.random.default_rng(seed)
    exceed = sum(_energy_split(rng.permutation(x), CFG.min_size)[1] >= q for _ in range(CFG.permutations))
    assert e_divisive(x, CFG, np.random.default_rng(seed)) == (k, (exceed + 1) / (CFG.permutations + 1))


def test_guarded_adjustment_leaves_cpu_independent_metric_alone():
    from perfgate_analysis.history import past_adjusted

    past = pd.DataFrame({"bench": np.geomspace(1000, 3000, 40), "value": np.full(40, 100.0)})
    window = pd.DataFrame({"bench": [1000.0, 3000.0, 0.0, np.nan]})
    values = np.array([100.0, 101.0, 102.0, 103.0])
    assert np.allclose(past_adjusted(window, values, past, "bench-guarded"), values / 100)


def test_guarded_adjustment_preserves_new_regression():
    from perfgate_analysis.history import past_adjusted

    bench = np.linspace(1000, 3000, 40)
    past = pd.DataFrame({"bench": bench, "value": 2e6 / bench})
    window = pd.DataFrame({"bench": [1500.0, 2500.0]})
    base = 2e6 / window["bench"].to_numpy()
    adjusted = past_adjusted(window, base * [1.0, 1.1], past, "bench-guarded")
    assert np.isclose(adjusted[1] / adjusted[0], 1.1)


def test_welch_finds_noise_free_step():
    from perfgate_analysis.history import welch_split

    assert np.isinf(welch_split(np.r_[np.ones(10), np.full(10, 2.0)], 4))


def test_vectorized_welch_matches_direct_variances():
    from perfgate_analysis.history import welch_split

    x = 1e6 + np.random.default_rng(18).normal(size=40)
    expected = max(abs(x[:k].mean() - x[k:].mean()) /
                   np.sqrt(x[:k].var(ddof=1) / k + x[k:].var(ddof=1) / (len(x) - k))
                   for k in range(4, len(x) - 3))
    assert np.isclose(welch_split(x, 4), expected, rtol=1e-7)


def test_online_zero_effect_is_identical_for_step_and_ramp():
    from perfgate_analysis.history import online_rates

    rng = np.random.default_rng(42)
    s = pd.DataFrame({"value": rng.normal(100, 1, 35), "bench": rng.normal(2000, 20, 35), "cpu_model": "x"})
    rates = pd.DataFrame(online_rates(s, np.array([0.0]), CpdConfig(permutations=19), rng))
    table = rates.pivot(index=["series", "detector"], columns="shape", values="rate")
    assert (table["step"] == table["ramp"]).all()
