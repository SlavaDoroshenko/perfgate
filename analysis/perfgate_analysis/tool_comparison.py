"""Summarize actual sitespeed compare output beside the Lighthouse samples.

python -m perfgate_analysis.tool_comparison <downloaded artifact directory> --out reports/sitespeed
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

from .methods import cliffs_delta, hodges_lehmann
from .rq3 import holm

METRICS = {"fcp": "firstContentfulPaint", "lcp": "largestContentfulPaint",
           "tbt": "totalBlockingTime", "cls": "cumulativeLayoutShift"}


def summarize(root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, metadata = [], []
    for file in sorted(root.rglob("metadata.json")):
        meta = json.loads(file.read_text())
        folder = file.parent
        comparison = json.loads((folder / "compare.json").read_text())
        loads = [json.loads(line) for line in (folder / "lighthouse.jsonl").read_text().splitlines() if line]
        if len(loads) != 2 * meta["runs"] or any(r["error"] or (r.get("failedRequests") or 0) > 0 for r in loads):
            raise ValueError(f"{folder}: invalid Lighthouse samples")
        common = {k: meta[k] for k in ("case", "repeat", "runs", "github_run")}
        metadata.append(meta)
        for tool in ("sitespeed", "lighthouse"):
            group = []
            for metric, name in METRICS.items():
                if tool == "sitespeed":
                    result = comparison["metrics"]["googleWebVitals"][name]
                    b, p = np.array(result["baseline"]["values"]), np.array(result["current"]["values"])
                    observed_p = result["statisticalTestU"]
                    pvalue = float(observed_p) if isinstance(observed_p, (int, float)) else 1.0
                    native = bool(result["isSignificant"] > 0)
                else:
                    b = np.array([r["metrics"][metric] for r in loads if r["variant"] == "base"])
                    p = np.array([r["metrics"][metric] for r in loads if r["variant"] == "pr"])
                    pvalue = float(mannwhitneyu(p, b, alternative="greater", method="asymptotic").pvalue)
                    native = pvalue < 0.05
                if len(b) != meta["runs"] or len(p) != meta["runs"] or not np.isfinite(np.r_[b, p]).all():
                    raise ValueError(f"{folder}: incomplete {tool} {metric}")
                shift = float(np.median(p) - np.median(b))
                effect = shift / np.median(b) if np.median(b) > 0 else np.nan
                large = shift > 0.005 if metric == "cls" else effect > (0.05 if metric == "tbt" else 0.01)
                group.append({**common, "tool": tool, "metric": metric, "base_median": np.median(b),
                    "pr_median": np.median(p), "effect": effect, "absolute_shift": shift,
                    "p": pvalue, "native_significant": native, "above_margin": large,
                    "cliffs_delta": float(cliffs_delta(b, p)[0]),
                    "hl": float(hodges_lehmann(b, p)[0])})
            corrected = holm(np.array([r["p"] for r in group]))
            for row, reject in zip(group, corrected):
                row["holm_and_margin"] = bool(reject and row["above_margin"])
            rows.extend(group)
    if not metadata:
        raise ValueError("no completed comparisons (metadata.json) found")
    return pd.DataFrame(rows), pd.DataFrame(metadata)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows, meta = summarize(args.root)
    args.out.mkdir(parents=True, exist_ok=True)
    rows.to_csv(args.out / "comparisons.csv", index=False)
    meta.to_csv(args.out / "metadata.csv", index=False)
    print(rows.groupby(["case", "tool", "metric"])[["effect", "native_significant", "holm_and_margin"]].agg(["median", "sum"]).to_string())
    print(meta.groupby("case")[["sitespeed_seconds", "lighthouse_seconds"]].median().to_string())


if __name__ == "__main__":
    main()
