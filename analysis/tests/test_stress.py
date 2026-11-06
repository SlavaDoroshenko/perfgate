import numpy as np
from perfgate_analysis.methods import permutation_mean
from perfgate_analysis.stress import scenarios


def test_permutation_mean_direction_and_reproducibility():
    method = permutation_mean(permutations=99)
    b = np.ones((2, 10))
    p = np.array([[2.] * 10, [1.] * 10])
    assert method(b, p).tolist() == [True, False]
    assert method(p, b).tolist() == [False, False]
    assert np.array_equal(method(b, p), method(b, p))


def test_stalls_change_tail_without_uniform_scaling():
    data = {name: (b, p) for name, _, b, p in scenarios(20, 500, 1)}
    b, p = data["rare_stall_15pct_plus100"]
    assert np.mean(p) > np.mean(b) * 1.1
    assert abs(np.median(p) / np.median(b) - 1) < .02
