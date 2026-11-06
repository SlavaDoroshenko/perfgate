"""Evaluate the complete candidate policy retrospectively, including invalid-job accounting."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import pandas as pd

from .compare import compare_frame, POLICY
from .load import filter_protocol, load_runs
from .power import injected_jobs
from .refresh import EPOCHS
from .rq3 import wilson


def evaluate(df: pd.DataFrame, runs: int):
    data = df[(df["mode"] == "abab") & (df.throttling == "devtools")].copy()
    rows = []
    for exp, g in data.groupby("experiment", sort=True):
        result = compare_frame(g, runs, strict=False, boots=99)
        rows.append({"experiment": exp, "app": g.app.iloc[0], "timestamp": g.timestamp.min(),
                     "is_aa": bool(g.is_aa.iloc[0]), "label": g.label.iloc[0], "n": runs,
                     "status": result["status"], "issues": "; ".join(result["issues"]),
                     "flagged_metrics": ";".join(m["name"].split("/")[-1] for m in result["metrics"] if m["regression"])})
    jobs = pd.DataFrame(rows)
    calibration = injected_jobs(data, include_invalid=True).groupby("experiment")[["kind", "pct"]].first().reset_index()
    jobs = jobs.merge(calibration, on="experiment", how="left")
    suite_rows = []
    aa = data[data.is_aa].copy()
    aa["suite"] = aa.experiment.str.extract(r"^(\d+-\d+)-", expand=False)
    pages = {"demo-spa", "demo-heavy", "demo-static", "demo-ssr"}
    for suite, g in aa.groupby("suite", sort=True):
        if set(g.app) != pages:
            suite_rows.append({"suite": suite, "n": runs, "status": "invalid", "issues": "missing page"})
            continue
        result = compare_frame(g, runs, strict=False, boots=99)
        suite_rows.append({"suite": suite, "n": runs, "status": result["status"], "issues": "; ".join(result["issues"])})
    return jobs, pd.DataFrame(suite_rows)


def summarize(jobs, suites):
    rows = []
    for n, g in suites.groupby("n"):
        valid = g[g.status != "invalid"]; k = int(valid.status.eq("regression").sum())
        lo, hi = wilson(k, len(valid))
        rows.append({"scope": "four_page_aa", "n": n, "kind": "aa", "pct": 0, "valid": len(valid),
                     "invalid": int(g.status.eq("invalid").sum()), "flagged": k, "rate": k/len(valid) if len(valid) else None, "lo": lo, "hi": hi})
    for (n, kind, pct), g in jobs[jobs.kind.notna()].groupby(["n", "kind", "pct"]):
        valid = g[g.status != "invalid"]; k = int(valid.status.eq("regression").sum())
        lo, hi = wilson(k, len(valid))
        rows.append({"scope": "injected_page_any_metric", "n": n, "kind": kind, "pct": pct,
                     "valid": len(valid), "invalid": int(g.status.eq("invalid").sum()), "flagged": k,
                     "rate": k/len(valid) if len(valid) else None, "lo": lo, "hi": hi})
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--after", help="UTC cutoff; only complete jobs beginning at/after this time")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    df = filter_protocol(load_runs([args.data]), 2, EPOCHS)
    df = df[df.runner.str.startswith("gha:")]
    if args.after:
        starts = df.groupby("experiment").timestamp.transform("min")
        df = df[starts >= pd.Timestamp(args.after)]
    if df.empty: raise SystemExit("no data in requested period")
    outputs = [evaluate(df, n) for n in (10, 20)]
    jobs = pd.concat([x[0] for x in outputs]); suites = pd.concat([x[1] for x in outputs])
    jobs.to_csv(args.out / "jobs.csv", index=False); suites.to_csv(args.out / "suites.csv", index=False)
    summary = summarize(jobs, suites); summary.to_csv(args.out / "summary.csv", index=False)
    sources = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
               (Path(__file__), Path(__file__).with_name("compare.py"), Path(__file__).with_name("quality.py"))}
    sha = subprocess.check_output(["git", "-C", str(args.data.resolve().parent), "rev-parse", "HEAD"], text=True).strip()
    (args.out / "manifest.json").write_text(json.dumps({"policy": POLICY, "data_sha": sha,
        "through": str(df.timestamp.max()), "after": args.after, "analysis": "retrospective unless independently frozen before data collection",
        "source_sha256": sources, "bootstrap_reps_for_unused_intervals": 99,
        "network_unknown_legacy_allowed": True}, indent=2)+"\n")
    print(summary.to_string(index=False))


if __name__ == "__main__": main()
