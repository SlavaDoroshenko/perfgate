"""Refresh the research tables from one validated, fixed data checkout.

python -m perfgate_analysis.refresh ../../perfgate-data/raw --out reports/2026-10-18
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from . import evaluate, history, mde, noise, power, report, report_rq2, rq3
from .load import filter_protocol, load_runs
from .methods import default_methods

EPOCHS = ["fa45447b5c39", "467c2a6f9f6c", "12817a1ef4f9"]


def save(out: Path, name: str, tables: dict) -> Path:
    folder = out / name
    folder.mkdir(parents=True, exist_ok=True)
    for filename, table in tables.items():
        table.to_csv(folder / f"{filename}.csv", index=False)
    print(f"wrote {folder}", flush=True)
    return folder


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sections", default="rq1,rq2,rq3,power,history")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    data_sha = subprocess.check_output(["git", "-C", str(args.data.resolve().parent), "rev-parse", "HEAD"], text=True).strip()
    print(f"validating data snapshot {data_sha}", flush=True)
    df = filter_protocol(load_runs([args.data]), 2, EPOCHS)
    df = df[df["runner"].str.startswith("gha:")]
    metadata = {"data_sha": data_sha, "epochs": EPOCHS, "warmup": 2,
                "from": str(df.timestamp.min()), "through": str(df.timestamp.max()),
                "loads": len(df), "jobs": int(df.experiment.nunique()),
                "invalid_loads": int((~df.ok).sum()), "sections": args.sections.split(",")}
    (args.out / "snapshot.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata), flush=True)
    methods = default_methods()
    for section in args.sections.split(","):
        print(f"computing {section}", flush=True)
        if section == "rq1":
            cfg = mde.PowerConfig()
            rates = mde.power_table(df, cfg=cfg)
            folder = save(args.out, section, {"noise_summary": noise.summarize(df),
                "within_between": noise.within_between(df), "failure_rate": noise.failure_rate(df),
                "power": rates, "mde": mde.mde_table(rates, cfg), "aa_false_alarms": mde.aa_false_alarms(df)})
            report.plot_power(rates, folder)
        elif section == "rq2":
            rates = evaluate.evaluate(df, methods=methods)
            summary = evaluate.summarize(rates)
            folder = save(args.out, section, {"rates": rates, "summary": summary,
                "real_jobs": evaluate.evaluate_real_jobs(df, methods=methods)})
            report_rq2.plot_tradeoff(summary, folder)
        elif section == "rq3":
            for n in (5, 10, 20):
                jobs = rq3.job_stats(df, loads=n)
                stable = jobs[jobs.metric != "tbt"]
                pr = rq3.pr_level(jobs)
                suites = rq3.suite_level(jobs)
                tables = {"jobs": jobs, "pooled_stable": rq3.mode_summary(stable, ["throttling"]),
                    "pooled_tbt": rq3.mode_summary(jobs[jobs.metric == "tbt"], ["throttling"]),
                    "pr_jobs": pr, "pr_level": rq3.pr_summary(pr, ["throttling"])}
                if not suites.empty:
                    tables |= {"suite_jobs": suites, "suite_level": rq3.pr_summary(suites, ["throttling"])}
                save(args.out, f"rq3_n{n}", tables)
        elif section == "power":
            injected = power.injected_jobs(df)
            aa = power.aa_jobs_like(df, injected)
            verdicts = power.job_verdicts(injected, methods, power.TARGET, by=("kind", "pct"))
            aa_verdicts = power.job_verdicts(aa, methods, None)
            rates = power.power_table(verdicts)
            cls = power.cls_absolute(injected[injected.kind == "layout-shift"], by=("kind", "pct"))
            folder = save(args.out, section, {"jobs": verdicts, "power": rates, "fpr": power.fpr_table(aa_verdicts),
                "cls_jobs": cls, "cls_aa": power.cls_absolute(aa[aa.app.isin(cls.app.unique())])})
            for n in power.SIZES:
                power.plot_power(rates, folder, [m.name for m in methods if m.name.startswith(("MWU", "median"))], n)
        elif section == "history":
            for window in (20, 40):
                cfg = history.CpdConfig(window=window)
                rates = history.evaluate_online(df[df["mode"] == "abab"], ("fcp", "lcp", "tbt"), cfg)
                save(args.out, f"history_w{window}", {"online_rates": rates, "online_summary": history.summarize_online(rates, cfg)})
        else:
            raise ValueError(f"unknown section: {section}")


if __name__ == "__main__":
    main()
