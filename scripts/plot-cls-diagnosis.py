"""Plot all measured CLS observations from the four fixed diagnostic series."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--local-original", type=Path, required=True)
p.add_argument("--local-control", type=Path, required=True)
p.add_argument("--ci-original", type=Path, required=True)
p.add_argument("--ci-control", type=Path, required=True)
p.add_argument("--out", type=Path, required=True)
a = p.parse_args()
fig, axes = plt.subplots(2, 2, figsize=(9, 6), sharey=True, constrained_layout=True)
for ax, directory, title in zip(axes.flat,
    [a.local_original, a.local_control, a.ci_original, a.ci_control],
    ["macOS: original", "macOS: reserved stats", "Linux CI: original", "Linux CI: reserved stats"]):
    manifest = json.loads((directory / "manifest.json").read_text())
    if "finished" not in manifest:
        raise SystemExit(f"Incomplete series: {directory}")
    for variant, offset, color in [("base", -0.08, "#176b91"), ("pr", 0.08, "#ba531c")]:
        rows = [r for r in manifest["runs"] if r["index"] >= 0 and r["variant"] == variant]
        ax.scatter([r["index"] + 1 + offset for r in rows], [r["cls"] for r in rows],
                   color=color, s=45, label=f"{variant}, n={len(rows)}")
    ax.set(title=title, xlabel="Alternating pair index", ylabel="Lighthouse CLS",
           xticks=range(1, manifest["pairs"] + 1), ylim=(0, 0.31))
    ax.grid(axis="y", alpha=0.2)
    ax.legend(fontsize=8, loc="upper right")
fig.suptitle("Exploratory CLS diagnosis: 64 px vs 96 px banner\nWarmups excluded; original and control have different baselines", fontsize=12)
a.out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(a.out, dpi=180)
fig.savefig(a.out.with_suffix(".svg"))
