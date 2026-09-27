"""Load JSONL run records into a flat DataFrame."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Iterable
from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd
from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO / "schema" / "run.schema.json"

# Package directory whose git tree hash identifies the measured build (see noise.yml, --app-build).
APP_PACKAGES = {
    "demo-spa": "apps/demo-spa",
    "demo-heavy": "apps/demo-spa",
    "demo-static": "apps/demo-static",
    "demo-ssr": "apps/demo-ssr",
}


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


@cache
def tree_hash(sha: str, path: str) -> str | None:
    """12-char tree hash of `path` at commit `sha`, or None when git cannot resolve it."""
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "ls-tree", sha, "--", path],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return None
    return out[2][:12] if len(out) >= 3 else None


def app_epoch(app: str, app_build: str | None, git_sha: str | None) -> str:
    """
    What makes two jobs comparable. Records written before --app-build existed carry only the
    commit; resolving it to the same tree hash keeps commits that did not touch the app together.
    """
    if app_build:
        return app_build
    if git_sha and app in APP_PACKAGES:
        resolved = tree_hash(git_sha, APP_PACKAGES[app])
        if resolved:
            return resolved
    return (git_sha or "unknown")[:7]


def filter_protocol(df: pd.DataFrame, warmup: int | None, epochs: list[str] | None) -> pd.DataFrame:
    """Keep jobs of one measurement protocol: warm-up count and app build (prefix match)."""
    if warmup is not None:
        df = df[df["warmup"].fillna(1).astype(int) == warmup]
    if epochs:
        df = df[df["epoch"].astype(str).str.startswith(tuple(epochs))]
    return df


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
                "warmup": r.get("warmup"),
                "app_build": r.get("appBuild"),
                "label": r.get("label"),
                "run_index": r["runIndex"],
                "order": r["order"],
                "inject": f"{inject['type']}:{inject['size']:g}" if inject else None,
                "error": r["error"],
                "benchmark_index": r["benchmarkIndex"],
                "failed_requests": r.get("failedRequests"),
                "runner": runner_kind(r["env"]),
                "runner_image": r["env"]["runnerImage"],
                "cpu_model": r["env"]["cpuModel"],
                "chrome": r["env"]["chromeVersion"],
                "lighthouse": r["env"]["lighthouseVersion"],
                "git_sha": r["gitSha"],
                # short commit id: the built bundle differs between commits, so metrics
                # from different builds are not comparable across jobs
                "build": (r["gitSha"] or "unknown")[:7],
                "timestamp": r["timestamp"],
                **r["metrics"],
            }
        )
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["ok"] = df["error"].isna()
    # A/A experiment: explicitly labelled, or (for older data) no injected regression anywhere.
    # Comparisons of two library versions or two commits carry no inject either, so the
    # label is what keeps them out of the false alarm statistics.
    by_inject = df.groupby("experiment")["inject"].transform(lambda s: s.isna().all())
    labelled = df.groupby("experiment")["label"].transform(lambda s: s.notna().all() and s.iloc[0] == "aa")
    has_label = df.groupby("experiment")["label"].transform(lambda s: s.notna().all())
    df["is_aa"] = np.where(has_label, labelled, by_inject)
    keys = df[["app", "app_build", "git_sha"]].drop_duplicates()
    epochs = {
        (a, b, g): app_epoch(a, None if pd.isna(b) else b, g)
        for a, b, g in keys.itertuples(index=False)
    }
    df["epoch"] = [epochs[k] for k in zip(df["app"], df["app_build"], df["git_sha"])]
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
