"""A local A/A pilot beside CI, with the same page, browser major and sample size."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .load import filter_protocol, load_runs
from .mde import PowerConfig, mde_table, power_table
from .noise import summarize, within_between
from .rq3 import job_stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    df = filter_protocol(load_runs(args.paths), 2, ["fa45447b5c39"])
    df = df[(df.app == "demo-heavy") & (df["mode"] == "abab") & (df.throttling == "devtools") & df.is_aa]
    local = df[df.runner.str.startswith("local:")]
    if local.empty:
        raise SystemExit("no comparable local A/A jobs")
    df = df[df.chrome.isin(local.chrome.unique())].sort_values(["experiment", "order"])
    df = df[df.groupby(["experiment", "variant"]).cumcount() < 10]
    # Compare only complete jobs, including the count before filtering out bad loads.
    counts = df.groupby(["experiment", "variant"]).size().unstack(fill_value=0)
    complete = counts[(counts.get("base", 0) == 10) & (counts.get("pr", 0) == 10)].index
    invalid = df.loc[~df.ok, "experiment"].unique()
    df = df[df.experiment.isin(complete) & ~df.experiment.isin(invalid)]
    args.out.mkdir(parents=True, exist_ok=True)
    tables = {"noise": summarize(df), "within_between": within_between(df),
              "jobs": job_stats(df, metrics=("fcp", "lcp", "tbt"), loads=10)}
    rates = power_table(df, sample_sizes=(10,), metrics=["fcp", "lcp", "tbt"], cfg=PowerConfig())
    tables |= {"power": rates, "mde": mde_table(rates)}
    for name, table in tables.items():
        table.to_csv(args.out / f"{name}.csv", index=False)
    print(df.groupby("runner").agg(jobs=("experiment", "nunique"), loads=("experiment", "size"),
                                    first=("timestamp", "min"), last=("timestamp", "max")).to_string())
    with pd.option_context("display.max_columns", 30):
        print(tables["within_between"].to_string(index=False))
        print(tables["mde"].to_string(index=False))


if __name__ == "__main__":
    main()
