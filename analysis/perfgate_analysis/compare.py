"""Candidate browser gate and collector-independent statistical comparison kernel.

Exit codes: 0 no regression detected, 1 regression, 2 invalid data, 3 usage/runtime error.
The percentile intervals are descriptive pointwise intervals, not simultaneous guarantees.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

from .load import load_runs
from .quality import comparison_issues
from .rq3 import holm

POLICY = "browser-candidate-2026-10-30"
MARGINS = {"fcp": (0.01, 0.0), "lcp": (0.01, 0.0), "tbt": (0.05, 5.0), "cls": (0.0, 0.005)}


@dataclass(frozen=True)
class Samples:
    name: str
    base: np.ndarray
    pr: np.ndarray
    relative_margin: float
    absolute_margin: float
    unit: str


def compare_samples(samples: list[Samples], alpha: float = .05, boots: int = 1999, seed: int = 20261030) -> list[dict]:
    """Lower-is-better, nonnegative metrics. One Holm family over all supplied metrics/pages."""
    if not samples or len({s.name for s in samples}) != len(samples):
        raise ValueError("nonempty, uniquely named metric family required")
    if not 0 < alpha < 1 or boots < 99:
        raise ValueError("invalid alpha or bootstrap count")
    rows = []
    for s in samples:
        b, p = np.asarray(s.base, float), np.asarray(s.pr, float)
        if b.ndim != 1 or p.ndim != 1 or len(b) != len(p) or len(b) < 5:
            raise ValueError(f"{s.name}: balanced samples with at least five measurements required")
        if not np.isfinite(np.r_[b, p]).all() or (np.r_[b, p] < 0).any():
            raise ValueError(f"{s.name}: finite, nonnegative measurements required")
        if not np.isfinite([s.relative_margin, s.absolute_margin]).all() or min(s.relative_margin, s.absolute_margin) < 0:
            raise ValueError("invalid margin")
        bm, pm = float(np.median(b)), float(np.median(p))
        shift = pm - bm
        # Stable per-metric seed: output does not depend on the input family order.
        name_seed = int.from_bytes(hashlib.sha256(s.name.encode()).digest()[:4], "big")
        rng = np.random.default_rng(seed + name_seed)
        mb = np.median(b[rng.integers(len(b), size=(boots, len(b)))], axis=1)
        mp = np.median(p[rng.integers(len(p), size=(boots, len(p)))], axis=1)
        interval = np.quantile(mp - mb, [alpha / 2, 1 - alpha / 2]).tolist()
        margin = max(s.absolute_margin, s.relative_margin * bm)
        rows.append({"name": s.name, "unit": s.unit, "n": len(b), "base_median": bm,
                     "pr_median": pm, "absolute_effect": shift,
                     "relative_effect": shift / bm if bm > 0 else None,
                     "absolute_effect_interval": interval, "interval_level": 1 - alpha,
                     "margin_absolute": margin, "above_margin": bool(shift > margin),
                     "p": float(mannwhitneyu(p, b, alternative="greater", method="asymptotic").pvalue)})
    rejected = holm(np.array([r["p"] for r in rows]), alpha)
    for row, reject in zip(rows, rejected):
        row["holm_rejected"] = bool(reject)
        row["regression"] = bool(reject and row["above_margin"])
    return rows


def compare_frame(df: pd.DataFrame, runs: int = 20, strict: bool = True, boots: int = 1999) -> dict:
    result = {"schema_version": 1, "policy": POLICY, "status": "invalid", "runs_per_variant": runs,
              "alpha": .05, "correction": "holm", "metrics": [], "issues": [],
              "limitations": ["Candidate policy; prospective validation is pending.",
                              "No detected regression is not proof of equivalence.",
                              "Bootstrap intervals are pointwise and assume independent loads; they do not determine the verdict."]}
    if df.empty:
        result["issues"].append("no measurements")
        return result
    if runs not in (10, 20):
        result["issues"].append("candidate browser policy supports 10 or 20 loads per variant")
        return result
    if df.groupby("app").experiment.nunique().gt(1).any():
        result["issues"].append("one comparison per page required; do not pool repeated jobs")
    for column in ("mode", "throttling", "warmup", "chrome", "lighthouse", "chrome_binary"):
        if column not in df:
            continue
        if df[column].nunique(dropna=False) != 1:
            result["issues"].append(f"mixed suite {column}")
    samples = []
    for exp, g in df.groupby("experiment", sort=True):
        issues = comparison_issues(g, tuple(MARGINS), min_runs=runs,
                                   expected_runs=runs if strict else None, require_network=strict)
        if g["mode"].iloc[0] != "abab" or g.throttling.iloc[0] != "devtools" or not g.warmup.eq(2).all():
            issues.append("candidate policy requires abab/devtools/two warmups")
        if strict and (g.chrome.isna().any() or g.lighthouse.isna().any()):
            issues.append("browser or collector version unknown")
        result["issues"].extend(f"{exp}: {issue}" for issue in issues)
        if issues:
            continue
        g = g.sort_values("order")
        for metric, (relative, absolute) in MARGINS.items():
            b = g.loc[g.variant == "base", metric].to_numpy(float)[:runs]
            p = g.loc[g.variant == "pr", metric].to_numpy(float)[:runs]
            samples.append(Samples(f"{g.app.iloc[0]}/{metric}", b, p, relative, absolute,
                                   "unitless" if metric == "cls" else "ms"))
    if result["issues"]:
        return result
    result["metrics"] = compare_samples(samples, boots=boots)
    result["status"] = "regression" if any(m["regression"] for m in result["metrics"]) else "no_regression_detected"
    return result


def markdown(result: dict) -> str:
    lines = [f"# perfgate: {result['status']}", "", f"Policy: `{result['policy']}` (candidate).", ""]
    if result["issues"]:
        lines += ["Measurement issues:", "", *[f"- {x}" for x in result["issues"]], ""]
    if result["metrics"]:
        lines += ["| Metric | Base | PR | Change | 95% interval, absolute | Regression |",
                  "|---|---:|---:|---:|---:|---|"]
        for m in result["metrics"]:
            relative = f"{m['relative_effect']:+.2%}" if m["relative_effect"] is not None else "relative undefined (zero base)"
            lo, hi = m["absolute_effect_interval"]
            lines.append(f"| {m['name']} ({m['unit']}) | {m['base_median']:.4g} | {m['pr_median']:.4g} | "
                         f"{m['absolute_effect']:+.4g}; {relative} | [{lo:.4g}, {hi:.4g}] | {'yes' if m['regression'] else 'no'} |")
    lines += ["", *[f"- {s}" for s in result["limitations"]], ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    try:
        result = compare_frame(load_runs(args.paths), args.runs)
    except (ValueError, KeyError, TypeError, OSError) as error:
        result = compare_frame(pd.DataFrame(), args.runs)
        result["issues"] = [str(error)]
    (args.out / "comparison.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    (args.out / "comparison.md").write_text(markdown(result))
    print(result["status"])
    raise SystemExit({"no_regression_detected": 0, "regression": 1, "invalid": 2}[result["status"]])


if __name__ == "__main__":
    main()
