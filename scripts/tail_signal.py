"""Advisory tail signal for TBT, declared in docs/protocols/extensions-2026-11-17.md.

Not part of the gate: the frozen candidate decides the verdict; this signal only adds a
warning that mean TBT rose although the median may not have (rare long tasks).

Rule, per page: one-sided Welch t-test on TBT (PR mean greater), Holm over the pages
of one check; a page warns when its Holm-adjusted p < 0.05 AND the mean rose by more
than max(10%, 20 ms).
"""
from __future__ import annotations

import numpy as np
from scipy.stats import ttest_ind

ALPHA = 0.05
RELATIVE = 0.10
ABSOLUTE_MS = 20.0


def holm(p: list[float]) -> list[float]:
    """Holm step-down adjusted p-values, in input order."""
    order = np.argsort(p)
    adjusted = np.empty(len(p))
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(p) - rank) * p[i]))
        adjusted[i] = running
    return adjusted.tolist()


def tail_signal(pages: dict[str, tuple[np.ndarray, np.ndarray]]) -> dict[str, dict]:
    """pages: name -> (base TBT loads, PR TBT loads). Returns per-page decision and numbers."""
    names = sorted(pages)
    rows = {}
    for name in names:
        base, pr = (np.asarray(x, float) for x in pages[name])
        p = ttest_ind(pr, base, equal_var=False, alternative="greater").pvalue
        diff = pr.mean() - base.mean()
        rows[name] = {"p": 1.0 if np.isnan(p) else float(p), "base_mean": float(base.mean()),
                      "pr_mean": float(pr.mean()), "mean_diff_ms": float(diff),
                      "mean_rel": float(diff / base.mean()) if base.mean() > 0 else None}
    for name, adjusted in zip(names, holm([rows[n]["p"] for n in names])):
        r = rows[name]
        r["p_holm"] = adjusted
        r["warning"] = bool(adjusted < ALPHA and r["mean_diff_ms"] > max(ABSOLUTE_MS, RELATIVE * r["base_mean"]))
    return rows
