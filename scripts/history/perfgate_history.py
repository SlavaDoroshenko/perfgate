"""History of perfgate comparisons on the main branch and a static dashboard.

`record` turns perfgate report directories (comparison.json, runs.jsonl) into compact
history records, one JSON line per measured page. `dashboard` renders a history file
into one self-contained HTML page: per page and metric the median of the measured
commit over time, the per-push verdict, the runner CPU model and Chrome version, and
an advisory change-point check on the latest window.

The history value of a record is the median of the measured (new) commit's loads, the
series examined in docs/history-cpd.md. The change-point check is that document's
online setup: E-Divisive with one change point (perfgate_analysis.history.e_divisive)
on the last 20 points, adjusted with Lighthouse's benchmarkIndex learned from earlier
points only and only when that slope is significant ("bench-guarded"). Its warnings
are advisory: the false-alarm rates measured so far do not justify failing a job.

uv run --project analysis python scripts/history/perfgate_history.py record --reports DIR --out history.jsonl
uv run --project analysis python scripts/history/perfgate_history.py dashboard --history history.jsonl --out index.html
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import statistics
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from perfgate_analysis.history import CpdConfig, e_divisive, past_adjusted

SCHEMA_VERSION = 1
METRICS = ("fcp", "lcp", "tbt", "cls")
VALID = ("regression", "no_regression_detected")
# Window, permutations and alpha of the evaluated online setup; fewer points are not checked.
CPD = CpdConfig(window=20)
MIN_POINTS = 12
MAX_TEXT = 200


def _text(value, limit: int = MAX_TEXT) -> str | None:
    return None if value is None else str(value)[:limit]


def _number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def _url(value) -> str | None:
    value = _text(value, 500)
    return value if value and value.startswith("https://") else None


def find_reports(root: Path) -> list[Path]:
    """Directories below root with comparison.json or execution.json; links are not followed."""
    found = []

    def walk(d: Path) -> None:
        names = {p.name for p in d.iterdir()}
        if "comparison.json" in names or "execution.json" in names:
            found.append(d)
        for p in sorted(d.iterdir()):
            if p.is_dir() and not p.is_symlink():
                walk(p)

    if root.is_dir():
        walk(root)
    return found


def read_runs(report: Path) -> list[dict]:
    path = report / "runs.jsonl"
    if not path.is_file():
        return []
    runs = []
    for line in path.read_text().splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            runs.append(row)
    return runs


def environment(runs: list[dict], page: str) -> dict:
    """Machine and browser of the measured commit's loads of one page."""
    own = [r for r in runs if r.get("app") == page] or runs
    env = next((r.get("env") for r in own if isinstance(r.get("env"), dict)), {})
    pr = [r for r in own if r.get("variant") == "pr" and not r.get("error")]
    bench = [b for b in (_number(r.get("benchmarkIndex")) for r in pr) if b is not None]
    first = own[0] if own else {}
    return {
        "cpu_model": _text(env.get("cpuModel")),
        # the version Chrome reports is always recorded; the binary version only with CHROME_PATH
        "chrome_version": _text(env.get("chromeVersion")),
        "chrome_binary_version": _text(env.get("chromeBinaryVersion")),
        "lighthouse_version": _text(env.get("lighthouseVersion")),
        "runner_image": _text(env.get("runnerImage")),
        "benchmark_index": statistics.median(bench) if bench else None,
        "throttling": _text(first.get("throttling")),
        "mode": _text(first.get("mode")),
    }


def build_records(report: Path, commit: str | None = None, base_commit: str | None = None, ref: str | None = None,
                  run_url: str | None = None, commit_url: str | None = None, page: str = "web") -> list[dict]:
    """History records of one report directory, one per page. Failed reports still give a record."""
    runs = read_runs(report)
    try:
        comparison = json.loads((report / "comparison.json").read_text())
        if not isinstance(comparison, dict):
            raise ValueError("not an object")
    except (OSError, ValueError):
        comparison = {"status": "error", "metrics": [], "issues": ["comparison.json missing or unreadable"]}
    sha = commit or next((r["gitSha"] for r in runs if isinstance(r.get("gitSha"), str)), None)
    stamps = sorted(r["timestamp"] for r in runs if isinstance(r.get("timestamp"), str))
    status = comparison.get("status") if comparison.get("status") in (*VALID, "invalid") else "error"

    pages: dict[str, dict] = {}
    for m in comparison.get("metrics") or []:
        name, _, metric = str(m.get("name", "")).rpartition("/")
        if metric not in METRICS:
            continue
        pages.setdefault(name or page, {})[metric] = {
            "unit": "unitless" if metric == "cls" else "ms",
            "base_median": _number(m.get("base_median")),
            "pr_median": _number(m.get("pr_median")),
            "absolute_effect": _number(m.get("absolute_effect")),
            "relative_effect": _number(m.get("relative_effect")),
            "p": _number(m.get("p")),
            "regression": m.get("regression") is True,
        }
    if not pages:
        names = sorted({r["app"] for r in runs if isinstance(r.get("app"), str)})
        pages = {name: {} for name in names or [page]}

    records = []
    for name, metrics in sorted(pages.items()):
        verdict = status
        if status in VALID:
            verdict = "regression" if any(m["regression"] for m in metrics.values()) else "no_regression_detected"
        records.append({
            "schema_version": SCHEMA_VERSION,
            "commit": _text(sha),
            "base_commit": _text(base_commit),
            "ref": _text(ref),
            "measured_at": stamps[0] if stamps else None,
            "page": _text(name),
            "status": verdict,
            "policy": _text(comparison.get("policy")),
            "runs_per_variant": comparison.get("runs_per_variant"),
            "metrics": metrics,
            "issues": [_text(i) for i in (comparison.get("issues") or [])[:5]],
            "env": environment(runs, name),
            "run_url": _url(run_url),
            "commit_url": _url(commit_url),
        })
    return records


def load_history(path: Path) -> list[dict]:
    """Records of a history file in measurement order; malformed lines are skipped."""
    records = []
    for line in path.read_text().splitlines() if path.is_file() else []:
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(r, dict) and r.get("schema_version") == SCHEMA_VERSION and isinstance(r.get("page"), str):
            r.setdefault("metrics", {})
            r.setdefault("env", {})
            records.append(r)
    return sorted(records, key=lambda r: str(r.get("measured_at") or ""))


def first_valid(records: list[dict]) -> list[dict]:
    """
    One record per page, commit and workflow run: of the run's attempts, the first valid
    measurement, otherwise the first record. A re-run that replaces an inconvenient result
    would bias the history; separate runs of one commit (scheduled A/A jobs) all count.
    """
    chosen: dict[tuple, int] = {}
    for i, r in enumerate(records):
        run = re.sub(r"/attempts/\d+$", "", str(r.get("run_url") or f"#{i}"))
        key = (r["page"], r.get("commit") or f"#{i}", run)
        if key not in chosen or (records[chosen[key]]["status"] not in VALID and r["status"] in VALID):
            chosen[key] = i
    return [records[i] for i in sorted(chosen.values())]


def _segment_key(r: dict) -> tuple:
    env = r.get("env") or {}
    return r.get("policy"), r.get("runs_per_variant"), env.get("throttling"), env.get("chrome_version")


def change_point(records: list[dict], metric: str, cfg: CpdConfig = CPD) -> dict:
    """
    Advisory change-point check of one page/metric series. Only the trailing points measured
    with the same policy, loads, throttling and Chrome version are pooled.
    """
    points = [r for r in records if r["status"] in VALID
              and _number((r["metrics"].get(metric) or {}).get("pr_median")) is not None]
    if not points:
        return {"checked": False, "reason": "no valid points"}
    key = _segment_key(points[-1])
    start = len(points)
    while start > 0 and _segment_key(points[start - 1]) == key:
        start -= 1
    segment = points[start:]
    if len(segment) < MIN_POINTS:
        return {"checked": False, "reason": f"{len(segment)} of {MIN_POINTS} comparable points"}
    frame = pd.DataFrame({
        "value": [r["metrics"][metric]["pr_median"] for r in segment],
        "bench": [_number(r["env"].get("benchmark_index")) or np.nan for r in segment],
        "cpu_model": [r["env"].get("cpu_model") for r in segment],
    })
    if frame["value"].median() == 0:
        return {"checked": False, "reason": "median is zero"}
    window, past = frame.iloc[-cfg.window:], frame.iloc[:-cfg.window]
    values = past_adjusted(window, window["value"].to_numpy(float), past, "bench-guarded")
    k, p = e_divisive(values, cfg, np.random.default_rng(cfg.seed))
    before, after = float(np.median(values[:k])), float(np.median(values[k:]))
    change = after / before - 1 if before > 0 else None
    first = segment[len(segment) - len(window) + k]
    return {"checked": True, "points": len(window), "past": len(past), "p": p, "change": change,
            "warning": bool(p < cfg.alpha and after > before), "commit": first.get("commit"),
            "measured_at": first.get("measured_at"), "record": first}


# --- dashboard ---------------------------------------------------------------------------------

# Graphite neutrals; CPU models take the first three validated categorical slots (all-pairs safe
# for colour-vision deficiencies), further models share "other". Status colours mean status only.
CSS = """
:root {
  color-scheme: light;
  --bg: #fafafa; --card: #ffffff; --raised: #f4f4f5; --hair: rgba(23, 23, 23, 0.08);
  --text: #171717; --text-2: #525252; --muted: #6e6e6e;
  --cpu-1: #2a78d6; --cpu-2: #eb6834; --cpu-3: #1baf7a; --cpu-other: #a3a3a3;
  --regression: #dc2626; --advisory: #b45309; --quiet: #d4d4d4; --trace: #a3a3a3;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --bg: #141415; --card: #19191b; --raised: #232325; --hair: rgba(237, 237, 237, 0.08);
    --text: #ededed; --text-2: #a1a1a6; --muted: #8b8b91;
    --cpu-1: #3987e5; --cpu-2: #d95926; --cpu-3: #199e70; --cpu-other: #6b6b70;
    --regression: #e5484d; --advisory: #f0a020; --quiet: #3a3a3d; --trace: #5c5c61;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #141415; --card: #19191b; --raised: #232325; --hair: rgba(237, 237, 237, 0.08);
  --text: #ededed; --text-2: #a1a1a6; --muted: #8b8b91;
  --cpu-1: #3987e5; --cpu-2: #d95926; --cpu-3: #199e70; --cpu-other: #6b6b70;
  --regression: #e5484d; --advisory: #f0a020; --quiet: #3a3a3d; --trace: #5c5c61;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
       font: 14px/20px system-ui, -apple-system, "Segoe UI", sans-serif; }
.mono, td.num, .figure, svg text { font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
       font-variant-numeric: tabular-nums; }
main { max-width: 1280px; margin: 0 auto; padding: 32px; }
header { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; flex-wrap: wrap;
         padding-bottom: 24px; border-bottom: 1px solid var(--hair); }
.brand { font-size: 16px; font-weight: 600; }
h1 { font-size: 28px; line-height: 36px; font-weight: 500; margin: 24px 0 4px; }
h2 { font-size: 20px; line-height: 28px; font-weight: 500; margin: 0; }
h3 { font-size: 14px; line-height: 20px; font-weight: 500; margin: 0; }
p { margin: 0; }
.text-2 { color: var(--text-2); } .muted { color: var(--muted); }
.meta { font-size: 12px; line-height: 16px; color: var(--muted); }
section { margin-top: 48px; }
.section-head { display: flex; align-items: baseline; justify-content: space-between; gap: 16px;
                flex-wrap: wrap; margin-bottom: 16px; }
.legend { display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: 12px; line-height: 16px; color: var(--text-2); }
.legend span { white-space: nowrap; }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 4px; margin-right: 8px; }
.cell { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 8px; }
.panels { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
@media (max-width: 900px) { .panels { grid-template-columns: 1fr; } main { padding: 16px; } }
.panel { background: var(--card); border: 1px solid var(--hair); border-radius: 12px; padding: 20px; }
.panel-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.figure { font-size: 20px; line-height: 28px; font-weight: 500; text-align: right; }
.figure small { display: block; font-size: 12px; line-height: 16px; font-weight: 400; color: var(--text-2); }
.panel .note { margin-top: 12px; font-size: 13px; line-height: 20px; color: var(--text-2); }
.panel .note.warn::before { content: ""; display: inline-block; width: 8px; height: 8px; border-radius: 2px;
                            margin-right: 8px; background: var(--advisory); }
svg { width: 100%; height: auto; display: block; overflow: visible; }
svg text { fill: var(--muted); font-size: 12px; }
.grid { stroke: var(--hair); stroke-width: 1; }
.trace { stroke: var(--trace); stroke-width: 1.5; fill: none; stroke-linejoin: round; }
.ring { fill: none; stroke: var(--regression); stroke-width: 2; }
.latest { fill: none; stroke: var(--text); stroke-width: 1.5; }
.cp { stroke: var(--advisory); stroke-width: 1.5; stroke-dasharray: 4 4; }
.cp-span { fill: var(--advisory); opacity: 0.08; }
.browser { stroke: var(--muted); stroke-width: 1; stroke-dasharray: 1 3; }
.strip-quiet { fill: var(--quiet); } .strip-regression { fill: var(--regression); }
.strip-invalid { fill: none; stroke: var(--muted); stroke-width: 1; }
.table { overflow-x: auto; background: var(--card); border: 1px solid var(--hair); border-radius: 12px; }
table { border-collapse: collapse; width: 100%; font-size: 13px; line-height: 20px; white-space: nowrap; }
th { font-weight: 500; color: var(--text-2); text-align: left; }
th, td { padding: 8px 16px; border-bottom: 1px solid var(--hair); }
tbody tr:last-child td { border-bottom: 0; }
th.num, td.num { text-align: right; }
td .delta { color: var(--muted); margin-left: 8px; }
.verdict-regression { color: var(--regression); }
details { margin-top: 16px; }
summary { cursor: pointer; color: var(--text-2); font-size: 13px; line-height: 20px; padding: 4px 0; }
summary:focus-visible, a:focus-visible { outline: 2px solid var(--text); outline-offset: 2px; border-radius: 4px; }
details .table { margin-top: 8px; }
a { color: inherit; text-decoration-color: var(--hair); text-underline-offset: 3px; }
a:hover { text-decoration-color: currentColor; }
.how { max-width: 72ch; color: var(--text-2); }
.how li { margin-bottom: 8px; }
"""

STATUS = {"regression": "regression", "no_regression_detected": "no regression detected",
          "invalid": "invalid", "error": "error"}
NAMES = {"fcp": "First Contentful Paint", "lcp": "Largest Contentful Paint",
         "tbt": "Total Blocking Time", "cls": "Cumulative Layout Shift"}
CPU_SLOTS = 3


def _e(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _fmt(value: float | None, metric: str) -> str:
    if value is None:
        return "–"
    return f"{value:.3f}" if metric == "cls" else f"{value:,.0f} ms"


def _pct(value: float | None) -> str:
    return "–" if value is None else f"{value:+.1%}"


def _chrome(r: dict) -> str:
    return r["env"].get("chrome_binary_version") or r["env"].get("chrome_version") or "unknown"


def _short(sha) -> str:
    return _e(str(sha)[:7]) if sha else "–"


def _link(text: str, url) -> str:
    url = _url(url)
    return f'<a href="{_e(url)}">{text}</a>' if url else text


def cpu_name(model: str | None) -> str:
    """'AMD EPYC 7763 64-Core Processor' -> 'EPYC 7763'; unknown formats pass through."""
    if not model:
        return "unknown"
    m = re.search(r"EPYC\s+(\w+)", model)
    if m:
        return f"EPYC {m.group(1)}"
    m = re.search(r"(?i)xeon\(r\)\s+(?:platinum\s+)?([\w-]+)", model)
    if m:
        return f"Xeon {m.group(1)}"
    return model


def _ticks(lo: float, hi: float, n: int = 4) -> list[float]:
    span = hi - lo or abs(hi) or 1.0
    raw = span / n
    step = 10 ** math.floor(math.log10(raw))
    step *= next(m for m in (1, 2, 5, 10) if raw <= m * step)
    first = math.ceil(lo / step) * step
    return [first + i * step for i in range(int((hi - first) / step) + 1)]


def colors(records: list[dict]) -> dict[str, str]:
    """
    CPU model -> colour variable in order of first appearance, so a model keeps its colour as
    the history grows; models after the third share "other".
    """
    order: list[str] = []
    for r in records:
        model = r["env"].get("cpu_model") or "unknown"
        if model not in order:
            order.append(model)
    return {m: f"var(--cpu-{i + 1})" if i < CPU_SLOTS else "var(--cpu-other)" for i, m in enumerate(order)}


def _value(r: dict, metric: str) -> float | None:
    if r["status"] not in VALID:
        return None
    return _number((r["metrics"].get(metric) or {}).get("pr_median"))


def chart(records: list[dict], metric: str, cpu: dict[str, str], cp: dict) -> str:
    """Inline SVG: the median of each measured commit, coloured by runner CPU, with the verdict strip."""
    width, height, left, right, top = 560, 232, 52, 8, 16
    plot_bottom, strip_y = 176, 196
    n = len(records)
    values = [_value(r, metric) for r in records]
    present = [v for v in values if v is not None]
    if not present:
        return '<p class="muted">No valid measurements</p>'
    lo, hi = min(present), max(present)
    pad = (hi - lo) * 0.1 or abs(hi) * 0.05 or 1.0
    if metric != "cls":
        pad = max(pad, 5.0)  # a flat millisecond series still gets a readable millisecond axis
    # metrics are never negative: no axis below zero
    lo, hi = max(lo - pad, 0.0) if lo >= 0 else lo - pad, hi + pad
    band = (width - left - right) / n
    x = lambda i: left + band * (i + 0.5)
    y = lambda v: top + (plot_bottom - top) * (hi - v) / (hi - lo)
    out = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{_e(NAMES[metric])}, '
           f'median per measured commit">']
    ticks = _ticks(lo, hi)
    # as many decimals as the tick step needs, so neighbouring labels never print the same
    step_size = ticks[1] - ticks[0] if len(ticks) > 1 else 1.0
    decimals = max(0, -math.floor(math.log10(step_size))) if step_size > 0 else 0
    for t in ticks:
        out.append(f'<line class="grid" x1="{left}" x2="{width - right}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>'
                   f'<text x="{left - 8}" y="{y(t) + 4:.1f}" text-anchor="end">{_e(f"{t:,.{decimals}f}")}</text>')
    if cp.get("warning"):
        i = records.index(cp["record"])
        xi = x(i) - band / 2
        out.append(f'<rect class="cp-span" x="{xi:.1f}" y="{top}" width="{width - right - xi:.1f}" '
                   f'height="{plot_bottom - top}"/>'
                   f'<line class="cp" x1="{xi:.1f}" x2="{xi:.1f}" y1="{top}" y2="{plot_bottom}"/>')
    for i in range(1, n):
        prev, cur = records[i - 1]["env"].get("chrome_version"), records[i]["env"].get("chrome_version")
        if prev != cur:
            xi = (x(i - 1) + x(i)) / 2
            out.append(f'<line class="browser" x1="{xi:.1f}" x2="{xi:.1f}" y1="{top}" y2="{plot_bottom}">'
                       f'<title>Chrome {_e(cur or "unknown")}</title></line>')
    path = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(values) if v is not None)
    out.append(f'<polyline class="trace" points="{path}"/>')
    radius = 3.5 if band >= 8 else 2.5
    for i, (r, v) in enumerate(zip(records, values)):
        m = r["metrics"].get(metric) or {}
        model = r["env"].get("cpu_model") or "unknown"
        tip = (f"{str(r.get('measured_at') or '')[:16].replace('T', ' ')}  {str(r.get('commit') or '')[:7]}\n"
               f"{STATUS.get(r['status'], r['status'])}\nmedian {_fmt(v, metric)}, "
               f"{_pct(m.get('relative_effect'))} vs base\n{cpu_name(model)}, Chrome {_chrome(r)}")
        title = f"<title>{_e(tip)}</title>"
        sx, sw = x(i) - min(band, 8) / 2 + 0.5, max(min(band, 8) - 1, 1)
        if v is None:
            out.append(f'<rect class="strip-invalid" x="{sx:.1f}" y="{strip_y + 0.5}" width="{sw - 1:.1f}" '
                       f'height="7">{title}</rect>')
            continue
        kind = "strip-regression" if m.get("regression") else "strip-quiet"
        out.append(f'<rect class="{kind}" x="{sx:.1f}" y="{strip_y}" width="{sw:.1f}" height="8" rx="1">{title}</rect>')
        out.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="{radius}" fill="{cpu[model]}" '
                   f'stroke="var(--card)" stroke-width="1">{title}</circle>')
        if m.get("regression"):
            out.append(f'<circle class="ring" cx="{x(i):.1f}" cy="{y(v):.1f}" r="{radius + 3}"/>')
    last = next((i for i in range(n - 1, -1, -1) if values[i] is not None), None)
    if last is not None:
        out.append(f'<circle class="latest" cx="{x(last):.1f}" cy="{y(values[last]):.1f}" r="{radius + 3}"/>')
    step = max(1, math.ceil(n / 5))
    for i in range(0, n, step):
        out.append(f'<text x="{x(i):.1f}" y="{height - 4}" text-anchor="middle">'
                   f'{_e(str(records[i].get("measured_at") or "")[5:10])}</text>')
    out.append(f'<text x="{left - 8}" y="{strip_y + 8}" text-anchor="end">gate</text>')
    out.append("</svg>")
    return "".join(out)


def describe(cp: dict) -> str:
    if not cp["checked"]:
        return f"Change-point check not run: {_e(cp['reason'])}"
    where = f"from {_short(cp['commit'])} ({_e(str(cp['measured_at'] or '')[:10])})"
    detail = f"E-Divisive p = {cp['p']:.3f}, last {cp['points']} points"
    if cp["warning"]:
        return f"Advisory: possible change of {_e(_pct(cp['change']))} {where}; {detail}"
    if cp["p"] < CPD.alpha:
        return f"Possible decrease of {_e(_pct(cp['change']))} {where}, not a warning; {detail}"
    return f"No change point in the latest window; {detail}"


def _trend(own: list[dict], metric: str) -> tuple[float | None, float | None]:
    """
    Latest median and its change against the median of up to ten earlier valid points measured on
    the same CPU model: across models the medians differ by more than most regressions.
    """
    points = [(r["env"].get("cpu_model"), v) for r in own if (v := _value(r, metric)) is not None]
    if not points:
        return None, None
    model, latest = points[-1]
    previous = [v for m, v in points[:-1] if m == model][-10:]
    if len(previous) < 3 or metric == "cls":
        return latest, None
    ref = float(np.median(previous))
    return latest, (latest / ref - 1 if ref > 0 else None)


def overview(pages: list[str], records: list[dict], warned: dict[str, int]) -> str:
    head = ("<th>Page</th><th>Last measured (UTC)</th><th>Gate</th>"
            + "".join(f'<th class="num">{m.upper()}</th>' for m in METRICS) + "<th>History</th>")
    rows = []
    for page in pages:
        own = [r for r in records if r["page"] == page]
        last = own[-1]
        cells = [f'<a href="#{_e(page)}">{_e(page)}</a>',
                 f'<span class="mono">{_e(str(last.get("measured_at") or "")[:16].replace("T", " "))}</span>',
                 f'<span class="verdict-{_e(last["status"])}">{_e(STATUS.get(last["status"], last["status"]))}</span>']
        for metric in METRICS:
            latest, change = _trend(own, metric)
            delta = f'<span class="delta">{_e(_pct(change))}</span>' if change is not None else ""
            cells.append(f'<td class="num">{_e(_fmt(latest, metric))}{delta}</td>')
        count = warned.get(page, 0)
        cells.append(f"{count} advisory warning{'s' if count != 1 else ''}" if count else "quiet")
        rows.append("<tr>" + "".join(c if c.startswith("<td") else f"<td>{c}</td>" for c in cells) + "</tr>")
    return (f'<div class="table"><table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
            '<p class="meta" style="margin-top:8px">Latest median; beside it the change against the median '
            "of up to ten earlier measurements on the same runner CPU model</p>")


def render(records: list[dict], title: str = "perfgate history") -> tuple[str, list[str]]:
    """The dashboard HTML and the advisory warnings as plain text lines."""
    records = first_valid(records)
    cpu = colors(records)
    pages = sorted({r["page"] for r in records})
    warnings: list[str] = []
    sections: list[str] = []
    warned: dict[str, int] = {}
    for page in pages:
        own = [r for r in records if r["page"] == page]
        panels = []
        for metric in METRICS:
            cp = change_point(own, metric)
            if cp.get("warning"):
                warned[page] = warned.get(page, 0) + 1
                warnings.append(f"{page} {metric.upper()}: possible change of {_pct(cp['change'])} from "
                                f"{str(cp['commit'] or '')[:7]} (E-Divisive p = {cp['p']:.3f}, advisory)")
            latest, change = _trend(own, metric)
            sub = f"{_pct(change)} vs same CPU" if change is not None else "latest median"
            panels.append(
                f'<div class="panel"><div class="panel-head"><div><h3>{metric.upper()}</h3>'
                f'<p class="meta">{NAMES[metric]}</p></div>'
                f'<div class="figure">{_e(_fmt(latest, metric))}<small>{_e(sub)}</small></div></div>'
                f"{chart(own, metric, cpu, cp)}"
                f'<p class="note{" warn" if cp.get("warning") else ""}">{describe(cp)}</p></div>')
        sections.append(
            f'<section id="{_e(page)}"><div class="section-head"><h2>{_e(page)}</h2>'
            f'<span class="meta">{len(own)} measurements</span></div>'
            f'<div class="panels">{"".join(panels)}</div>'
            f"<details><summary>Latest {min(len(own), 15)} measurements</summary>{table(own[-15:][::-1])}</details>"
            "</section>")
    body = [f'<header><span class="brand">perfgate</span>']
    if records:
        body.append(f'<span class="meta">{len(records)} measurements · {len(pages)} '
                    f'page{"s" if len(pages) != 1 else ""} · '
                    f'{_e(str(records[0].get("measured_at") or "")[:10])} to '
                    f'{_e(str(records[-1].get("measured_at") or "")[:10])}</span>')
    body.append(f"</header><h1>{_e(title)}</h1>")
    if not records:
        body.append('<p class="text-2">No history records yet</p>')
    else:
        body.append('<p class="text-2">Each point is one perfgate comparison of a pushed commit; '
                    "its height is the median of that commit's loads</p>")
        named = [(cpu_name(m), c) for m, c in cpu.items() if c != "var(--cpu-other)"]
        if len(named) < len(cpu):
            named.append(("other CPUs", "var(--cpu-other)"))
        legend = " ".join(f'<span><span class="dot" style="background:{c}"></span>{_e(name)}</span>'
                          for name, c in named)
        body.append(f'<section><div class="section-head"><h2>Now</h2><p class="legend">{legend}'
                    '<span><span class="cell" style="background:var(--regression)"></span>regression</span>'
                    '<span><span class="cell" style="background:var(--advisory)"></span>advisory change</span>'
                    f"</p></div>{overview(pages, records, warned)}</section>")
    body += sections
    if records:
        body.append(
            '<section><h2>How to read this</h2><ul class="how">'
            "<li>Colour is the runner CPU model. On shared CI runners the CPU changes between jobs and "
            "moves the medians; that is why each push is judged inside its own job, against its base, "
            "and the history only advises.</li>"
            "<li>The gate row under each chart shows that per-push verdict: grey no regression, red a "
            "regression of this metric, outlined invalid. A red ring marks the same point on the trace.</li>"
            "<li>A dashed amber line is an advisory change point: E-Divisive on the latest 20 points with the "
            "benchmarkIndex adjustment learned from earlier points (docs/history-cpd.md). It never fails a "
            "job; in the research data it also fired without a change in up to 17% of windows on some series.</li>"
            "<li>Dotted lines mark a Chrome version change; the ringed point is the latest measurement.</li>"
            "</ul></section>")
    page_html = ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
                 "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
                 f"<title>{_e(title)}</title><style>{CSS}</style></head><body><main>\n"
                 + "\n".join(body) + "\n</main></body></html>\n")
    return page_html, warnings


def table(records: list[dict]) -> str:
    head = ("<th>Measured (UTC)</th><th>Commit</th><th>Gate</th>"
            + "".join(f'<th class="num">{m.upper()}</th>' for m in METRICS) + "<th>CPU</th><th>Chrome</th><th>Run</th>")
    rows = []
    for r in records:
        cells = [f'<td class="mono">{_e(str(r.get("measured_at") or "")[:16].replace("T", " "))}</td>',
                 f'<td class="mono">{_link(_short(r.get("commit")), r.get("commit_url"))}</td>',
                 f'<td class="verdict-{_e(r["status"])}">{_e(STATUS.get(r["status"], r["status"]))}</td>']
        for metric in METRICS:
            m = r["metrics"].get(metric) or {}
            cells.append(f'<td class="num">{_e(_fmt(m.get("pr_median"), metric))}'
                         f'<span class="delta">{_e(_pct(m.get("relative_effect")))}</span></td>' if m
                         else '<td class="num">–</td>')
        cells += [f'<td>{_e(cpu_name(r["env"].get("cpu_model")))}</td>', f'<td class="mono">{_e(_chrome(r))}</td>',
                  f'<td>{_link("run", r.get("run_url")) if _url(r.get("run_url")) else "–"}</td>']
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return (f'<div class="table"><table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
            '<p class="meta" style="margin-top:8px">Median of the measured commit; beside it the change of the '
            "median against the compared base commit</p>")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    rec = sub.add_parser("record", help="append history records of perfgate report directories")
    rec.add_argument("--reports", type=Path, required=True, help="directory tree with perfgate reports")
    rec.add_argument("--out", type=Path, required=True, help="history JSONL file to append to")
    rec.add_argument("--commit", help="measured commit (default: gitSha of the raw records)")
    rec.add_argument("--base-commit")
    rec.add_argument("--ref")
    rec.add_argument("--run-url")
    rec.add_argument("--commit-url")
    rec.add_argument("--page", default="web", help="page label when the report has no measurements")
    dash = sub.add_parser("dashboard", help="render a history file as one HTML page")
    dash.add_argument("--history", type=Path, required=True)
    dash.add_argument("--out", type=Path, required=True)
    dash.add_argument("--title", default="perfgate history")
    dash.add_argument("--summary", type=Path, help="append advisory warnings as Markdown to this file")
    args = parser.parse_args(argv)

    if args.command == "record":
        reports = find_reports(args.reports)
        if not reports:
            print(f"no perfgate reports below {args.reports}", file=sys.stderr)
            return 1
        records = [r for d in reports for r in build_records(d, args.commit, args.base_commit, args.ref,
                                                             args.run_url, args.commit_url, args.page)]
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("a") as f:
            for r in records:
                f.write(json.dumps(r, sort_keys=True, allow_nan=False) + "\n")
        for r in records:
            print(f"{r['page']}: {r['status']}")
        return 0

    page, warnings = render(load_history(args.history), args.title)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page)
    if args.summary:
        with args.summary.open("a") as f:
            f.write("### perfgate history (advisory)\n\n")
            f.write("".join(f"- {w}\n" for w in warnings) if warnings else "No change-point warnings.\n")
    for w in warnings:
        print(f"::warning title=perfgate history (advisory)::{w}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
