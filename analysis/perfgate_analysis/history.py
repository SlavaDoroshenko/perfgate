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
        .agg(
            timestamp=("timestamp", "min"),
            cpu_model=("cpu_model", "first"),
            bench=("benchmark_index", "median"),
            value=(metric, "median"),
        )
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


def welch_split(x: np.ndarray, min_size: int) -> float:
    """
    Largest Welch t-statistic over all splits of the window: the shape of Mozilla Perfherder's
    detector, which compares the points before and after every candidate with a t-test and
    alerts above a fixed t (7 by default there).
    """
    x = np.asarray(x, dtype=float)
    n = len(x)
    best = 0.0
    for k in range(max(min_size, 2), n - max(min_size, 2) + 1):
        a, b = x[:k], x[k:]
        se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
        if se > 0:
            best = max(best, abs(b.mean() - a.mean()) / se)
    return best


# Perfherder's default threshold on the t-statistic
MOZILLA_T = 7.0


def past_adjusted(window: pd.DataFrame, values: np.ndarray, past: pd.DataFrame, how: str, min_jobs: int = 3) -> np.ndarray:
    """
    Adjust a window for the machine using only jobs that ran before it - what a running tool
    knows at the time. `cpu`: divide by the past median on the same CPU model (models seen fewer
    than `min_jobs` times fall back to the past median over all models). `bench`: regress the
    log of the past medians on the log of Lighthouse's benchmarkIndex and remove that slope.
    """
    if how == "cpu":
        overall = past["value"].median()
        ref = past.groupby("cpu_model")["value"].agg(["median", "size"])
        typical = [
            ref.loc[c, "median"] if c in ref.index and ref.loc[c, "size"] >= min_jobs else overall
            for c in window["cpu_model"]
        ]
        return values / np.asarray(typical, dtype=float)
    if how == "bench":
        ok = past[(past["bench"] > 0) & (past["value"] > 0)]
        x, y = np.log(ok["bench"].to_numpy(float)), np.log(ok["value"].to_numpy(float))
        slope = np.polyfit(x, y, 1)[0] if len(ok) >= min_jobs and np.ptp(x) > 0 else 0.0
        centre = np.median(x) if len(x) else 0.0
        bench = np.log(window["bench"].to_numpy(float))
        return values / np.exp(slope * (bench - centre)) / np.median(ok["value"]) if len(ok) else values
    raise ValueError(how)


def online_rates(
    s: pd.DataFrame,
    steps: np.ndarray,
    cfg: CpdConfig,
    rng: np.random.Generator,
    train: int = 12,
) -> list[dict]:
    """
    Windows that only use the past: every window of `cfg.window` jobs after the first `train`
    jobs, with the machine adjustment learned on all jobs before the window. A change of known
    size is put into the raw medians of the second half before adjusting - as a step, or as a
    linear ramp that reaches the size at the last job (the slow creep).
    """
    s = s.reset_index(drop=True)
    half = cfg.window // 2
    ramp = np.r_[np.zeros(half), np.arange(1, cfg.window - half + 1) / (cfg.window - half)]
    jump = np.r_[np.zeros(half), np.ones(cfg.window - half)]
    rows = []
    starts = range(train, len(s) - cfg.window + 1)
    for shape, profile in (("step", jump), ("ramp", ramp)):
        for step in steps:
            hits: dict[tuple[str, str], int] = {}
            for i in starts:
                w, past = s.iloc[i : i + cfg.window], s.iloc[:i]
                raw = w["value"].to_numpy(float) * (1 + step * profile)
                for series, values in (
                    ("raw", raw),
                    ("cpu-past", past_adjusted(w, raw, past, "cpu")),
                    ("bench-past", past_adjusted(w, raw, past, "bench")),
                ):
                    found = {
                        "e-divisive": e_divisive(values, cfg, rng)[1] < cfg.alpha,
                        "mozilla-t": welch_split(values, cfg.min_size) >= MOZILLA_T,
                    }
                    for detector, f in found.items():
                        hits[(series, detector)] = hits.get((series, detector), 0) + int(f)
            n = len(starts)
            for (series, detector), k in hits.items():
                rows.append({"shape": shape, "step": float(step), "series": series, "detector": detector,
                             "windows": n, "rate": k / n if n else float("nan")})
    return rows


def evaluate_online(df: pd.DataFrame, metrics: tuple[str, ...], cfg: CpdConfig = CpdConfig(), train: int = 12) -> pd.DataFrame:
    rows = []
    steps = STEPS[STEPS <= 0.3]
    for metric in metrics:
        series = job_series(df, metric)
        for key, s in series.groupby([*SERIES_KEY, "epoch"]):
            if len(s) < cfg.window + train or s["value"].median() == 0:
                continue
            rng = np.random.default_rng(cfg.seed)
            for r in online_rates(s, steps, cfg, rng, train):
                rows.append({**dict(zip([*SERIES_KEY, "epoch"], key)), "metric": metric, "jobs": len(s), **r})
    return pd.DataFrame(rows)


def summarize_online(rates: pd.DataFrame, cfg: CpdConfig = CpdConfig()) -> pd.DataFrame:
    rows = []
    keys = [*SERIES_KEY, "epoch", "metric", "shape", "series", "detector"]
    for key, g in rates.groupby(keys):
        g = g.sort_values("step")
        hit = g[(g["step"] > 0) & (g["rate"] >= cfg.target_power)]
        rows.append(
            {
                **dict(zip(keys, key)),
                "windows": int(g["windows"].iloc[0]),
                "false_alarm_rate": float(g.loc[g["step"] == 0, "rate"].iloc[0]),
                "mde": float(hit["step"].iloc[0]) if len(hit) else float("nan"),
            }
        )
    return pd.DataFrame(rows)


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
    parser.add_argument("--online", action="store_true",
                        help="past-only adjustment, step and ramp, E-Divisive vs Mozilla's t-test")
    parser.add_argument("--train", type=int, default=12, help="jobs before the first online window")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    df = filter_protocol(load_runs(args.paths), args.warmup, args.epoch)
    df = df[df["runner"].str.startswith("gha:") & (df["mode"] == "abab")]
    cfg = CpdConfig(window=args.window, permutations=args.permutations)
    metrics = tuple(args.metrics.split(","))

    if args.online:
        rates = evaluate_online(df, metrics, cfg, args.train)
        summary = summarize_online(rates, cfg)
        rates.to_csv(out / "online_rates.csv", index=False)
        summary.to_csv(out / "online_summary.csv", index=False)
        with pd.option_context("display.width", 250, "display.max_rows", 400, "display.precision", 3):
            print(summary.pivot_table(index=["app", "throttling", "metric", "shape"], columns=["detector", "series"],
                                      values=["false_alarm_rate", "mde"]).to_string())
        print(f"\nwrote {out}")
        return

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
