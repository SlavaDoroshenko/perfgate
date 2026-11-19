"""Advisory rare long-task rule, second version, declared in docs/protocols/followup-2026-11-19.md.

Replaces the Welch rule of scripts/tail_signal.py, which cannot reach p < 0.05 reliably
when only a few PR loads are slow: those loads inflate the variance they are divided by
(with 3 slow loads of 20 and quiet base loads, t stays near 1.8 whatever the stall
length). This rule counts slow loads instead.

Rule, per page: threshold = median(base TBT) + max(100 ms, 20% of that median). A page
warns when at least two PR loads are above the threshold and no base load is. Not part
of the gate: the verdict is unchanged.
"""
from __future__ import annotations

import numpy as np

ABSOLUTE_MS = 100.0
RELATIVE = 0.20
MIN_PR_LOADS = 2


def tail_exceedance(pages: dict[str, tuple[np.ndarray, np.ndarray]]) -> dict[str, dict]:
    """pages: name -> (base TBT loads, PR TBT loads). Returns per-page decision and numbers."""
    rows = {}
    for name in sorted(pages):
        base, pr = (np.asarray(x, float) for x in pages[name])
        median = float(np.median(base))
        threshold = median + max(ABSOLUTE_MS, RELATIVE * median)
        slow_pr, slow_base = int((pr > threshold).sum()), int((base > threshold).sum())
        rows[name] = {"base_median": median, "threshold_ms": threshold, "slow_pr": slow_pr,
                      "slow_base": slow_base, "n_base": len(base), "n_pr": len(pr),
                      "warning": slow_pr >= MIN_PR_LOADS and slow_base == 0}
    return rows
