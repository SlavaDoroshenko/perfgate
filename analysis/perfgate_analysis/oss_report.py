"""Per-job effects of real library upgrades; these cases have no assumed ground truth."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

from .load import load_runs
from .methods import cliffs_delta, hodges_lehmann
from .rq3 import holm


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    df = load_runs(args.paths)
    df = df[df.label == "vendor"]
    if df.empty or not df.ok.all():
        raise SystemExit("missing or failed vendor measurements; inspect the raw data")
    rows = []
    for exp, g in df.groupby("experiment"):
        group = []
        for metric in ("fcp", "lcp", "tbt", "cls"):
            b = g.loc[g.variant == "base", metric].to_numpy(float)
            p = g.loc[g.variant == "pr", metric].to_numpy(float)
            if len(b) != len(p) or len(b) < 5 or not np.isfinite(np.r_[b, p]).all():
                raise ValueError(f"{exp}: incomplete {metric} comparison")
            shift = float(np.median(p) - np.median(b))
            effect = shift / np.median(b) if np.median(b) > 0 else np.nan
            large = abs(shift) > 0.005 if metric == "cls" else abs(effect) > (0.05 if metric == "tbt" else 0.01)
            group.append({"experiment": exp, "app": g.app.iloc[0], "throttling": g.throttling.iloc[0],
                "metric": metric, "n": len(b), "base_median": float(np.median(b)), "pr_median": float(np.median(p)),
                "effect": effect, "absolute_shift": shift,
                "p": float(mannwhitneyu(p, b, alternative="two-sided", method="asymptotic").pvalue),
                "above_margin": large, "cliffs_delta": float(cliffs_delta(b, p)[0]),
                "hl": float(hodges_lehmann(b, p)[0]), "cpu": g.cpu_model.iloc[0], "app_build": g.epoch.iloc[0]})
        rejected = holm(np.array([r["p"] for r in group]))
        for row, reject in zip(group, rejected):
            row["holm_and_margin"] = bool(reject and row["above_margin"])
        rows.extend(group)
    result = pd.DataFrame(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.out, index=False)
    print(f"{len(df)} loads, {df.experiment.nunique()} jobs, {df.app.nunique()} release pairs")
    print(result.pivot_table(index=["app", "throttling"], columns="metric", values="effect").to_string())


if __name__ == "__main__":
    main()
