"""Descriptive noise statistics of lab metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import GROUP, METRICS


def robust_cv(x: np.ndarray) -> float:
    """1.4826 * MAD / median: CV analogue that tolerates outliers."""
    x = np.asarray(x, dtype=float)
    med = np.median(x)
    if med == 0:
        return float("nan")
    return float(1.4826 * np.median(np.abs(x - med)) / med)


def cv(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    mean = x.mean()
    if len(x) < 2 or mean == 0:
        return float("nan")
    return float(x.std(ddof=1) / mean)


def long_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Clean successful A/A loads in long format: one row per (load, metric)."""
    clean = df[df["ok"] & df["is_aa"]]
    return clean.melt(
        id_vars=[*GROUP, "experiment", "variant", "order", "timestamp"],
        value_vars=METRICS,
        var_name="metric",
    ).dropna(subset=["value"])


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """Pooled noise per configuration and metric."""
    rows = []
    for key, g in long_metrics(df).groupby([*GROUP, "metric"]):
        v = g["value"].to_numpy()
        q1, med, q3 = np.percentile(v, [25, 50, 75])
        rows.append(
            {
                **dict(zip([*GROUP, "metric"], key)),
                "experiments": g["experiment"].nunique(),
                "n": len(v),
                "median": med,
                "iqr": q3 - q1,
                "cv": cv(v),
                "robust_cv": robust_cv(v),
                "zero_share": float(np.mean(v == 0)),
            }
        )
    return pd.DataFrame(rows)


def within_between(df: pd.DataFrame) -> pd.DataFrame:
    """
    within: typical spread inside one CI job (what a same-job base/PR comparison sees);
    between: spread of per-job medians over days (what a stored historical baseline sees).
    """
    rows = []
    for key, g in long_metrics(df).groupby([*GROUP, "metric"]):
        per_exp = g.groupby("experiment")["value"]
        medians = per_exp.median().to_numpy()
        within = per_exp.apply(robust_cv).dropna()
        rows.append(
            {
                **dict(zip([*GROUP, "metric"], key)),
                "experiments": len(medians),
                # nan when every job has a zero median (e.g. CLS of a stable page)
                "within_robust_cv": float(within.median()) if len(within) else float("nan"),
                "between_cv_of_medians": cv(medians),
            }
        )
    return pd.DataFrame(rows)


def failure_rate(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(GROUP)
        .agg(runs=("ok", "size"), failed=("ok", lambda s: int((~s).sum())))
        .assign(failure_rate=lambda t: t["failed"] / t["runs"])
        .reset_index()
    )
