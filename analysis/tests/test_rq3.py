import numpy as np

from perfgate_analysis.load import to_frame
from perfgate_analysis.rq3 import compare_modes, holm, job_stats, mode_summary, pr_level, pr_summary, wilson

from .conftest import make_record


def drifting_jobs(mode: str, jobs: int, runs: int = 20, drift: float = 0.02, seed: int = 3) -> list[dict]:
    """A/A jobs whose machine slows down linearly by `drift` over the series."""
    rng = np.random.default_rng(seed)
    records = []
    for e in range(jobs):
        if mode == "abab":
            variants = ["base", "pr"] * runs
        else:
            variants = ["base"] * runs + ["pr"] * runs
        total = len(variants)
        for order, variant in enumerate(variants):
            v = 1000.0 * (1 + drift * order / total) * (1 + rng.normal(0, 0.003))
            records.append(
                make_record(
                    experimentId=f"{mode}-{e}",
                    mode=mode,
                    variant=variant,
                    runIndex=order // 2 if mode == "abab" else order % runs,
                    order=order,
                    metrics={"lcp": v, "fcp": v, "tbt": 0.0, "cls": 0.0, "si": v, "ttfb": 2.0},
                )
            )
    return records


def test_wilson_contains_proportion():
    lo, hi = wilson(5, 100)
    assert lo < 0.05 < hi
    assert wilson(0, 10)[0] == 0.0


def test_sequential_turns_drift_into_false_alarms():
    df = to_frame(drifting_jobs("abab", 30) + drifting_jobs("sequential", 30, seed=4))
    jobs = job_stats(df, metrics=("fcp",))
    summary = mode_summary(jobs, ["throttling"]).set_index("mode")
    # a 2% slowdown over the job splits into ~1% between the halves of a sequential series
    assert summary.loc["sequential", "fpr"] > 0.9
    assert summary.loc["abab", "fpr"] < 0.2
    assert summary.loc["sequential", "effect_mean"] > 0.005
    cmp = compare_modes(jobs, ["throttling"]).iloc[0]
    assert cmp["fisher_p"] < 0.001


def test_no_drift_no_difference():
    df = to_frame(drifting_jobs("abab", 30, drift=0.0) + drifting_jobs("sequential", 30, drift=0.0, seed=4))
    summary = mode_summary(job_stats(df, metrics=("fcp",)), ["throttling"]).set_index("mode")
    assert summary["fpr"].max() < 0.2


def test_holm():
    assert holm(np.array([0.01, 0.04, 0.5])).tolist() == [True, False, False]
    assert holm(np.array([0.001, 0.02])).tolist() == [True, True]
    assert not holm(np.array([0.2, 0.3])).any()


def test_pr_level_counts_jobs_not_metrics():
    df = to_frame(drifting_jobs("abab", 10) + drifting_jobs("sequential", 10, seed=4))
    pr = pr_level(job_stats(df, metrics=("fcp", "lcp", "si")))
    assert len(pr) == 20
    summary = pr_summary(pr, ["throttling"]).set_index("mode")
    assert summary.loc["sequential", "any_holm"] > summary.loc["abab", "any_holm"]
