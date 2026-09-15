"""Load JSONL run records into a flat DataFrame."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path

import pandas as pd
from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema" / "run.schema.json"


def _validator() -> Draft202012Validator:
    return Draft202012Validator(json.loads(SCHEMA_PATH.read_text()))


def iter_files(paths: Iterable[str | Path]) -> list[Path]:
    files: list[Path] = []
    for p in map(Path, paths):
        files.extend(sorted(p.rglob("*.jsonl")) if p.is_dir() else [p])
    return files


def read_records(paths: Iterable[str | Path], validate: bool = True) -> list[dict]:
    validator = _validator() if validate else None
    records = []
    for file in iter_files(paths):
        for lineno, line in enumerate(file.read_text().splitlines(), 1):
            if not line.strip():
                continue
            rec = json.loads(line)
            if validator is not None:
                errors = sorted(validator.iter_errors(rec), key=lambda e: list(e.path))
                if errors:
                    raise ValueError(f"{file}:{lineno}: {errors[0].message}")
            records.append(rec)
    return records


def runner_kind(env: dict) -> str:
    """GitHub-hosted runners are identified by image, local machines by CPU."""
    if env.get("ci") and env.get("runnerImage"):
        return f"gha:{env['runnerImage'].split('-')[0]}"
    return f"local:{env['platform']}:{env['cpuModel']}"


def to_frame(records: list[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    rows = []
    for r in records:
        inject = r["inject"]
        rows.append(
            {
                "experiment": r["experimentId"],
                "app": r["app"],
                "variant": r["variant"],
                "mode": r["mode"],
                "throttling": r["throttling"],
                "run_index": r["runIndex"],
                "order": r["order"],
                "inject": f"{inject['type']}:{inject['size']:g}" if inject else None,
                "error": r["error"],
                "benchmark_index": r["benchmarkIndex"],
                "runner": runner_kind(r["env"]),
                "runner_image": r["env"]["runnerImage"],
                "cpu_model": r["env"]["cpuModel"],
                "chrome": r["env"]["chromeVersion"],
                "lighthouse": r["env"]["lighthouseVersion"],
                "timestamp": r["timestamp"],
                **r["metrics"],
            }
        )
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["ok"] = df["error"].isna()
    # A/A experiment: no load in the whole series carries an injected regression
    df["is_aa"] = df.groupby("experiment")["inject"].transform(lambda s: s.isna().all())
    return df


def load_runs(paths: Iterable[str | Path], validate: bool = True) -> pd.DataFrame:
    return to_frame(read_records(paths, validate=validate))


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and summarize perfgate JSONL files")
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--no-validate", action="store_true")
    args = parser.parse_args()

    df = load_runs(args.paths, validate=not args.no_validate)
    if df.empty:
        print("no records")
        return
    print(f"{len(df)} runs, {df['experiment'].nunique()} experiments, {(~df['ok']).sum()} failed")
    print(df.groupby(["runner", "throttling", "mode", "is_aa"]).size().to_string())


if __name__ == "__main__":
    main()
