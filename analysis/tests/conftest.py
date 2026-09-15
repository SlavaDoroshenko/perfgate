from __future__ import annotations

import numpy as np
import pytest


def make_record(**over) -> dict:
    rec = {
        "schemaVersion": 1,
        "experimentId": "exp-1",
        "app": "demo-spa",
        "variant": "base",
        "url": "http://127.0.0.1:4173/",
        "inject": None,
        "mode": "abab",
        "throttling": "simulate",
        "runIndex": 0,
        "order": 0,
        "metrics": {"lcp": 1000.0, "fcp": 800.0, "tbt": 0.0, "cls": 0.0, "si": 900.0, "ttfb": 2.0},
        "benchmarkIndex": 2000.0,
        "error": None,
        "env": {
            "chromeVersion": "153.0.8010.47",
            "lighthouseVersion": "13.4.1",
            "nodeVersion": "v22.0.0",
            "platform": "linux",
            "osRelease": "6.8.0",
            "arch": "x64",
            "cpuModel": "AMD EPYC 7763",
            "cpuCount": 4,
            "totalMemMb": 16000,
            "ci": True,
            "runnerImage": "ubuntu24-20260901.1",
            "runnerName": "GitHub Actions 1",
        },
        "gitSha": "abc",
        "timestamp": "2026-09-16T10:00:00.000Z",
    }
    rec.update(over)
    return rec


def synthetic_records(experiments: int, runs: int, sigma: float, seed: int = 1, mean: float = 1000.0) -> list[dict]:
    """A/A experiments with normally distributed metrics (relative sd = sigma)."""
    rng = np.random.default_rng(seed)
    records = []
    for e in range(experiments):
        order = 0
        for i in range(runs):
            for variant in ("base", "pr"):
                v = float(rng.normal(mean, sigma * mean))
                records.append(
                    make_record(
                        experimentId=f"exp-{e}",
                        variant=variant,
                        runIndex=i,
                        order=order,
                        metrics={"lcp": v, "fcp": v, "tbt": 0.0, "cls": 0.0, "si": v, "ttfb": 2.0},
                    )
                )
                order += 1
    return records


@pytest.fixture
def record_factory():
    return make_record
