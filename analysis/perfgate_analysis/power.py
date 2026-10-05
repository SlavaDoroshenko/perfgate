"""
Power on real CI noise: how often every rule catches a regression of known kind and size.

The regression bench (regressions.yml) measures base and PR builds on the runners like any other
job, with a synthetic regression of 2/5/10/25% injected into the PR. Unlike RQ2, nothing is
resampled or shifted: the miss rate comes from real jobs with their real run order, so it
includes everything resampling cannot model - drift during the job, a different machine per job,
and the way the injected work interacts with the page.

Each kind of regression is aimed at one metric (script-delay → FCP, long-task → TBT,
lcp-delay → LCP, layout-shift → CLS); that metric is where detection is counted. The effect
actually reached is taken from the data, since TBT and CLS are not additive in the injected size.
False alarms of the same rules come from the A/A jobs of the same page, mode and throttling.

Fewer loads per variant are taken as the first k pairs of the series - what a shorter job
would have measured - not as a random subsample.

python -m perfgate_analysis.power <data dirs> --out reports/power --warmup 2 --epoch ...
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .load import filter_protocol, load_runs
from .methods import Method, cliffs_delta, default_methods, hodges_lehmann, mann_whitney
from .rq3 import wilson

# kind of regression → the metric it is aimed at
TARGET = {"script-delay": "fcp", "long-task": "tbt", "lcp-delay": "lcp", "layout-shift": "cls"}

# Injector sizes of the current bench (regressions.yml) → nominal percent. The first run on
# 28.09 used other CLS sizes and lcp-delay on the heavy page; keeping only these drops it.
NOMINAL = {
    ("demo-heavy", "script-delay"): {36: 2, 90: 5, 179: 10, 448: 25},
    ("demo-heavy", "long-task"): {60: 2, 74: 5, 99: 10, 171: 25},
    ("demo-spa", "lcp-delay"): {45: 2, 112: 5, 224: 10, 561: 25},
    ("demo-heavy", "layout-shift"): {66.56: 2, 70.4: 5, 76.8: 10, 96: 25},
}

SIZES = (5, 10, 20)


def injected_jobs(df: pd.DataFrame) -> pd.DataFrame:
    """Loads of the regression bench at its current calibration, with kind and nominal size."""
    ok = df[df["ok"] & (df["label"] == "injected")].copy()
    inj = ok.groupby("experiment")["inject"].transform(lambda s: s.dropna().iloc[0] if s.notna().any() else None)
    ok["kind"] = inj.str.split(":").str[0]
    ok["size"] = inj.str.split(":").str[1].astype(float)

    def nominal(row) -> float:
        table = NOMINAL.get((row.app, row.kind), {})
        return next((pct for size, pct in table.items() if np.isclose(size, row.size)), np.nan)

    keys = ok[["app", "kind", "size"]].drop_duplicates()
    pct = {(r.app, r.kind, r.size): nominal(r) for r in keys.itertuples(index=False)}
    ok["pct"] = [pct[k] for k in zip(ok["app"], ok["kind"], ok["size"])]
    return ok.dropna(subset=["pct"])


def aa_jobs_like(df: pd.DataFrame, injected: pd.DataFrame) -> pd.DataFrame:
    """A/A loads of the pages, runner, mode and throttling the bench uses."""
    cfg = injected[["app", "runner", "throttling", "mode"]].drop_duplicates()
    aa = df[df["ok"] & df["is_aa"]]
    return aa.merge(cfg, on=["app", "runner", "throttling", "mode"])


def _series(g: pd.DataFrame, metric: str, k: int | None) -> tuple[np.ndarray, np.ndarray] | None:
    """First k base and PR loads of one job, in run order."""
    g = g.sort_values("order").dropna(subset=[metric])
    b = g.loc[g["variant"] == "base", metric].to_numpy(float)
    p = g.loc[g["variant"] == "pr", metric].to_numpy(float)
    k = min(len(b), len(p)) if k is None else k
    if len(b) < k or len(p) < k or k < 2:
        return None
    return b[:k], p[:k]


def job_verdicts(
    jobs: pd.DataFrame,
    methods: list[Method],
    metric_of: dict[str, str] | None,
    sizes: tuple[int, ...] = SIZES,
    by: tuple[str, ...] = (),
) -> pd.DataFrame:
    """
    One row per (job, metric, loads, method). With `metric_of`, each job is judged on the metric
    its regression is aimed at; without it (A/A), on every metric of TARGET.
    """
    rows = []
    for exp, g in jobs.groupby("experiment"):
        first = g.iloc[0]
        metrics = [metric_of[first["kind"]]] if metric_of else sorted(set(TARGET.values()))
        for metric in metrics:
            for k in sizes:
                s = _series(g, metric, k)
                if s is None:
                    continue
                b, p = s
                if np.median(b) == 0:
                    continue
                base, pr = b.reshape(1, -1), p.reshape(1, -1)
                common = {
                    "experiment": exp,
                    "app": first["app"],
                    "timestamp": g["timestamp"].min(),
                    **{c: first[c] for c in by},
                    "metric": metric,
                    "n": k,
                    "effect": float(np.median(p) / np.median(b) - 1),
                    "hl": float(hodges_lehmann(base, pr)[0]),
                    "cliffs_delta": float(cliffs_delta(base, pr)[0]),
                }
                for m in methods:
                    rows.append({**common, "method": m.name, "flagged": bool(m(base, pr)[0])})
    return pd.DataFrame(rows)


def power_table(verdicts: pd.DataFrame) -> pd.DataFrame:
    """Detection rate with a Wilson interval per kind × size × loads × method."""
    rows = []
    for (kind, pct, metric, n, method), g in verdicts.groupby(["kind", "pct", "metric", "n", "method"]):
        k, total = int(g["flagged"].sum()), len(g)
        lo, hi = wilson(k, total)
        rows.append(
            {
                "kind": kind,
                "pct": pct,
                "metric": metric,
                "n": n,
                "method": method,
                "jobs": total,
                "power": k / total,
                "lo": lo,
                "hi": hi,
                "effect_median": float(g["effect"].median()),
                "effect_iqr": float(g["effect"].quantile(0.75) - g["effect"].quantile(0.25)),
            }
        )
    return pd.DataFrame(rows)


def fpr_table(aa: pd.DataFrame) -> pd.DataFrame:
    """False alarm rate of every rule on A/A jobs of the same configuration."""
    rows = []
    for (app, metric, n, method), g in aa.groupby(["app", "metric", "n", "method"]):
        k, total = int(g["flagged"].sum()), len(g)
        lo, hi = wilson(k, total)
        rows.append({"app": app, "metric": metric, "n": n, "method": method, "jobs": total,
                     "fpr": k / total, "lo": lo, "hi": hi})
    return pd.DataFrame(rows)


# CLS in absolute units: "good" CLS ends at 0.1, so 0.005-0.025 is 5-25% of that budget
CLS_MARGINS = (0.005, 0.01, 0.025)


def cls_absolute(jobs: pd.DataFrame, sizes: tuple[int, ...] = SIZES, by: tuple[str, ...] = ()) -> pd.DataFrame:
    """
    CLS is not a timing: in the lab a page shifts by one of a few fixed amounts, and which one
    is a race between the late content and the first paint. A relative effect on such a metric
    is mostly the share of loads that lost the race, so CLS is judged here by the absolute
    difference of medians and by how often the larger shift happens.
    """
    rows = []
    for exp, g in jobs.groupby("experiment"):
        first = g.iloc[0]
        for k in sizes:
            s = _series(g, "cls", k)
            if s is None:
                continue
            b, p = s
            # the larger of the shifts that occur on base: loads at or above it lost the race
            high = np.max(b) if np.ptp(b) > 0 else np.inf
            base, pr = b.reshape(1, -1), p.reshape(1, -1)
            mwu = mann_whitney()
            row = {
                "experiment": exp,
                "app": first["app"],
                **{c: first[c] for c in by},
                "n": k,
                "abs_effect": float(np.median(p) - np.median(b)),
                "base_high_share": float(np.mean(b >= high)),
                "distinct_base": int(len(np.unique(b))),
            }
            for c in CLS_MARGINS:
                row[f"median >+{c}"] = bool(np.median(p) - np.median(b) > c)
                row[f"MWU & >+{c}"] = bool(mwu(base, pr)[0] and np.median(p) - np.median(b) > c)
            rows.append(row)
    return pd.DataFrame(rows)


def plot_power(power: pd.DataFrame, out: Path, methods: list[str], n: int) -> None:
    """Power curves per kind of regression: share of jobs flagged against the nominal size."""
    kinds = [k for k in TARGET if k in set(power["kind"])]
    fig, axes = plt.subplots(1, len(kinds), figsize=(4 * len(kinds), 4), sharey=True, squeeze=False)
    for ax, kind in zip(axes[0], kinds):
        g = power[(power["kind"] == kind) & (power["n"] == n)]
        for method in methods:
            m = g[g["method"] == method].sort_values("pct")
            if m.empty:
                continue
            ax.errorbar(m["pct"], m["power"] * 100, yerr=[(m["power"] - m["lo"]).clip(0) * 100, (m["hi"] - m["power"]).clip(0) * 100],
                        marker="o", ms=4, capsize=2, lw=1, label=method)
        ax.axhline(80, color="grey", ls="--", lw=0.8)
        ax.set_xscale("log")
        ax.set_xticks([2, 5, 10, 25], labels=["2", "5", "10", "25"])
        ax.set_xticks([], minor=True)
        ax.set_xlabel("injected regression, % (nominal)")
        ax.set_title(f"{kind} → {TARGET[kind].upper()}")
    axes[0][0].set_ylabel(f"jobs flagged, % ({n} loads per variant)")
    axes[0][-1].legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    fig.savefig(out / f"power_n{n}.png", dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--out", default="reports/power")
    parser.add_argument("--warmup", type=int, default=None)
    parser.add_argument("--epoch", action="append")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    df = filter_protocol(load_runs(args.paths), args.warmup, args.epoch)
    injected = injected_jobs(df)
    if injected.empty:
        raise SystemExit("no regression bench jobs after filtering")
    aa = aa_jobs_like(df, injected)
    print(f"{injected['experiment'].nunique()} regression jobs, {aa['experiment'].nunique()} A/A jobs")

    methods = default_methods()
    verdicts = job_verdicts(injected, methods, TARGET, by=("kind", "pct"))
    aa_verdicts = job_verdicts(aa, methods, None)
    power = power_table(verdicts)
    fpr = fpr_table(aa_verdicts)

    verdicts.to_csv(out / "jobs.csv", index=False)
    power.to_csv(out / "power.csv", index=False)
    fpr.to_csv(out / "fpr.csv", index=False)
    cls_jobs = cls_absolute(injected[injected["kind"] == "layout-shift"], by=("kind", "pct"))
    cls_aa = cls_absolute(aa[aa["app"].isin(cls_jobs["app"].unique())]) if not cls_jobs.empty else pd.DataFrame()
    cls_jobs.to_csv(out / "cls_jobs.csv", index=False)
    cls_aa.to_csv(out / "cls_aa.csv", index=False)
    shown = ["Mann-Whitney α=0.05", "MWU α=0.05 & >1%", "Brunner-Munzel α=0.05", "median >2%", "median >5%", "single-run >2%"]
    for n in SIZES:
        plot_power(power, out, shown, n)

    with pd.option_context("display.width", 220, "display.max_rows", 400, "display.precision", 3):
        for n in SIZES:
            print(f"\nДоля обнаруженных регрессий, {n} загрузок на вариант:")
            print(power[power["n"] == n].pivot_table(index="method", columns=["kind", "pct"], values="power").to_string())
        print("\nФактический эффект (медиана по джобам, n=20):")
        print(power[(power["n"] == 20)].groupby(["kind", "pct"])[["effect_median", "effect_iqr", "jobs"]].first().to_string())
        print("\nЛожные тревоги на A/A той же конфигурации:")
        print(fpr.pivot_table(index="method", columns=["app", "metric", "n"], values="fpr").to_string())
        if not cls_jobs.empty:
            rules = [c for c in cls_jobs.columns if c.startswith(("median >+", "MWU & >+"))]
            print("\nCLS в абсолютных величинах: доля обнаружений (регрессии) и ложных тревог (A/A):")
            print(cls_jobs.groupby(["n", "pct"])[[*rules, "abs_effect"]].mean().to_string())
            print(cls_aa.groupby("n")[[*rules, "abs_effect"]].mean().to_string())
            print("\nДоля загрузок с большим сдвигом на base (гонка):", round(cls_aa["base_high_share"].mean(), 3),
                  "; различных значений CLS на base в джобе (медиана):", cls_aa["distinct_base"].median())
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
