"""
Change point detection on the history of the main branch.

The same-job comparison answers "did this PR slow the page down". It cannot see a slow creep -
ten PRs of +0.5% each pass every gate - nor a regression merged without the check. For that
the tool keeps one number per scheduled job (the median of its base loads) and looks for a
step in the series.

The history is much noisier than a single job: every job lands on a different runner CPU
(`rq1-preliminary.md`, section 2). So the series is examined twice: raw, and adjusted for the
CPU model by dividing every job median by the median of the jobs that ran on the same model.

Method: E-Divisive with a single change point (energy statistic, permutation test), the family
used by MongoDB, Apache Otava (Hunter) and Nyrkiö. Evaluation on real A/A history: windows of
consecutive jobs, no change by construction (false alarms), and the same windows with a
multiplicative step of known size injected halfway (power). The smallest step detected in 80% of
windows is the history MDE, directly comparable with the same-job MDE of RQ1.

python -m perfgate_analysis.history <data dirs> --out reports/history --warmup 2 --epoch ...
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .load import filter_protocol, load_runs

STEPS = np.array([0.0, 0.005, 0.01, 0.02, 0.03, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3])
SERIES_KEY = ["app", "throttling", "mode"]


@dataclass(frozen=True)
class CpdConfig:
    window: int = 20
    min_size: int = 4
    permutations: int = 199
    alpha: float = 0.05
    target_power: float = 0.8
    seed: int = 20260927


def job_series(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """One row per A/A job: time, CPU model and the median of its base loads."""
    clean = df[df["ok"] & df["is_aa"] & (df["variant"] == "base")].dropna(subset=[metric])
    rows = (
        clean.groupby([*SERIES_KEY, "epoch", "experiment"])
        .agg(timestamp=("timestamp", "min"), cpu_model=("cpu_model", "first"), value=(metric, "median"))
        .reset_index()
        .sort_values("timestamp")
    )
    rows["metric"] = metric
    return rows


def cpu_adjusted(series: pd.DataFrame) -> pd.Series:
    """Job median relative to the typical median on the same CPU model within the series."""
    typical = series.groupby("cpu_model")["value"].transform("median")
    return series["value"] / typical


def _energy_split(x: np.ndarray, min_size: int) -> tuple[int, float]:
    """Best single split of a 1-d series by the energy (E-Divisive, alpha = 1) statistic."""
    n = len(x)
    d = np.abs(x[:, None] - x[None, :])
    # 2-d prefix sums: every block sum of the distance matrix in O(1), all splits at once
    s = np.zeros((n + 1, n + 1))
    s[1:, 1:] = d.cumsum(0).cumsum(1)
    k = np.arange(max(min_size, 2), n - max(min_size, 2) + 1)
    m, l = k, n - k
    within_a = s[k, k]
    between = s[k, n] - s[k, k]
    within_b = s[n, n] - s[k, n] - s[n, k] + s[k, k]
    q = (m * l / n) * (2 * between / (m * l) - within_a / (m * (m - 1)) - within_b / (l * (l - 1)))
    i = int(np.argmax(q))
    return int(k[i]), float(q[i])


def e_divisive(x: np.ndarray, cfg: CpdConfig, rng: np.random.Generator) -> tuple[int, float]:
    """Location of the most likely change point and its permutation p-value."""
    x = np.asarray(x, dtype=float)
    k, q = _energy_split(x, cfg.min_size)
    exceed = sum(_energy_split(rng.permutation(x), cfg.min_size)[1] >= q for _ in range(cfg.permutations))
    return k, (exceed + 1) / (cfg.permutations + 1)


def detection_rates(values: np.ndarray, steps: np.ndarray, cfg: CpdConfig, rng: np.random.Generator) -> np.ndarray:
    """Share of windows where a step of each size, injected halfway, is detected."""
    windows = [values[i : i + cfg.window] for i in range(0, len(values) - cfg.window + 1)]
    if not windows:
        return np.full(len(steps), np.nan)
    half = cfg.window // 2
    rates = []
    for step in steps:
        hits = 0
        for w in windows:
            shifted = w.copy()
            shifted[half:] *= 1 + step
            hits += e_divisive(shifted, cfg, rng)[1] < cfg.alpha
        rates.append(hits / len(windows))
    return np.array(rates)


def evaluate(df: pd.DataFrame, metrics: tuple[str, ...], cfg: CpdConfig = CpdConfig()) -> pd.DataFrame:
    rows = []
    for metric in metrics:
        series = job_series(df, metric)
        for key, s in series.groupby([*SERIES_KEY, "epoch"]):
            if len(s) < cfg.window or s["value"].median() == 0:
                continue
            for variant, values in (("raw", s["value"].to_numpy()), ("cpu-adjusted", cpu_adjusted(s).to_numpy())):
                rng = np.random.default_rng(cfg.seed)
                rates = detection_rates(values, STEPS, cfg, rng)
                for step, rate in zip(STEPS, rates):
                    rows.append(
                        {
                            **dict(zip([*SERIES_KEY, "epoch"], key)),
                            "metric": metric,
                            "series": variant,
                            "jobs": len(s),
                            "cpu_models": s["cpu_model"].nunique(),
                            "step": float(step),
                            "rate": float(rate),
                        }
                    )
    return pd.DataFrame(rows)


def summarize(rates: pd.DataFrame, cfg: CpdConfig = CpdConfig()) -> pd.DataFrame:
    rows = []
    for key, g in rates.groupby([*SERIES_KEY, "epoch", "metric", "series"]):
        g = g.sort_values("step")
        hit = g[(g["step"] > 0) & (g["rate"] >= cfg.target_power)]
        rows.append(
            {
                **dict(zip([*SERIES_KEY, "epoch", "metric", "series"], key)),
                "jobs": int(g["jobs"].iloc[0]),
                "false_alarm_rate": float(g.loc[g["step"] == 0, "rate"].iloc[0]),
                "mde": float(hit["step"].iloc[0]) if len(hit) else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def plot_series(df: pd.DataFrame, metric: str, out: Path) -> None:
    """Job medians over time coloured by CPU model: the hardware lottery made visible."""
    series = job_series(df, metric)
    for key, s in series.groupby(SERIES_KEY):
        if len(s) < 10 or s["value"].median() == 0:
            continue
        fig, axes = plt.subplots(2, 1, figsize=(9, 6.2), sharex=True)
        adj = cpu_adjusted(s)
        for cpu, c in s.groupby("cpu_model"):
            axes[0].scatter(c["timestamp"], c["value"], s=14, label=cpu)
            axes[1].scatter(c["timestamp"], adj[c.index] * 100 - 100, s=14)
        axes[0].set_ylabel(f"job median {metric.upper()}, ms")
        axes[1].set_ylabel("vs same CPU, %")
        axes[1].axhline(0, color="grey", lw=0.8)
        axes[0].set_title(f"{' / '.join(key)}: history of the base median", fontsize=9)
        fig.autofmt_xdate()
        fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=3, fontsize=7, frameon=False)
        fig.tight_layout(rect=(0, 0.07, 1, 1))
        fig.savefig(out / f"history_{metric}_{'_'.join(key)}.png", dpi=150)
        plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--out", default="reports/history")
    parser.add_argument("--warmup", type=int, default=None)
    parser.add_argument("--epoch", action="append")
    parser.add_argument("--metrics", default="fcp,lcp,tbt")
    parser.add_argument("--window", type=int, default=CpdConfig.window)
    parser.add_argument("--permutations", type=int, default=CpdConfig.permutations)
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    df = filter_protocol(load_runs(args.paths), args.warmup, args.epoch)
    df = df[df["runner"].str.startswith("gha:") & (df["mode"] == "abab")]
    cfg = CpdConfig(window=args.window, permutations=args.permutations)
    metrics = tuple(args.metrics.split(","))

    rates = evaluate(df, metrics, cfg)
    summary = summarize(rates, cfg)
    rates.to_csv(out / "rates.csv", index=False)
    summary.to_csv(out / "summary.csv", index=False)
    for metric in metrics:
        plot_series(df, metric, out)

    with pd.option_context("display.width", 200, "display.max_rows", 200, "display.precision", 3):
        print(summary.pivot_table(index=["app", "throttling", "metric"], columns="series",
                                  values=["false_alarm_rate", "mde"]).to_string())
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
