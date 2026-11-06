"""Exploratory distribution-shape and serial-dependence simulations, not measured browser power."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from .methods import default_methods, permutation_mean
from .rq3 import wilson


def scenarios(n: int, reps: int, seed: int):
    rng = np.random.default_rng(seed)
    b = rng.lognormal(np.log(100) - .02**2 / 2, .02, (reps, n))
    p = rng.lognormal(np.log(100) - .02**2 / 2, .02, (reps, n))
    yield "iid_null", "false_alarm", b, p
    yield "location_5pct", "detection", b, p * 1.05
    yield "rare_stall_15pct_plus100", "detection", b, p + (rng.random((reps, n)) < .15) * 100
    heavy_b = rng.lognormal(np.log(100) - .5**2 / 2, .5, (reps, n))
    heavy_p = rng.lognormal(np.log(100) - .5**2 / 2, .5, (reps, n))
    yield "heavy_tail_null", "false_alarm", heavy_b, heavy_p
    yield "heavy_tail_shift_10pct", "detection", heavy_b, heavy_p * 1.1
    # Same population mean, different distributions: rejection is NOT a false positive
    # for methods whose null is equality of distributions/probabilistic superiority.
    yield "variance_change_same_mean", "distribution_change", b, heavy_p
    eps = rng.normal(0, .01 * np.sqrt(1 - .8**2), (reps, 2*n))
    x = np.empty_like(eps); x[:, 0] = rng.normal(0, .01, reps)
    for t in range(1, 2*n): x[:, t] = .8*x[:, t-1] + eps[:, t]
    values = 100 * np.exp(x)
    yield "ar1_null_abab", "false_alarm", values[:, ::2], values[:, 1::2]
    yield "ar1_null_sequential", "false_alarm", values[:, :n], values[:, n:]


def run(reps: int = 500, seed: int = 20261030):
    rows = []
    methods = default_methods() + [permutation_mean()]
    for n in (10, 20):
        for scenario, interpretation, b, p in scenarios(n, reps, seed):
            # All rules use the same complete simulated experiments, without method-specific caps.
            for method in methods:
                start = time.perf_counter(); detected = method(b, p)
                k = int(detected.sum()); lo, hi = wilson(k, reps)
                rows.append({"scenario": scenario, "interpretation": interpretation, "n": n,
                             "method": method.name, "reps": reps, "flagged": k, "rate": k/reps,
                             "lo": lo, "hi": hi, "analysis_seconds": time.perf_counter()-start})
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--reps", type=int, default=500)
    args = parser.parse_args()
    if args.reps < 1: parser.error("--reps must be positive")
    args.out.mkdir(parents=True, exist_ok=True)
    run(args.reps).to_csv(args.out / "stress.csv", index=False)
    (args.out / "manifest.json").write_text(json.dumps({"seed": 20261030, "reps": args.reps,
        "type": "exploratory simulated data", "paired_draws_across_methods": True,
        "not_browser_measurements": True}, indent=2)+"\n")


if __name__ == "__main__": main()
