"""RQ2 report: python -m perfgate_analysis.report_rq2 <data dirs> --out reports/rq2"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from . import GROUP
from .evaluate import EvalConfig, evaluate, evaluate_real_jobs, summarize
from .load import load_runs
from .methods import default_methods


def filter_protocol(df: pd.DataFrame, warmup: int | None, epochs: list[str] | None) -> pd.DataFrame:
    if warmup is not None:
        df = df[df["warmup"].fillna(1).astype(int) == warmup]
    if epochs:
        df = df[df["epoch"].astype(str).str.startswith(tuple(epochs))]
    return df


def plot_tradeoff(summary: pd.DataFrame, out: Path) -> None:
    """False alarms against MDE: the trade-off every method makes."""
    for (metric, n), g in summary.groupby(["metric", "n"]):
        agg = g.groupby("method").agg(fpr=("false_alarm_rate", "median"), mde=("mde", "median")).dropna()
        if agg.empty:
            continue
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.scatter(agg["fpr"] * 100, agg["mde"] * 100, s=40)
        for name, row in agg.iterrows():
            ax.annotate(name, (row["fpr"] * 100, row["mde"] * 100), fontsize=7,
                        xytext=(4, 4), textcoords="offset points")
        ax.axvline(5, color="grey", ls="--", lw=0.8)
        ax.set_xlabel("false alarms on A/A, %")
        ax.set_ylabel("smallest detected regression (power 0.8), %")
        ax.set_title(f"{metric}, {n} loads per variant")
        fig.tight_layout()
        fig.savefig(out / f"tradeoff_{metric}_n{n}.png", dpi=150)
        plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--out", default="reports/rq2")
    parser.add_argument("--reps", type=int, default=1000)
    parser.add_argument("--warmup", type=int, default=None, help="keep only jobs with this warm-up count")
    parser.add_argument("--epoch", action="append", help="keep only these app fingerprints (prefix match)")
    parser.add_argument("--metrics", default="fcp,lcp,tbt")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    df = filter_protocol(load_runs(args.paths), args.warmup, args.epoch)
    if df.empty:
        raise SystemExit("no records after filtering")
    metrics = tuple(args.metrics.split(","))
    print(f"{len(df)} loads, {df['experiment'].nunique()} jobs, {df['app'].nunique()} apps")

    methods = default_methods()
    rates = evaluate(df, methods=methods, metrics=metrics, cfg=EvalConfig(reps=args.reps))
    summary = summarize(rates)
    real = evaluate_real_jobs(df, methods=methods, metrics=metrics)

    rates.to_csv(out / "rates.csv", index=False)
    summary.to_csv(out / "summary.csv", index=False)
    real.to_csv(out / "real_jobs.csv", index=False)
    plot_tradeoff(summary, out)

    with pd.option_context("display.width", 200, "display.max_rows", 200, "display.precision", 3):
        print("\nПо методам (медиана по конфигурациям и метрикам):")
        print(summary.groupby(["method", "n"]).agg(
            fpr=("false_alarm_rate", "median"), mde=("mde", "median"), loads=("loads", "max")
        ).to_string())
        if not real.empty:
            print("\nНа реальных джобах:")
            print(real.pivot_table(index="method", columns="kind", values="flagged", aggfunc="mean").to_string())
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
