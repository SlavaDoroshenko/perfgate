"""Display all observed TBT values and exploratory per-job decisions; never pool jobs."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('root', type=Path)
p.add_argument('--analysis', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
jobs = pd.read_csv(a.analysis / 'jobs.csv').set_index('experiment')
series = []
for manifest in sorted(a.root.rglob('manifest.json')):
    m = json.loads(manifest.read_text())
    if m.get('protocol') != 'tail-browser-pilot-2026-10-30' or m.get('acquisition_role') != 'pilot': continue
    if m['experiment'] not in jobs.index: raise SystemExit('Analyze every job before plotting')
    series.append((manifest.parent, m))
fig, axes = plt.subplots((len(series) + 1) // 2, 2, figsize=(12, 3 * ((len(series) + 1) // 2)), squeeze=False, sharey=True, constrained_layout=True)
for ax, (directory, m) in zip(axes.flat, series):
    valid = bool(jobs.loc[m['experiment'], 'valid'])
    ax.set_title(f"{m['env']['platform']} / {m['condition']} / seed {m['seed']}" + ('' if valid else ' — INVALID'), fontsize=10)
    if not valid:
        ax.text(.05, .5, 'Invalid series retained in jobs.csv', transform=ax.transAxes)
        continue
    records = [json.loads(line) for line in (directory / 'runs.jsonl').read_text().splitlines()]
    for variant, color, offset in [('base', '#176b91', -.08), ('pr', '#ba531c', .08)]:
        rows = [r for r in records if r['variant'] == variant]
        ax.scatter([r['runIndex'] + 1 + offset for r in rows], [r['metrics']['tbt'] for r in rows], s=20, color=color, label=variant)
    stalled = [r for r in records if r['variant'] == 'pr' and r['runIndex'] in m['selected_indices']]
    if stalled:
        ax.scatter([r['runIndex'] + 1.08 for r in stalled], [r['metrics']['tbt'] for r in stalled], s=70, marker='x', color='#8b1742', label='assigned stall')
    ax.set(xlabel='Alternating pair index', ylabel='TBT (ms)', xticks=[1, 5, 10, 15, 20])
    ax.grid(axis='y', alpha=.2); ax.legend(fontsize=7, loc='center right')
for ax in axes.flat[len(series):]: ax.set_visible(False)
fig.suptitle('Fixed rare-stall browser pilot: all measured observations\n20 loads per variant; rare = 3 assigned 800 ms stalls; jobs are not pooled', fontsize=12)
fig.savefig(a.out / 'observations.png', dpi=160); fig.savefig(a.out / 'observations.svg'); plt.close(fig)
methods = pd.read_csv(a.analysis / 'methods.csv')
if not methods.empty:
    methods['detected'] = methods.detected.map(lambda x: str(x).lower() == 'true')
    matrix = methods.pivot(index='method', columns='experiment', values='detected').astype(float)
    fig, ax = plt.subplots(figsize=(12, 7), constrained_layout=True)
    ax.imshow(matrix.to_numpy(), vmin=0, vmax=1, cmap='Blues', aspect='auto')
    labels = [f"{jobs.loc[e, 'platform']}\n{jobs.loc[e, 'condition']}\n{str(jobs.loc[e, 'seed'])[-2:]}" for e in matrix.columns]
    ax.set_xticks(range(len(labels)), labels=labels)
    ax.set_yticks(range(len(matrix)), labels=matrix.index, fontsize=9)
    for i in range(len(matrix)):
        for j in range(len(matrix.columns)):
            value = matrix.iloc[i, j]
            ax.text(j, i, 'yes' if value else 'no', ha='center', va='center', color='white' if value else '#222', fontsize=8)
    ax.set_title('Exploratory TBT decisions on identical samples\nDifferent endpoints/nulls; unadjusted across methods; not power estimates')
    fig.savefig(a.out / 'methods.png', dpi=160); fig.savefig(a.out / 'methods.svg'); plt.close(fig)
