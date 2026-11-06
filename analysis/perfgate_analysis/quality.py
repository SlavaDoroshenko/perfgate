"""Validate whole comparisons before selecting samples; never repair a failed job by dropping rows."""
from __future__ import annotations

import numpy as np
import pandas as pd

PROTOCOL = ("app", "epoch", "label", "mode", "throttling", "warmup", "runner", "runner_image", "cpu_model", "chrome", "chrome_binary", "lighthouse")


def comparison_issues(g: pd.DataFrame, metrics=(), min_runs: int = 2,
                      expected_runs: int | None = None, require_network: bool = False) -> list[str]:
    issues = []
    if g.empty:
        return ["empty comparison"]
    if not g["ok"].all():
        issues.append("failed audit or network request")
    if require_network and g["failed_requests"].isna().any():
        issues.append("network status unknown")
    for col in PROTOCOL:
        if col in g and g[col].nunique(dropna=False) != 1:
            issues.append(f"mixed {col}")
    if set(g.variant) != {"base", "pr"}:
        issues.append("both base and pr required")
    sizes = g.groupby("variant").size()
    if "warmup_errors" in g and g.warmup_errors.fillna(0).gt(0).any():
        issues.append("failed warmup")
    if "planned_runs" in g and g.planned_runs.notna().any():
        if g.planned_runs.isna().any() or g.planned_runs.nunique() != 1 or not sizes.eq(g.planned_runs.iloc[0]).all():
            issues.append("recorded slots differ from planned runs")
    if len(sizes) != 2 or sizes.nunique() != 1 or sizes.min() < min_runs:
        issues.append("unbalanced or insufficient samples")
    if expected_runs is not None and (len(sizes) != 2 or not sizes.eq(expected_runs).all()):
        issues.append(f"expected exactly {expected_runs} samples per variant")
    if g.duplicated(["variant", "run_index"]).any() or g.order.duplicated().any():
        issues.append("duplicate measurement slot")
    for _, v in g.groupby("variant"):
        if sorted(v.run_index.tolist()) != list(range(len(v))):
            issues.append("missing or non-contiguous run indices")
            break
    ordered = g.sort_values("order")
    if ordered.order.tolist() != list(range(len(g))):
        issues.append("missing or non-contiguous execution order")
    if len(sizes) == 2 and sizes.nunique() == 1:
        n = int(sizes.iloc[0])
        mode = g["mode"].iloc[0]
        variants = ["base", "pr"] * n if mode == "abab" else ["base"] * n + ["pr"] * n
        if ordered.variant.tolist() != variants:
            issues.append("execution order differs from declared protocol")
        for _, v in ordered.groupby("variant"):
            if v.run_index.tolist() != list(range(n)):
                issues.append("run indices differ from execution order")
                break
    for metric in metrics:
        if metric not in g or not np.isfinite(g[metric].to_numpy(float)).all():
            issues.append(f"missing or non-finite {metric}")
        elif (g[metric] < 0).any():
            issues.append(f"negative {metric}")
    return issues


def valid_comparisons(df: pd.DataFrame, metrics=(), min_runs: int = 2,
                      expected_runs: int | None = None, require_network: bool = False):
    accepted, rejected = [], []
    for exp, g in df.groupby("experiment", sort=False):
        issues = comparison_issues(g, metrics, min_runs, expected_runs, require_network)
        if issues:
            rejected.append({"experiment": exp, "loads": len(g), "reasons": "; ".join(issues)})
        else:
            accepted.append(exp)
    return df[df.experiment.isin(accepted)], pd.DataFrame(rejected, columns=["experiment", "loads", "reasons"])
