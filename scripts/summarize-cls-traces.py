"""Summarize diagnostic CLS traces without altering gate outcomes or excluding modes."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median


def summarize(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    events, runs = [], []
    for entry in manifest["runs"]:
        path = directory / entry["file"]
        run = json.loads(path.read_text())
        selectors = {node["nodeId"]: node["node"]["selector"] for node in run["traceElements"]}
        first_ts = min((event["ts"] for event in run["shifts"]), default=0)
        valid_shifts = [e for e in run["shifts"] if not e["args"]["data"].get("had_recent_input")]
        runs.append({"file": entry["file"], "index": run["index"], "variant": run["variant"],
                     "warmup": run["index"] < 0, "cls": run["cls"], "events": len(valid_shifts),
                     "event_score_sum": sum(e["args"]["data"]["weighted_score_delta"] for e in valid_shifts)})
        for i, event in enumerate(run["shifts"]):
            data = event["args"]["data"]
            movements = [{"selector": selectors.get(node["node_id"], f"node:{node['node_id']}"),
                          "dy": node["new_rect"][1] - node["old_rect"][1],
                          "dx": node["new_rect"][0] - node["old_rect"][0]}
                         for node in data.get("impacted_nodes", [])]
            events.append({"file": entry["file"], "index": run["index"], "variant": run["variant"],
                           "ordinal": i, "since_first_shift_ms": (event["ts"] - first_ts) / 1000,
                           "score": data["weighted_score_delta"], "recent_input": data["had_recent_input"],
                           "max_distance": data.get("frame_max_distance"), "movements": json.dumps(movements)})
    summary = {"purpose": manifest["purpose"], "source": manifest["source"], "chrome": manifest["chrome"],
               "complete": "finished" in manifest, "pairs_planned": manifest["pairs"], "variants": {}}
    for variant in ["base", "pr"]:
        observations = [r["cls"] for r in runs if r["variant"] == variant and not r["warmup"]]
        if not observations:
            continue
        summary["variants"][variant] = {"n": len(observations), "median": median(observations),
                                        "mean": mean(observations), "min": min(observations),
                                        "max": max(observations),
                                        "values_rounded_9dp": dict(Counter(round(v, 9) for v in observations))}
    if all(v in summary["variants"] for v in ["base", "pr"]):
        base = summary["variants"]["base"]["median"]
        treatment = summary["variants"]["pr"]["median"]
        summary["observed_median_absolute_difference"] = treatment - base
        summary["observed_median_relative_difference"] = treatment / base - 1 if base else None
    summary["input_sha256"] = {entry["file"]: hashlib.sha256((directory / entry["file"]).read_bytes()).hexdigest()
                               for entry in manifest["runs"]}
    return summary, runs, events


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    summary, runs, events = summarize(args.directory)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    for name, rows in [("runs", runs), ("events", events)]:
        if rows:
            with (args.out / f"{name}.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
    print(json.dumps({k: v for k, v in summary.items() if k != "input_sha256"}, indent=2))
