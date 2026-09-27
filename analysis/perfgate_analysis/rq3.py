"""
RQ3: does interleaving base and PR loads (abab) beat running them one after another (sequential)?

Both modes spend the same number of loads, so the question is purely about the order. The unit
of analysis is one real A/A job with its original base/PR labels and run order - resampling would
shuffle the order away, and the order is exactly what differs between the modes.

Per job: the relative effect median(pr)/median(base) - 1 (zero by construction on A/A), the
two-sided Mann-Whitney p-value, and the rank correlation of the metric with the position in the
series (drift of the machine during the job). Per mode: false alarm rate with a Wilson interval,
spread and bias of the effect, and how often a gate with a minimum effect would fire.

python -m perfgate_analysis.rq3 <data dirs> --out reports/rq3 --warmup 2 --epoch ...
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import fisher_exact, levene, mannwhitneyu, norm, spearmanr

from . import GROUP
from .load import filter_protocol, load_runs

METRICS = ("fcp", "lcp", "si", "tbt")
ALPHA = 0.05
MIN_EFFECT = 0.01


def wilson(k: int, n: int, level: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return float("nan"), float("nan")
    z = norm.ppf(0.5 + level / 2)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def job_stats(df: pd.DataFrame, metrics: tuple[str, ...] = METRICS) -> pd.DataFrame:
    """One row per (A/A job, metric)."""
    rows = []
    clean = df[df["ok"] & df["is_aa"]]
    for (*key, exp), g in clean.groupby([*GROUP, "experiment"]):
        g = g.sort_values("order")
        for metric in metrics:
            m = g.dropna(subset=[metric])
            base = m.loc[m["variant"] == "base", metric].to_numpy(float)
            pr = m.loc[m["variant"] == "pr", metric].to_numpy(float)
            if len(base) < 5 or len(pr) < 5 or np.median(base) == 0:
                continue
            p = mannwhitneyu(pr, base, alternative="two-sided", method="asymptotic").pvalue
            values = m[metric].to_numpy(float)
            rho = spearmanr(m["order"], values).statistic if np.ptp(values) > 0 else np.nan
            rows.append(
                {
                    **dict(zip(GROUP, key)),
                    "experiment": exp,
                    "timestamp": g["timestamp"].min(),
                    "cpu_model": g["cpu_model"].iloc[0],
                    "metric": metric,
                    "n": min(len(base), len(pr)),
                    "effect": float(np.median(pr) / np.median(base) - 1),
                    "p": 1.0 if np.isnan(p) else float(p),
                    "drift_rho": float(rho),
                }
            )
    return pd.DataFrame(rows)


def mode_summary(jobs: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """False alarms, gate firings, and the distribution of the A/A effect per mode."""
    rows = []
    for key, g in jobs.groupby([*by, "mode"]):
        n = len(g)
        k = int((g["p"] < ALPHA).sum())
        gate = int(((g["p"] < ALPHA) & (g["effect"].abs() > MIN_EFFECT)).sum())
        lo, hi = wilson(k, n)
        eff = g["effect"].to_numpy()
        rows.append(
            {
                **dict(zip([*by, "mode"], key if isinstance(key, tuple) else (key,))),
                "comparisons": n,
                "false_alarms": k,
                "fpr": k / n,
                "fpr_lo": lo,
                "fpr_hi": hi,
                "gate_fires": gate,
                "gate_rate": gate / n,
                "effect_mean": float(eff.mean()),
                "effect_sd": float(eff.std(ddof=1)) if n > 1 else float("nan"),
                "abs_effect_p95": float(np.percentile(np.abs(eff), 95)),
                "abs_drift_rho": float(np.nanmedian(np.abs(g["drift_rho"]))),
            }
        )
    return pd.DataFrame(rows)


def holm(p: np.ndarray, alpha: float = ALPHA) -> np.ndarray:
    """Holm step-down: which of the p-values are rejected at family-wise level alpha."""
    order = np.argsort(p)
    reject = np.zeros(len(p), dtype=bool)
    for rank, i in enumerate(order):
        if p[i] > alpha / (len(p) - rank):
            break
        reject[i] = True
    return reject


def pr_level(jobs: pd.DataFrame) -> pd.DataFrame:
    """
    What a pull request sees: one verdict per job over all its metrics. A job raises an alarm if
    any metric is flagged - without correction, with Holm, and with Holm plus the 1% minimum effect.
    Metrics of one job are correlated, so this is also the honest unit for comparing the modes.
    """
    rows = []
    for (*key, exp), g in jobs.groupby([*GROUP, "experiment"]):
        p = g["p"].to_numpy()
        big = g["effect"].abs().to_numpy() > MIN_EFFECT
        h = holm(p)
        rows.append(
            {
                **dict(zip(GROUP, key)),
                "experiment": exp,
                "metrics": len(g),
                "any_raw": bool((p < ALPHA).any()),
                "any_holm": bool(h.any()),
                "any_holm_gate": bool((h & big).any()),
            }
        )
    return pd.DataFrame(rows)


def pr_summary(pr: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    rows = []
    for key, g in pr.groupby([*by, "mode"]):
        n = len(g)
        row = {**dict(zip([*by, "mode"], key if isinstance(key, tuple) else (key,))), "jobs": n}
        for col in ("any_raw", "any_holm", "any_holm_gate"):
            k = int(g[col].sum())
            lo, hi = wilson(k, n)
            row |= {col: k / n, f"{col}_lo": lo, f"{col}_hi": hi}
        rows.append(row)
    out = pd.DataFrame(rows)
    # sequential vs abab on the job level: independent units, so Fisher is valid here
    tests = []
    for key, g in pr.groupby(by):
        a, s = g[g["mode"] == "abab"], g[g["mode"] == "sequential"]
        if len(a) and len(s):
            t = [[int(s["any_holm"].sum()), int((~s["any_holm"]).sum())],
                 [int(a["any_holm"].sum()), int((~a["any_holm"]).sum())]]
            tests.append({**dict(zip(by, key if isinstance(key, tuple) else (key,))),
                          "fisher_p_holm": float(fisher_exact(t).pvalue)})
    return out.merge(pd.DataFrame(tests), on=by, how="left") if tests else out


def compare_modes(jobs: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """sequential vs abab: Fisher test on false alarms, Brown-Forsythe test on effect spread."""
    rows = []
    for key, g in jobs.groupby(by):
        a = g[g["mode"] == "abab"]
        s = g[g["mode"] == "sequential"]
        if len(a) < 5 or len(s) < 5:
            continue
        fa = [[int((s["p"] < ALPHA).sum()), int((s["p"] >= ALPHA).sum())],
              [int((a["p"] < ALPHA).sum()), int((a["p"] >= ALPHA).sum())]]
        rows.append(
            {
                **dict(zip(by, key if isinstance(key, tuple) else (key,))),
                "n_abab": len(a),
                "n_sequential": len(s),
                "fpr_abab": (a["p"] < ALPHA).mean(),
                "fpr_sequential": (s["p"] < ALPHA).mean(),
                "fisher_p": float(fisher_exact(fa).pvalue),
                "sd_ratio": float(s["effect"].std(ddof=1) / a["effect"].std(ddof=1)),
                "spread_p": float(levene(s["effect"], a["effect"], center="median").pvalue),
            }
        )
    return pd.DataFrame(rows)


def plot_effects(jobs: pd.DataFrame, out: Path) -> None:
    """Per-job A/A effect by mode: the spread is the noise floor of a real comparison."""
    for (app, throttling), g in jobs.groupby(["app", "throttling"]):
        metrics = [m for m in METRICS if m in set(g["metric"])]
        fig, axes = plt.subplots(1, len(metrics), figsize=(3.2 * len(metrics), 3.6), squeeze=False)
        for ax, metric in zip(axes[0], metrics):
            data = [g[(g["metric"] == metric) & (g["mode"] == mode)]["effect"] * 100 for mode in ("abab", "sequential")]
            ax.boxplot(data, tick_labels=["abab", "sequential"], showfliers=True)
            ax.axhline(0, color="grey", lw=0.8)
            ax.set_title(metric.upper(), fontsize=9)
            ax.set_ylabel("A/A effect, %" if metric == metrics[0] else "")
        fig.suptitle(f"{app}, {throttling}: median(PR)/median(base) − 1 per job", fontsize=9)
        fig.tight_layout()
        fig.savefig(out / f"effects_{app}_{throttling}.png", dpi=150)
        plt.close(fig)


def plot_fpr(summary: pd.DataFrame, out: Path) -> None:
    """False alarm rate with Wilson intervals, pooled per throttling mode."""
    fig, ax = plt.subplots(figsize=(6, 3.6))
    labels, x = [], 0
    for throttling, g in summary.groupby("throttling"):
        for mode, color in (("abab", "tab:blue"), ("sequential", "tab:orange")):
            r = g[g["mode"] == mode].iloc[0]
            ax.errorbar(x, r["fpr"] * 100, yerr=[[(r["fpr"] - r["fpr_lo"]) * 100], [(r["fpr_hi"] - r["fpr"]) * 100]],
                        fmt="o", color=color, capsize=4)
            labels.append(f"{throttling}\n{mode}")
            x += 1
    ax.axhline(ALPHA * 100, color="grey", ls="--", lw=0.8, label="nominal 5%")
    ax.set_xticks(range(len(labels)), labels, fontsize=8)
    ax.set_ylabel("A/A false alarms, % (95% CI)")
    ax.set_title("Mann-Whitney on real job order, FCP/LCP/SI pooled", fontsize=9)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "fpr_by_mode.png", dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--out", default="reports/rq3")
    parser.add_argument("--warmup", type=int, default=None)
    parser.add_argument("--epoch", action="append")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    df = filter_protocol(load_runs(args.paths), args.warmup, args.epoch)
    df = df[df["runner"].str.startswith("gha:")]
    jobs = job_stats(df)
    if jobs.empty:
        raise SystemExit("no A/A jobs after filtering")
    stable = jobs[jobs["metric"] != "tbt"]
    tables = {
        "jobs": jobs,
        "by_config": mode_summary(jobs, ["app", "throttling", "metric"]),
        "pooled_stable": mode_summary(stable, ["throttling"]),
        "pooled_tbt": mode_summary(jobs[jobs["metric"] == "tbt"], ["throttling"]),
        "compare_config": compare_modes(jobs, ["app", "throttling", "metric"]),
        "compare_pooled": compare_modes(stable, ["throttling"]),
    }
    pr = pr_level(jobs)
    tables["pr_jobs"] = pr
    tables["pr_level"] = pr_summary(pr, ["throttling"])
    tables["pr_level_app"] = pr_summary(pr, ["app", "throttling"])
    for name, t in tables.items():
        t.to_csv(out / f"{name}.csv", index=False)
    plot_effects(jobs, out)
    plot_fpr(tables["pooled_stable"], out)

    with pd.option_context("display.width", 200, "display.max_rows", 200, "display.precision", 4):
        print(f"{jobs['experiment'].nunique()} A/A jobs")
        for name in ("pooled_stable", "compare_pooled", "pooled_tbt", "pr_level", "pr_level_app"):
            print(f"\n{name}:\n{tables[name].to_string(index=False)}")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
