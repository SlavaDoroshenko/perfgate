import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tail_exceedance import tail_exceedance  # noqa: E402


def test_two_slow_pr_loads_warn_where_welch_stays_quiet():
    rng = np.random.default_rng(1)
    base = rng.normal(340, 5, 20)
    pr = rng.normal(340, 5, 20)
    pr[[2, 12]] += 740
    r = tail_exceedance({"p": (base, pr)})["p"]
    assert r["warning"] and r["slow_pr"] == 2 and r["slow_base"] == 0


def test_one_slow_load_does_not_warn():
    base = np.full(20, 340.0)
    pr = base.copy()
    pr[5] += 740
    assert not tail_exceedance({"p": (base, pr)})["p"]["warning"]


def test_a_slow_base_load_suppresses_the_warning():
    base = np.full(20, 340.0)
    base[7] += 500
    pr = np.full(20, 340.0)
    pr[[1, 9, 15]] += 740
    assert not tail_exceedance({"p": (base, pr)})["p"]["warning"]


def test_threshold_is_the_larger_of_100_ms_and_20_percent():
    assert tail_exceedance({"z": (np.zeros(20), np.zeros(20))})["z"]["threshold_ms"] == 100
    assert tail_exceedance({"h": (np.full(20, 1000.0), np.full(20, 1000.0))})["h"]["threshold_ms"] == 1200
