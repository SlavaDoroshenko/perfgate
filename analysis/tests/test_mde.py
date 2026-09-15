import numpy as np

from perfgate_analysis.load import to_frame
from perfgate_analysis.mde import DELTAS, PowerConfig, aa_false_alarms, mde_from_curve, mde_table, power_curve, power_table

from .conftest import synthetic_records


def normal_experiments(sigma: float, experiments: int = 20, size: int = 40, seed: int = 7):
    rng = np.random.default_rng(seed)
    return [rng.normal(1000, sigma * 1000, size) for _ in range(experiments)]


def test_false_alarm_rate_close_to_alpha():
    power = power_curve(normal_experiments(0.05), n=10, deltas=np.array([0.0]), cfg=PowerConfig(reps=4000))
    assert 0.03 <= power[0] <= 0.07


def test_mde_matches_normal_theory():
    # relative sd 5%, n=20: (z_0.95 + z_0.8) * 0.05 * sqrt(2/20) ≈ 3.9% for a t-test,
    # MWU is ~5% less efficient → first grid point with power >= 0.8 is 5%
    curve = power_curve(normal_experiments(0.05), n=20, cfg=PowerConfig(reps=2000))
    assert mde_from_curve(curve) == 0.05
    assert curve[list(DELTAS).index(0.02)] < 0.8


def test_power_increases_with_sample_size():
    exps = normal_experiments(0.05)
    delta = np.array([0.03])
    small = power_curve(exps, n=5, deltas=delta)[0]
    large = power_curve(exps, n=20, deltas=delta)[0]
    assert large > small


def test_too_short_experiments_give_nan():
    curve = power_curve([np.ones(10)], n=20)
    assert np.isnan(curve).all()


def test_constant_metric_never_detected():
    curve = power_curve([np.zeros(40)] * 5, n=10)
    assert (curve == 0).all()
    assert np.isnan(mde_from_curve(curve))


def test_tables_from_frame():
    df = to_frame(synthetic_records(experiments=5, runs=20, sigma=0.05))
    power = power_table(df, metrics=["lcp"], sample_sizes=(10,), cfg=PowerConfig(reps=500))
    mde = mde_table(power)
    assert len(mde) == 1
    assert mde["mde"].iloc[0] in (0.05, 0.075)

    fa = aa_false_alarms(df, metrics=["lcp", "tbt"])
    lcp = fa[fa["metric"] == "lcp"].iloc[0]
    assert lcp["experiments"] == 5
    # all-zero TBT can never raise an alarm
    assert fa[fa["metric"] == "tbt"]["false_alarm_rate"].iloc[0] == 0
