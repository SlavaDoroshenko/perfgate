"""
Empirical minimum detectable effect (MDE) from real A/A measurements.

For a configuration we take every A/A experiment (one CI job), repeatedly draw two
disjoint subsamples of n loads from it, multiply the "pr" subsample by (1 + delta)
and test pr > base with Mann-Whitney U. The rejection rate at delta = 0 is the false
alarm rate, at delta > 0 the power. MDE is the smallest delta with power >= target.

Resampling stays inside one experiment: that is exactly the comparison a same-job
base/PR check performs. Drift across days is analysed separately (noise.within_between).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

from . import GROUP, METRICS

DELTAS = np.array([0.0, 0.01, 0.02, 0.03, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5])
SAMPLE_SIZES = (5, 10, 20)


@dataclass(frozen=True)
class PowerConfig:
    alpha: float = 0.05
    target_power: float = 0.8
    reps: int = 1000
    seed: int = 20260916


def power_curve(
    experiments: list[np.ndarray],
    n: int,
    deltas: np.ndarray = DELTAS,
    cfg: PowerConfig = PowerConfig(),
) -> np.ndarray:
    """Rejection rate for each delta. Experiments with fewer than 2n loads are skipped."""
    usable = [np.asarray(e, dtype=float) for e in experiments if len(e) >= 2 * n]
    if not usable:
        return np.full(len(deltas), np.nan)

    rng = np.random.default_rng(cfg.seed)
    reps_per_exp = max(1, -(-cfg.reps // len(usable)))
    base_parts, pr_parts = [], []
    for values in usable:
        # the same draws are reused for every delta (common random numbers → smooth curves)
        idx = rng.permuted(np.tile(np.arange(len(values)), (reps_per_exp, 1)), axis=1)
        base_parts.append(values[idx[:, :n]])
        pr_parts.append(values[idx[:, n : 2 * n]])
    base = np.vstack(base_parts)
    pr = np.vstack(pr_parts)

    power = np.empty(len(deltas))
    for i, delta in enumerate(deltas):
        p = mannwhitneyu(pr * (1 + delta), base, alternative="greater", axis=1, method="asymptotic").pvalue
        # constant samples (e.g. all-zero TBT) give nan p-values: never a detection
        power[i] = np.mean(np.nan_to_num(p, nan=1.0) < cfg.alpha)
    return power


def mde_from_curve(power: np.ndarray, deltas: np.ndarray = DELTAS, target: float = 0.8) -> float:
    hits = np.flatnonzero((deltas > 0) & (power >= target))
    return float(deltas[hits[0]]) if len(hits) else float("nan")


def _aa_experiments(df: pd.DataFrame, metric: str) -> dict[tuple, list[np.ndarray]]:
    clean = df[df["ok"] & df["is_aa"]].dropna(subset=[metric])
    out: dict[tuple, list[np.ndarray]] = {}
    for key, g in clean.groupby(GROUP):
        out[key] = [e[metric].to_numpy() for _, e in g.groupby("experiment")]
    return out


def power_table(
    df: pd.DataFrame,
    metrics: list[str] = METRICS,
    sample_sizes: tuple[int, ...] = SAMPLE_SIZES,
    deltas: np.ndarray = DELTAS,
    cfg: PowerConfig = PowerConfig(),
) -> pd.DataFrame:
    rows = []
    for metric in metrics:
        for key, experiments in _aa_experiments(df, metric).items():
            for n in sample_sizes:
                curve = power_curve(experiments, n, deltas, cfg)
                for delta, pw in zip(deltas, curve):
                    rows.append({**dict(zip(GROUP, key)), "metric": metric, "n": n, "delta": delta, "power": pw})
    return pd.DataFrame(rows)


def mde_table(power: pd.DataFrame, cfg: PowerConfig = PowerConfig()) -> pd.DataFrame:
    rows = []
    for key, g in power.groupby([*GROUP, "metric", "n"]):
        g = g.sort_values("delta")
        rows.append(
            {
                **dict(zip([*GROUP, "metric", "n"], key)),
                "false_alarm_rate": float(g.loc[g["delta"] == 0, "power"].iloc[0]),
                "mde": mde_from_curve(g["power"].to_numpy(), g["delta"].to_numpy(), cfg.target_power),
            }
        )
    return pd.DataFrame(rows)


def aa_false_alarms(df: pd.DataFrame, metrics: list[str] = METRICS, alpha: float = 0.05) -> pd.DataFrame:
    """
    Two-sided MWU of the real base vs pr labels in each A/A experiment. Unlike the
    resampling above this keeps the run order, so drift during a sequential series shows up.
    """
    rows = []
    for metric in metrics:
        clean = df[df["ok"] & df["is_aa"]].dropna(subset=[metric])
        for key, g in clean.groupby(GROUP):
            p_values = []
            for _, e in g.groupby("experiment"):
                base = e.loc[e["variant"] == "base", metric].to_numpy()
                pr = e.loc[e["variant"] == "pr", metric].to_numpy()
                if len(base) < 2 or len(pr) < 2:
                    continue
                p = mannwhitneyu(pr, base, alternative="two-sided", method="asymptotic").pvalue
                p_values.append(1.0 if np.isnan(p) else p)
            if p_values:
                rows.append(
                    {
                        **dict(zip(GROUP, key)),
                        "metric": metric,
                        "experiments": len(p_values),
                        "false_alarm_rate": float(np.mean(np.array(p_values) < alpha)),
                    }
                )
    return pd.DataFrame(rows)
