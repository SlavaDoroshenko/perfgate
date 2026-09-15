"""Build RQ1 tables and figures: python -m perfgate_analysis.report <data dirs> --out reports/rq1"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from . import GROUP, METRICS
from .load import load_runs
from .mde import PowerConfig, aa_false_alarms, mde_table, power_table
from .noise import failure_rate, long_metrics, summarize, within_between


def _label(key: tuple) -> str:
    return " / ".join(str(k) for k in key)


def plot_distributions(df: pd.DataFrame, out: Path) -> None:
    data = long_metrics(df)
    for metric in METRICS:
        m = data[data["metric"] == metric]
        if m.empty:
            continue
        groups = list(m.groupby(GROUP))
        fig, ax = plt.subplots(figsize=(8, 0.5 + 0.45 * len(groups)))
        ax.boxplot([g["value"] for _, g in groups], orientation="horizontal", showfliers=True)
        ax.set_yticks(range(1, len(groups) + 1), [_label(k) for k, _ in groups], fontsize=8)
        ax.set_xlabel(f"{metric} ({'score' if metric == 'cls' else 'ms'})")
        ax.set_title(f"{metric}: A/A distribution per configuration")
        fig.tight_layout()
        fig.savefig(out / f"dist_{metric}.png", dpi=150)
        plt.close(fig)


def plot_drift(df: pd.DataFrame, out: Path) -> None:
    data = long_metrics(df)
    for metric in METRICS:
        m = data[data["metric"] == metric]
        if m.empty:
            continue
        fig, ax = plt.subplots(figsize=(9, 4))
        for key, g in m.groupby(GROUP):
            med = g.groupby("experiment").agg(t=("timestamp", "min"), v=("value", "median")).sort_values("t")
            ax.plot(med["t"], med["v"], marker="o", ms=3, label=_label(key))
        ax.set_ylabel(f"median {metric} per job")
        ax.set_title(f"{metric}: job medians over time")
        ax.legend(fontsize=7)
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(out / f"drift_{metric}.png", dpi=150)
        plt.close(fig)


def plot_power(power: pd.DataFrame, out: Path) -> None:
    for (metric, *key), g in power.groupby(["metric", *GROUP]):
        if g["power"].isna().all():
            continue
        fig, ax = plt.subplots(figsize=(6, 4))
        for n, c in g.groupby("n"):
            ax.plot(c["delta"] * 100, c["power"], marker="o", ms=3, label=f"n={n}")
        ax.axhline(0.8, color="grey", ls="--", lw=0.8)
        ax.axhline(0.05, color="grey", ls=":", lw=0.8)
        ax.set_xscale("symlog", linthresh=1)
        ax.set_xlabel("injected slowdown, %")
        ax.set_ylabel("detection rate (Mann-Whitney, α=0.05)")
        ax.set_title(f"{metric}: {_label(tuple(key))}", fontsize=9)
        ax.legend()
        fig.tight_layout()
        name = "_".join([metric, *map(str, key)]).replace(":", "-").replace("/", "-").replace(" ", "")
        fig.savefig(out / f"power_{name}.png", dpi=150)
        plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="JSONL files or directories")
    parser.add_argument("--out", default="reports/rq1")
    parser.add_argument("--reps", type=int, default=1000)
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    df = load_runs(args.paths)
    if df.empty:
        raise SystemExit("no records found")
    print(f"{len(df)} runs, {df['experiment'].nunique()} experiments")

    cfg = PowerConfig(reps=args.reps)
    power = power_table(df, cfg=cfg)
    tables = {
        "noise_summary": summarize(df),
        "within_between": within_between(df),
        "failure_rate": failure_rate(df),
        "power": power,
        "mde": mde_table(power, cfg) if not power.empty else pd.DataFrame(),
        "aa_false_alarms": aa_false_alarms(df),
    }
    for name, table in tables.items():
        table.to_csv(out / f"{name}.csv", index=False)

    plot_distributions(df, out)
    plot_drift(df, out)
    if not power.empty:
        plot_power(power, out)

    with pd.option_context("display.width", 160, "display.max_columns", 20, "display.precision", 3):
        print("\nMDE (relative slowdown detectable with power 0.8):")
        mde = tables["mde"]
        if not mde.empty:
            print(mde.pivot_table(index=[*GROUP, "metric"], columns="n", values="mde").to_string())
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
