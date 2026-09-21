"""
Detection methods under comparison (RQ2).

Every method is a rule that looks at `n` base loads and `n` PR loads and answers one
question: is the PR slower? They are written to work on batches — inputs are 2-D arrays
of shape (replicates, n) — so that thousands of resampled comparisons can be evaluated
on identical draws, which keeps the comparison between methods fair.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from scipy.stats import mannwhitneyu, ttest_ind

Detector = Callable[[np.ndarray, np.ndarray], np.ndarray]


@dataclass(frozen=True)
class Method:
    name: str
    detect: Detector
    # loads consumed per variant: None uses the whole sample, 1 uses a single load
    loads: int | None = None
    # cap on replicates during evaluation, for methods that are expensive per comparison
    max_reps: int | None = None

    def __call__(self, base: np.ndarray, pr: np.ndarray) -> np.ndarray:
        return self.detect(np.asarray(base, dtype=float), np.asarray(pr, dtype=float))


def _ratio(base: np.ndarray, pr: np.ndarray) -> np.ndarray:
    b = np.median(base, axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(b > 0, np.median(pr, axis=1) / np.where(b > 0, b, 1) - 1, np.nan)


def single_run(margin: float) -> Method:
    """One load per variant against a fixed margin — the naive CI check."""

    def detect(base: np.ndarray, pr: np.ndarray) -> np.ndarray:
        with np.errstate(divide="ignore", invalid="ignore"):
            r = np.where(base[:, 0] > 0, pr[:, 0] / base[:, 0] - 1, np.nan)
        return np.nan_to_num(r, nan=-np.inf) > margin

    return Method(f"single-run >{margin:.0%}", detect, loads=1)


def threshold(margin: float) -> Method:
    """Median of n loads against a fixed margin — the Lighthouse CI style rule."""

    def detect(base: np.ndarray, pr: np.ndarray) -> np.ndarray:
        return np.nan_to_num(_ratio(base, pr), nan=-np.inf) > margin

    return Method(f"median >{margin:.0%}", detect)


def mann_whitney(alpha: float = 0.05) -> Method:
    """Rank test, one-sided — the sitespeed.io style rule."""

    def detect(base: np.ndarray, pr: np.ndarray) -> np.ndarray:
        p = mannwhitneyu(pr, base, alternative="greater", axis=1, method="asymptotic").pvalue
        return np.nan_to_num(p, nan=1.0) < alpha

    return Method(f"Mann-Whitney α={alpha}", detect)


def welch_t(alpha: float = 0.05) -> Method:
    """Welch's t-test, one-sided — the rule Mozilla's alerting is built on."""

    def detect(base: np.ndarray, pr: np.ndarray) -> np.ndarray:
        p = ttest_ind(pr, base, axis=1, equal_var=False, alternative="greater").pvalue
        return np.nan_to_num(p, nan=1.0) < alpha

    return Method(f"Welch t α={alpha}", detect)


def significant_and_large(alpha: float = 0.05, min_effect: float = 0.01) -> Method:
    """Significance plus a minimum effect size: a test alone flags differences nobody cares about."""

    mwu = mann_whitney(alpha)

    def detect(base: np.ndarray, pr: np.ndarray) -> np.ndarray:
        return mwu(base, pr) & (np.nan_to_num(_ratio(base, pr), nan=-np.inf) > min_effect)

    return Method(f"MWU α={alpha} & >{min_effect:.0%}", detect)


def bootstrap_ratio(alpha: float = 0.05, min_effect: float = 0.0, boots: int = 499, seed: int = 20260921) -> Method:
    """
    Percentile bootstrap confidence interval of the ratio of medians; a regression is
    reported when the whole interval lies above the minimum effect. Reports an interval
    rather than a verdict, which is what a PR comment should show.
    """

    def detect(base: np.ndarray, pr: np.ndarray) -> np.ndarray:
        rng = np.random.default_rng(seed)
        reps, n = base.shape
        out = np.empty(reps, dtype=bool)
        chunk = max(1, 2_000_000 // (boots * n))
        for start in range(0, reps, chunk):
            b = base[start : start + chunk]
            p = pr[start : start + chunk]
            k = b.shape[0]
            idx_b = rng.integers(0, n, size=(k, boots, n))
            idx_p = rng.integers(0, n, size=(k, boots, n))
            mb = np.median(np.take_along_axis(b[:, None, :], idx_b, axis=2), axis=2)
            mp = np.median(np.take_along_axis(p[:, None, :], idx_p, axis=2), axis=2)
            with np.errstate(divide="ignore", invalid="ignore"):
                # a zero baseline has no ratio: treat it as "no regression detected"
                ratio = np.where(mb > 0, mp / np.where(mb > 0, mb, 1) - 1, -np.inf)
            out[start : start + chunk] = np.percentile(ratio, 100 * alpha, axis=1) > min_effect
        return out

    return Method(
        f"bootstrap CI α={alpha}" + (f" & >{min_effect:.0%}" if min_effect else ""),
        detect,
        max_reps=200,
    )


def default_methods() -> list[Method]:
    """The set compared in RQ2: naive rules, the tests in use today, and the combined rule."""
    return [
        single_run(0.02),
        single_run(0.05),
        threshold(0.02),
        threshold(0.05),
        welch_t(),
        mann_whitney(),
        significant_and_large(min_effect=0.01),
        significant_and_large(min_effect=0.02),
        bootstrap_ratio(),
        bootstrap_ratio(min_effect=0.01),
    ]
