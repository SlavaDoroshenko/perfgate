"""
RQ2: compare detection methods on identical comparisons.

Every method sees exactly the same resampled draws of real A/A loads, so differences in
the results come from the rule, not from the luck of the draw. False alarm rate is the
detection rate at delta = 0; power is the rate at delta > 0; MDE is the smallest delta a
method detects with the target power.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import GROUP
from .methods import Method, default_methods

DELTAS = np.array([0.0, 0.005, 0.01, 0.02, 0.03, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3])
SAMPLE_SIZES = (5, 10, 20)


@dataclass(frozen=True)
class EvalConfig:
    reps: int = 1000
    seed: int = 20260921
    target_power: float = 0.8


def aa_experiments(df: pd.DataFrame, metric: str) -> dict[tuple, list[np.ndarray]]:
    """Clean A/A loads of one metric, grouped by configuration and job."""
    clean = df[df["ok"] & df["is_aa"]].dropna(subset=[metric])
    return {
        key: [e[metric].to_numpy() for _, e in g.groupby("experiment")]
        for key, g in clean.groupby(GROUP)
    }


def _draws(experiments: list[np.ndarray], n: int, reps: int, rng: np.random.Generator):
    """Two disjoint subsamples of n loads, drawn inside one job, stacked over jobs."""
    usable = [np.asarray(e, dtype=float) for e in experiments if len(e) >= 2 * n]
    if not usable:
        return None, None
    per = max(1, -(-reps // len(usable)))
    base, pr = [], []
    for values in usable:
        idx = rng.permuted(np.tile(np.arange(len(values)), (per, 1)), axis=1)
        base.append(values[idx[:, :n]])
        pr.append(values[idx[:, n : 2 * n]])
    return np.vstack(base), np.vstack(pr)


def evaluate(
    df: pd.DataFrame,
    methods: list[Method] | None = None,
    metrics: tuple[str, ...] = ("fcp", "lcp", "tbt"),
    sizes: tuple[int, ...] = SAMPLE_SIZES,
    deltas: np.ndarray = DELTAS,
    cfg: EvalConfig = EvalConfig(),
) -> pd.DataFrame:
    methods = methods or default_methods()
    rows = []
    for metric in metrics:
        for key, experiments in aa_experiments(df, metric).items():
            for n in sizes:
                rng = np.random.default_rng(cfg.seed)
                base, pr = _draws(experiments, n, cfg.reps, rng)
                if base is None:
                    continue
                # a metric that is constant at zero cannot be shifted multiplicatively
                if np.median(base) == 0:
                    continue
                for delta in deltas:
                    shifted = pr * (1 + delta)
                    for m in methods:
                        b, p = (base, shifted) if m.max_reps is None else (base[: m.max_reps], shifted[: m.max_reps])
                        rows.append(
                            {
                                **dict(zip(GROUP, key)),
                                "metric": metric,
                                "n": n,
                                "loads": m.loads or n,
                                "delta": float(delta),
                                "method": m.name,
                                "reps": len(b),
                                "rate": float(np.mean(m(b, p))),
                            }
                        )
    return pd.DataFrame(rows)


def summarize(rates: pd.DataFrame, cfg: EvalConfig = EvalConfig()) -> pd.DataFrame:
    """False alarm rate and MDE per configuration, metric, sample size and method."""
    rows = []
    for key, g in rates.groupby([*GROUP, "metric", "n", "loads", "method"]):
        g = g.sort_values("delta")
        positive = g[g["delta"] > 0]
        hit = positive[positive["rate"] >= cfg.target_power]
        rows.append(
            {
                **dict(zip([*GROUP, "metric", "n", "loads", "method"], key)),
                "false_alarm_rate": float(g.loc[g["delta"] == 0, "rate"].iloc[0]),
                "mde": float(hit["delta"].iloc[0]) if len(hit) else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def evaluate_real_jobs(
    df: pd.DataFrame,
    methods: list[Method] | None = None,
    metrics: tuple[str, ...] = ("fcp", "lcp", "tbt"),
) -> pd.DataFrame:
    """
    Apply every method to the real base/PR labels of each job, keeping the run order.
    A/A jobs measure false alarms in the wild; control jobs measure real detection.
    """
    methods = methods or default_methods()
    rows = []
    ok = df[df["ok"]]
    for (*key, exp, is_aa), g in ok.groupby([*GROUP, "experiment", "is_aa"]):
        for metric in metrics:
            b = g[g["variant"] == "base"][metric].dropna().to_numpy()
            p = g[g["variant"] == "pr"][metric].dropna().to_numpy()
            k = min(len(b), len(p))
            if k < 2 or np.median(b[:k]) == 0:
                continue
            base, pr = b[:k].reshape(1, -1), p[:k].reshape(1, -1)
            for m in methods:
                rows.append(
                    {
                        **dict(zip(GROUP, key)),
                        "experiment": exp,
                        "kind": "aa" if is_aa else "control",
                        "metric": metric,
                        "n": k,
                        "method": m.name,
                        "flagged": bool(m(base, pr)[0]),
                        "effect": float(np.median(pr) / np.median(base) - 1),
                    }
                )
    return pd.DataFrame(rows)
