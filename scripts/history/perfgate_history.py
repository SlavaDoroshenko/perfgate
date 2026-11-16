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
# Okabe-Ito, without yellow (unreadable on white); further CPU models share grey.
PALETTE = ("#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00")
OTHER = "#888888"
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

CSS = """
:root { --bg: #ffffff; --fg: #1a1a1a; --muted: #5f5f5f; --grid: #e2e2e2; --line: #9a9a9a; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #161616; --fg: #e8e8e8; --muted: #a8a8a8; --grid: #333333; --line: #777777; }
}
body { background: var(--bg); color: var(--fg); font: 14px/1.45 system-ui, sans-serif; margin: 0 auto;
       max-width: 960px; padding: 16px; }
h1 { font-size: 20px; } h2 { font-size: 17px; margin-top: 32px; } h3 { font-size: 14px; margin: 18px 0 4px; }
p, li { color: var(--fg); } .muted { color: var(--muted); }
svg { width: 100%; height: auto; display: block; }
svg text { fill: var(--muted); font: 11px system-ui, sans-serif; }
.grid { stroke: var(--grid); } .series { stroke: var(--line); fill: none; }
.mark { stroke: var(--fg); stroke-width: 1; } .cp { stroke: var(--fg); stroke-dasharray: 5 3; }
.browser { stroke: var(--muted); stroke-dasharray: 1 3; }
.table { overflow-x: auto; }
table { border-collapse: collapse; font-size: 13px; white-space: nowrap; }
th, td { border-bottom: 1px solid var(--grid); padding: 3px 8px; text-align: left; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
a { color: inherit; }
.swatch { display: inline-block; width: 10px; height: 10px; margin-right: 4px; vertical-align: baseline; }
.legend > span { white-space: nowrap; margin-right: 12px; }
"""

STATUS = {"regression": "regression", "no_regression_detected": "no regression detected",
          "invalid": "invalid", "error": "error"}


def _e(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _fmt(value: float | None, metric: str) -> str:
    if value is None:
        return "–"
    return f"{value:.3f}" if metric == "cls" else f"{value:.0f} ms"


def _pct(value: float | None) -> str:
    return "–" if value is None else f"{value:+.1%}"


def _chrome(r: dict) -> str:
    return r["env"].get("chrome_binary_version") or r["env"].get("chrome_version") or "unknown"


def _short(sha) -> str:
    return _e(str(sha)[:7]) if sha else "–"


def _link(text: str, url) -> str:
    url = _url(url)
    return f'<a href="{_e(url)}">{text}</a>' if url else text


def _ticks(lo: float, hi: float, n: int = 4) -> list[float]:
    span = hi - lo or abs(hi) or 1.0
    raw = span / n
    step = 10 ** math.floor(math.log10(raw))
    step *= next(m for m in (1, 2, 5, 10) if raw <= m * step)
    first = math.ceil(lo / step) * step
    return [first + i * step for i in range(int((hi - first) / step) + 1)]


def colors(records: list[dict]) -> dict[str, str]:
    """CPU model -> colour, by number of records, the same in every chart."""
    counts: dict[str, int] = {}
    for r in records:
        model = r["env"].get("cpu_model") or "unknown"
        counts[model] = counts.get(model, 0) + 1
    ranked = sorted(counts, key=lambda m: (-counts[m], m))
    return {m: PALETTE[i] if i < len(PALETTE) else OTHER for i, m in enumerate(ranked)}


def chart(records: list[dict], metric: str, cpu: dict[str, str], cp: dict) -> str:
    """Inline SVG: median of the measured commit per record, marker shape = verdict of this metric."""
    width, height, left, right, top, bottom = 900, 210, 64, 12, 22, 30
    n = len(records)
    values = [_number((r["metrics"].get(metric) or {}).get("pr_median")) if r["status"] in VALID else None
              for r in records]
    present = [v for v in values if v is not None]
    if not present:
        return '<p class="muted">No valid measurements.</p>'
    lo, hi = min(present), max(present)
    pad = (hi - lo) * 0.08 or abs(hi) * 0.05 or 1.0
    # metrics are never negative: no axis below zero
    lo, hi = max(lo - pad, 0.0) if lo >= 0 else lo - pad, hi + pad
    x = lambda i: left + (width - left - right) * (i + 0.5) / n
    y = lambda v: top + (height - top - bottom) * (hi - v) / (hi - lo)
    out = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{_e(metric.upper())} history">']
    for t in _ticks(lo, hi):
        out.append(f'<line class="grid" x1="{left}" x2="{width - right}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>'
                   f'<text x="{left - 6}" y="{y(t) + 4:.1f}" text-anchor="end">'
                   f'{_e(f"{t:.3g}" if metric == "cls" else f"{t:.0f}")}</text>')
    step = max(1, math.ceil(n / 6))
    for i in range(0, n, step):
        out.append(f'<text x="{x(i):.1f}" y="{height - 10}" text-anchor="middle">'
                   f'{_e(str(records[i].get("measured_at") or "")[:10])}</text>')
    for i in range(1, n):
        prev, cur = records[i - 1]["env"].get("chrome_version"), records[i]["env"].get("chrome_version")
        if prev != cur:
            xi = (x(i - 1) + x(i)) / 2
            out.append(f'<line class="browser" x1="{xi:.1f}" x2="{xi:.1f}" y1="{top}" y2="{height - bottom}"/>'
                       f'<text x="{xi + 3:.1f}" y="{top - 8}">Chrome {_e(cur or "unknown")}</text>')
    if cp.get("warning"):
        i = records.index(cp["record"])
        xi = x(i) - (width - left - right) / n / 2
        out.append(f'<line class="cp" x1="{xi:.1f}" x2="{xi:.1f}" y1="{top}" y2="{height - bottom}"/>'
                   f'<text x="{xi + 3:.1f}" y="{top + 10}">possible change {_e(_pct(cp["change"]))} (advisory)</text>')
    path = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(values) if v is not None)
    out.append(f'<polyline class="series" points="{path}"/>')
    for i, (r, v) in enumerate(zip(records, values)):
        m = r["metrics"].get(metric) or {}
        model = r["env"].get("cpu_model") or "unknown"
        tip = (f"{str(r.get('measured_at') or '')[:16]} {str(r.get('commit') or '')[:7]}\n"
               f"{STATUS.get(r['status'], r['status'])}\nmedian {_fmt(v, metric)}, "
               f"change {_pct(m.get('relative_effect'))} vs base\n{model}\nChrome {_chrome(r)}")
        title = f"<title>{_e(tip)}</title>"
        if v is None:
            cx, cy = x(i), height - bottom - 4
            out.append(f'<path class="mark" d="M{cx - 3:.1f},{cy - 3:.1f}l6,6m0,-6l-6,6">{title}</path>')
        elif m.get("regression"):
            cx, cy = x(i), y(v)
            out.append(f'<path class="mark" fill="{cpu[model]}" '
                       f'd="M{cx:.1f},{cy - 6:.1f}l5.5,9.5h-11z">{title}</path>')
        else:
            out.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="3.2" fill="{cpu[model]}">{title}</circle>')
    out.append("</svg>")
    return "".join(out)


def describe(cp: dict) -> str:
    if not cp["checked"]:
        return f"Change-point check not run: {_e(cp['reason'])}."
    where = f"from {_short(cp['commit'])} ({_e(str(cp['measured_at'] or '')[:10])})"
    detail = f"E-Divisive p = {cp['p']:.3f} on the last {cp['points']} points, {cp['past']} earlier points for the adjustment"
    if cp["warning"]:
        return f"<strong>Advisory warning:</strong> possible change of {_e(_pct(cp['change']))} {where}; {detail}."
    if cp["p"] < CPD.alpha:
        return f"Possible decrease of {_e(_pct(cp['change']))} {where}, not a warning; {detail}."
    return f"No change point in the latest window; {detail}."


def render(records: list[dict], title: str = "perfgate history") -> tuple[str, list[str]]:
    """The dashboard HTML and the advisory warnings as plain text lines."""
    records = first_valid(records)
    cpu = colors(records)
    pages = sorted({r["page"] for r in records})
    warnings: list[str] = []
    body = [f"<h1>{_e(title)}</h1>"]
    if records:
        body.append(f'<p class="muted">{len(records)} measurements of {len(pages)} page(s), '
                    f'{_e(str(records[0].get("measured_at") or "")[:10])} to '
                    f'{_e(str(records[-1].get("measured_at") or "")[:10])}.</p>')
    else:
        body.append("<p>No history records yet.</p>")
    body.append(
        "<p>Each point is the median of the measured commit's loads in one perfgate comparison against "
        "the previous state of the branch. A triangle marks a per-push regression verdict for that metric, "
        "a cross an invalid or failed measurement. Colours are runner CPU models; dotted lines mark a "
        "Chrome version change. Change-point warnings are advisory: E-Divisive on the latest 20 points "
        "with the benchmarkIndex adjustment learned from earlier points (docs/history-cpd.md). "
        "They do not fail any job; in the research data they also fired without a change in up to "
        "17% of windows on some series.</p>")
    if cpu:
        legend = " ".join(f'<span><span class="swatch" style="background:{c}"></span>{_e(m)}</span>'
                          for m, c in cpu.items())
        body.append(f'<p class="legend">CPU models: {legend}</p>')
    for page in pages:
        own = [r for r in records if r["page"] == page]
        body.append(f'<h2 id="{_e(page)}">{_e(page)}</h2>')
        for metric in METRICS:
            cp = change_point(own, metric)
            if cp.get("warning"):
                warnings.append(f"{page} {metric.upper()}: possible change of {_pct(cp['change'])} from "
                                f"{str(cp['commit'] or '')[:7]} (E-Divisive p = {cp['p']:.3f}, advisory)")
            body.append(f"<h3>{metric.upper()}</h3>{chart(own, metric, cpu, cp)}"
                        f'<p class="muted">{describe(cp)}</p>')
        body.append("<h3>Latest measurements</h3>" + table(own[-15:][::-1]))
    page_html = ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
                 "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
                 f"<title>{_e(title)}</title><style>{CSS}</style></head><body>\n"
                 + "\n".join(body) + "\n</body></html>\n")
    return page_html, warnings


def table(records: list[dict]) -> str:
    head = "".join(f"<th>{h}</th>" for h in ("Measured (UTC)", "Commit", "Verdict", *(m.upper() for m in METRICS),
                                             "CPU", "Chrome", "Run"))
    rows = []
    for r in records:
        cells = [_e(str(r.get("measured_at") or "")[:16].replace("T", " ")),
                 _link(_short(r.get("commit")), r.get("commit_url")),
                 _e(STATUS.get(r["status"], r["status"]))]
        for metric in METRICS:
            m = r["metrics"].get(metric) or {}
            cells.append(f'{_e(_fmt(m.get("pr_median"), metric))}, {_e(_pct(m.get("relative_effect")))}'
                         if m else "–")
        cells += [_e(r["env"].get("cpu_model") or "unknown"), _e(_chrome(r)),
                  _link("run", r.get("run_url")) if _url(r.get("run_url")) else "–"]
        rows.append("<tr>" + "".join(f'<td class="num">{c}</td>' if 3 <= i < 3 + len(METRICS) else f"<td>{c}</td>"
                                     for i, c in enumerate(cells)) + "</tr>")
    return (f'<div class="table"><table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
            '<p class="muted">Metric cells: median of the measured commit, change of the median against '
            "the compared base commit.</p>")


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
