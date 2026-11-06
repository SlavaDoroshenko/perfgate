// Renders perfgate comparison reports as one pull/merge request comment.
//
// Report files come from a measurement job that ran untrusted pull request code,
// so everything read from them is validated, escaped and size-limited here.
// Only the fixed explanatory text below is trusted.
import { lstat, readdir, readFile } from 'node:fs/promises';
import { join, relative, sep } from 'node:path';

export const STATUSES = ['no_regression_detected', 'regression', 'invalid'];
const MAX_REPORT_BYTES = 1024 * 1024;
const MAX_REPORTS = 20;
const MAX_METRICS = 40;
const MAX_ISSUES = 20;
const MAX_DEPTH = 6;
export const MAX_COMMENT_LENGTH = 60000; // GitHub rejects bodies above 65,536 characters

const METRIC_LABELS = { fcp: 'FCP', lcp: 'LCP', tbt: 'TBT', cls: 'CLS' };

export function marker(key = 'default') {
  if (!/^[A-Za-z0-9._-]{1,64}$/.test(key)) throw new Error('comment key must match [A-Za-z0-9._-]{1,64}');
  return `<!-- perfgate-comment:${key} -->`;
}

const ZWSP = String.fromCharCode(0x200b);
const CONTROL = new RegExp(`[${String.fromCharCode(0)}-${String.fromCharCode(0x1f)}${String.fromCharCode(0x7f, 0x2028, 0x2029)}]+`, 'g');

/** Plain text for a Markdown table cell: no markup, links, HTML, mentions or line breaks. */
export function escapeText(value, max = 120) {
  let text = String(value).replace(CONTROL, ' ').trim();
  if (text.length > max) text = `${text.slice(0, max - 1)}…`;
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/[\\`*_{}[\]()#+\-.!|~:]/g, ch => `\\${ch}`)
    // Break @mentions, team mentions and #/!123 references without hiding text.
    .replace(/@/g, `@${ZWSP}`);
}

function isObject(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function finite(value, field) {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error(`${field}: finite number expected`);
  return value;
}
function bool(value, field) {
  if (typeof value !== 'boolean') throw new Error(`${field}: boolean expected`);
  return value;
}

/** Validates a comparison.json object produced by perfgate_analysis.compare. */
export function parseComparison(raw) {
  if (!isObject(raw)) throw new Error('report: object expected');
  if (!STATUSES.includes(raw.status)) throw new Error('report: unknown status');
  if (typeof raw.policy !== 'string') throw new Error('report: policy missing');
  if (!Array.isArray(raw.metrics) || !Array.isArray(raw.issues)) throw new Error('report: metrics and issues arrays required');
  const metrics = raw.metrics.map((m, i) => {
    const at = `metrics[${i}]`;
    if (!isObject(m) || typeof m.name !== 'string' || !['ms', 'unitless'].includes(m.unit)) throw new Error(`${at}: name/unit invalid`);
    const interval = m.absolute_effect_interval;
    if (!Array.isArray(interval) || interval.length !== 2) throw new Error(`${at}: interval invalid`);
    const p = finite(m.p, `${at}.p`);
    if (p < 0 || p > 1) throw new Error(`${at}.p: outside [0, 1]`);
    const relative = m.relative_effect === null ? null : finite(m.relative_effect, `${at}.relative_effect`);
    return {
      name: m.name, unit: m.unit, n: finite(m.n, `${at}.n`),
      base: finite(m.base_median, `${at}.base_median`), pr: finite(m.pr_median, `${at}.pr_median`),
      effect: finite(m.absolute_effect, `${at}.absolute_effect`), relative,
      interval: interval.map((x, j) => finite(x, `${at}.interval[${j}]`)),
      level: finite(m.interval_level, `${at}.interval_level`), p,
      aboveMargin: bool(m.above_margin, `${at}.above_margin`),
      significant: bool(m.holm_rejected, `${at}.holm_rejected`),
      regression: bool(m.regression, `${at}.regression`),
    };
  });
  const anyRegression = metrics.some(m => m.regression);
  // Refuse internally inconsistent reports instead of rendering a misleading verdict.
  if (raw.status === 'regression' && !anyRegression) throw new Error('report: regression status without a regressed metric');
  if (raw.status === 'no_regression_detected' && (anyRegression || !metrics.length)) throw new Error('report: inconsistent quiet status');
  if (raw.status !== 'invalid' && raw.issues.length) throw new Error('report: valid status with measurement issues');
  return {
    status: raw.status, policy: raw.policy,
    runs: typeof raw.runs_per_variant === 'number' && Number.isFinite(raw.runs_per_variant) ? raw.runs_per_variant : null,
    metrics, issues: raw.issues.map(x => String(x)),
  };
}

async function readJson(path) {
  const info = await lstat(path);
  if (!info.isFile()) throw new Error('not a regular file');
  if (info.size > MAX_REPORT_BYTES) throw new Error('file too large');
  return JSON.parse(await readFile(path, 'utf8'));
}

async function exists(path) {
  try { return (await lstat(path)).isFile(); } catch { return false; }
}

/**
 * Finds report directories below root: every directory with comparison.json or
 * execution.json. Symbolic links are never followed. The first path segment is
 * the artifact name when artifacts were downloaded into separate directories.
 */
export async function loadReports(root) {
  const found = [];
  async function walk(dir, depth) {
    if (depth > MAX_DEPTH || found.length >= MAX_REPORTS) return;
    let entries;
    try { entries = await readdir(dir, { withFileTypes: true }); } catch { return; }
    const names = new Set(entries.filter(e => e.isFile()).map(e => e.name));
    if (names.has('comparison.json') || names.has('execution.json')) found.push(dir);
    for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
      if (entry.isDirectory() && !entry.isSymbolicLink()) await walk(join(dir, entry.name), depth + 1);
    }
  }
  await walk(root, 0);
  const reports = [];
  for (const dir of found) {
    const path = relative(root, dir).split(sep).filter(Boolean);
    const report = { path: path.join('/') || '.', artifact: path[0] ?? null, comparison: null, error: null, seconds: null, refs: null };
    if (await exists(join(dir, 'comparison.json'))) {
      try { report.comparison = parseComparison(await readJson(join(dir, 'comparison.json'))); }
      catch (error) { report.error = `unreadable comparison.json (${error.message})`; }
    } else {
      report.error = 'comparison.json missing: measurement or analysis did not complete';
    }
    try {
      const execution = await readJson(join(dir, 'execution.json'));
      if (typeof execution.total_seconds === 'number' && Number.isFinite(execution.total_seconds)) report.seconds = execution.total_seconds;
    } catch { /* timing is optional */ }
    // compare-refs writes refs.json one level above comparison/.
    for (const candidate of [join(dir, 'refs.json'), join(dir, '..', 'refs.json')]) {
      try {
        const refs = await readJson(candidate);
        if (/^[0-9a-f]{40}$/.test(refs.base) && /^[0-9a-f]{40}$/.test(refs.pr)) { report.refs = { base: refs.base, pr: refs.pr }; break; }
      } catch { /* optional */ }
    }
    reports.push(report);
  }
  return reports;
}

function severity(report) {
  if (report.comparison?.status === 'regression') return 0;
  return report.comparison?.status === 'no_regression_detected' ? 2 : 1;
}

export function overallStatus(reports) {
  if (reports.some(r => r.comparison?.status === 'regression')) return 'regression';
  if (!reports.length || reports.some(r => !r.comparison || r.comparison.status === 'invalid')) return 'inconclusive';
  return 'no_regression_detected';
}

const HEADLINES = {
  regression: 'Performance regression detected',
  inconclusive: 'Inconclusive: no valid comparison',
  no_regression_detected: 'No regression detected',
};

function formatValue(value, unit) {
  if (unit === 'unitless') return value.toFixed(4);
  return Math.abs(value) >= 100 ? `${Math.round(value)} ms` : `${value.toFixed(1)} ms`;
}
function signed(value, unit) {
  const text = formatValue(value, unit);
  return value > 0 ? `+${text}` : value < 0 ? text.replace('-', '−') : text;
}
function formatP(p) {
  return p < 0.0001 ? '<0.0001' : p.toFixed(4);
}
function metricName(name) {
  const slash = name.lastIndexOf('/');
  const metric = name.slice(slash + 1);
  const page = slash > 0 ? name.slice(0, slash) : '';
  const label = METRIC_LABELS[metric] ?? metric;
  return page ? `${escapeText(page, 60)} · ${escapeText(label, 20)}` : escapeText(label, 40);
}
function decision(m) {
  if (m.regression) return '**regression**';
  if (m.significant) return 'significant, within margin';
  if (m.aboveMargin) return 'above margin, not significant';
  return 'no change detected';
}

function safeUrl(url) {
  if (typeof url !== 'string' || !/^https:\/\/[^\s()<>]+$/.test(url)) return null;
  return url;
}

function renderReport(report, links) {
  const lines = [];
  const title = report.artifact ? escapeText(report.path, 100) : 'Report';
  const link = report.artifact ? safeUrl(links[report.artifact]) : null;
  const status = report.comparison?.status;
  const statusText = status === 'regression' ? 'regression' : status === 'no_regression_detected' ? 'no regression detected' : 'invalid';
  lines.push(`#### ${title}: ${report.comparison ? statusText : 'no result'}`, '');
  const facts = [];
  if (report.comparison?.runs) facts.push(`${report.comparison.runs} loads per variant requested`);
  if (report.seconds !== null) facts.push(`${Math.round(report.seconds)} s measurement and analysis`);
  if (report.refs) facts.push(`base \`${report.refs.base.slice(0, 7)}\` → PR \`${report.refs.pr.slice(0, 7)}\``);
  if (link) facts.push(`[report artifact](${link})`);
  if (facts.length) lines.push(facts.join(' · '), '');
  if (report.error) {
    lines.push(`Report problem: ${escapeText(report.error, 300)}`, '');
    return lines;
  }
  const { metrics, issues } = report.comparison;
  if (issues.length) {
    lines.push(`<details><summary>Measurement issues (${issues.length}); no verdict was computed</summary>`, '');
    for (const issue of issues.slice(0, MAX_ISSUES)) lines.push(`- ${escapeText(issue, 300)}`);
    if (issues.length > MAX_ISSUES) lines.push(`- … ${issues.length - MAX_ISSUES} more in the artifact`);
    lines.push('', '</details>', '');
  }
  if (metrics.length) {
    const level = Math.round(metrics[0].level * 100);
    lines.push(`| Metric | Base median | PR median | Change | ${level}% interval of change | Raw p, one-sided | Result |`,
      '|---|---:|---:|---:|---:|---:|---|');
    for (const m of metrics.slice(0, MAX_METRICS)) {
      const relative = m.relative === null ? 'zero base' : `${m.relative >= 0 ? '+' : '−'}${Math.abs(m.relative * 100).toFixed(1)}%`;
      lines.push(`| ${metricName(m.name)} | ${formatValue(m.base, m.unit)} | ${formatValue(m.pr, m.unit)} | ` +
        `${signed(m.effect, m.unit)} (${relative}) | [${signed(m.interval[0], m.unit)}, ${signed(m.interval[1], m.unit)}] | ` +
        `${formatP(m.p)} | ${decision(m)} |`);
    }
    if (metrics.length > MAX_METRICS) lines.push('', `${metrics.length - MAX_METRICS} more metrics are in the artifact.`);
    lines.push('');
  }
  return lines;
}

/**
 * @param reports output of loadReports
 * @param options.key sticky comment key; options.runUrl link to the measuring run;
 *   options.artifactLinks {artifactName: url}; options.sha measured head commit.
 */
export function renderComment(reports, options = {}) {
  const status = overallStatus(reports);
  const lines = [marker(options.key), `### perfgate: ${HEADLINES[status]}`, ''];
  const sha = typeof options.sha === 'string' && /^[0-9a-f]{7,40}$/.test(options.sha) ? options.sha.slice(0, 7) : null;
  const runUrl = safeUrl(options.runUrl);
  const context = [];
  if (sha) context.push(`commit \`${sha}\``);
  if (runUrl) context.push(`[measurement run](${runUrl})`);
  const policies = [...new Set(reports.map(r => r.comparison?.policy).filter(Boolean))];
  if (policies.length) context.push(`policy ${policies.map(p => /^[A-Za-z0-9._-]{1,80}$/.test(p) ? `\`${p}\`` : 'unrecognized').join(', ')} (candidate)`);
  if (context.length) lines.push(context.join(' · '), '');
  if (!reports.length) {
    lines.push('The measurement run produced no perfgate report. Check the run log: the application may have failed to build or start.', '');
  }
  const counts = { regression: 0, problem: 0, quiet: 0 };
  for (const r of reports) counts[severity(r) === 0 ? 'regression' : severity(r) === 1 ? 'problem' : 'quiet']++;
  if (reports.length) {
    lines.push(`${reports.length} comparison(s): ${counts.regression} with a regression, ` +
      `${counts.problem} invalid or incomplete, ${counts.quiet} without a detected regression.`, '');
  }
  const ordered = [...reports].sort((a, b) => severity(a) - severity(b));
  for (const report of ordered.slice(0, MAX_REPORTS)) lines.push(...renderReport(report, options.artifactLinks ?? {}));
  lines.push(
    '<details><summary>How to read this</summary>', '',
    '- A metric is a **regression** only when the one-sided Mann–Whitney test is significant after Holm correction across all listed metrics *and* the observed median change exceeds the policy margin (1% FCP/LCP, max(5%, 5 ms) TBT, 0.005 CLS).',
    '- "No regression detected" is not proof that performance is unchanged: small, rare or tail-only slowdowns can pass unnoticed.',
    '- Intervals are descriptive pointwise bootstrap intervals of the median difference; they do not decide the verdict.',
    '- "Invalid" means failed loads, missing metrics or a broken protocol. Never treat it as a pass.',
    '- This comment reports measurements of pull request code. It is advisory; enforce merges with a required status check.',
    '', '</details>', '');
  let body = lines.join('\n');
  const max = options.maxLength ?? MAX_COMMENT_LENGTH;
  if (body.length > max) {
    const note = '\n\n…comment truncated; see the run artifacts for the full report.\n';
    body = body.slice(0, body.lastIndexOf('\n', max - note.length)) + note;
  }
  return { status, body };
}
