/** Fixed-size exploratory rare-stall acquisition, outside the frozen collector. */
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { mkdir, writeFile, appendFile, readFile, readdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { parseArgs } from 'node:util';
import { createHash } from 'node:crypto';
import { gzipSync } from 'node:zlib';
import { performance } from 'node:perf_hooks';
import { collectEnv, gitSha } from '../packages/collector/dist/env.js';
import { Run } from '../packages/collector/dist/schema.js';
import { extractMetrics, extractError, extractChromeVersion, extractFailedRequests } from '../packages/collector/dist/extract.js';
import { measurementIssues } from '../packages/collector/dist/quality.js';
import { stallIndices, stallEvidence } from './tail-protocol.mjs';
const require = createRequire(new URL('../packages/collector/package.json', import.meta.url));
const { default: lighthouse } = await import(pathToFileURL(require.resolve('lighthouse')).href);
const chromeLauncher = await import(pathToFileURL(require.resolve('chrome-launcher')).href);
const { values: v } = parseArgs({ options: {
  url: { type: 'string' }, out: { type: 'string' }, condition: { type: 'string' },
  seed: { type: 'string' }, runs: { type: 'string', default: '20' }, warmup: { type: 'string', default: '2' },
  'stall-ms': { type: 'string', default: '800' }, experiment: { type: 'string' },
} });
const runs = Number(v.runs), warmup = Number(v.warmup), seed = Number(v.seed), duration = Number(v['stall-ms']);
if (!v.url || !v.out || !v.experiment || !v.seed || !process.env.CHROME_PATH ||
    !Number.isInteger(warmup) || warmup < 0 || !Number.isFinite(duration) || duration <= 0 || duration > 5000) throw new Error('Invalid arguments');
const selected = stallIndices(v.condition, runs, seed);
const pilot = runs === 20 && warmup === 2;
let freezeBytes = null;
if (pilot) {
  freezeBytes = await readFile('docs/protocols/tail-browser-pilot-2026-10-30.json');
  const frozen = JSON.parse(freezeBytes);
  for (const [path, digest] of Object.entries(frozen.source_sha256)) {
    const actual = createHash('sha256').update(await readFile(path)).digest('hex');
    if (actual !== digest) throw new Error(`Frozen source changed: ${path}`);
  }
  if (!frozen.seeds.includes(seed) || duration !== frozen.stall_ms) throw new Error('Not a predeclared pilot configuration');
}
const readiness = await fetch(v.url, { signal: AbortSignal.timeout(10000) });
if (!readiness.ok) throw new Error(`HTTP ${readiness.status}`);
await readiness.arrayBuffer();
const out = resolve(v.out);
await mkdir(out); await mkdir(`${out}/evidence`);
const hash = data => createHash('sha256').update(data).digest('hex');
const sourceFiles = ['scripts/collect-tail.mjs', 'scripts/tail-protocol.mjs', 'scripts/prepare-tail-fixture.mjs', 'experiments/rare-stalls/probe.js', 'pnpm-lock.yaml'];
const sourceHashes = Object.fromEntries(await Promise.all(sourceFiles.map(async p => [p, hash(await readFile(p))])));
const fixtureFiles = ['tail-heavy.html', 'tail-probe.js', ...(await readdir('apps/demo-spa/dist/assets-heavy')).sort().map(p => `assets-heavy/${p}`)];
const fixtureHashes = Object.fromEntries(await Promise.all(fixtureFiles.map(async p => [p, hash(await readFile(`apps/demo-spa/dist/${p}`))])));
const appBuild = hash(JSON.stringify(fixtureHashes));
const env = collectEnv(), sha = gitSha();
const manifest = { protocol: 'tail-browser-pilot-2026-10-30', experiment: v.experiment,
  condition: v.condition, seed, runs, warmup, stall_ms: duration, selected_indices: selected,
  acquisition_role: pilot ? 'pilot' : 'instrumentation-smoke', freeze_sha256: freezeBytes ? hash(freezeBytes) : null,
  interpretation: 'fixed 15% contamination, not iid Bernoulli sampling; exploratory pilot, not power estimation',
  source: sha, source_sha256: sourceHashes, fixture_sha256: fixtureHashes, app_build: appBuild,
  started: new Date().toISOString(), completed_slots: 0, failures: [], env };
const save = () => writeFile(`${out}/manifest.json`, JSON.stringify(manifest, null, 2) + '\n');
await save();
let warmupErrors = 0, warmupDurationMs = 0;
const warmupStart = performance.now();
for (let index = -warmup; index < runs; index++) {
  if (index === 0) warmupDurationMs = performance.now() - warmupStart;
  for (const variant of ['base', 'pr']) {
    const expected = index >= 0 && variant === 'pr' && selected.includes(index);
    const url = new URL(v.url); url.searchParams.set('stall', expected ? '1' : '0');
    url.searchParams.set('stall_ms', String(duration));
    const timestamp = new Date().toISOString(), started = performance.now();
    const name = `${index < 0 ? 'warmup' : 'run'}-${Math.abs(index)}-${variant}`;
    let chrome, lhr, evidence, error = null;
    try {
      chrome = await chromeLauncher.launch({ chromeFlags: ['--headless=new', '--no-sandbox', '--disable-gpu'] });
      const result = await lighthouse(url.href, { port: chrome.port, output: 'json', logLevel: 'error', onlyCategories: ['performance'], throttlingMethod: 'devtools' });
      if (!result) throw new Error('No Lighthouse result');
      lhr = result.lhr;
      evidence = stallEvidence(result.artifacts.Trace.traceEvents, expected);
      if (expected && (evidence.durationMs === null || evidence.durationMs < duration - 5)) evidence.issues.push('Recorded stall shorter than intended wall-clock duration');
      await writeFile(`${out}/evidence/${name}.lhr.json.gz`, gzipSync(JSON.stringify(lhr)));
      if (expected || index === 0) await writeFile(`${out}/evidence/${name}.trace.json.gz`, gzipSync(JSON.stringify(result.artifacts.Trace)));
      error = [extractError(lhr), ...evidence.issues].filter(Boolean).join('; ') || null;
    } catch (err) { error = String(err); }
    finally { if (chrome) await chrome.kill(); }
    const record = Run.parse({ schemaVersion: 1, experimentId: v.experiment, app: 'tail-heavy', variant,
      url: url.href, inject: variant === 'pr' && v.condition !== 'aa' ? { type: 'tail-stall', size: duration } : null,
      mode: 'abab', throttling: 'devtools', warmup, warmupErrors, plannedRuns: runs,
      appBuild, label: v.condition === 'aa' ? 'aa' : 'injected', runIndex: Math.max(0, index), order: index < 0 ? 0 : index * 2 + Number(variant === 'pr'),
      durationMs: performance.now() - started, warmupDurationMs,
      metrics: lhr ? extractMetrics(lhr) : { fcp: null, lcp: null, tbt: null, cls: null, si: null, ttfb: null },
      benchmarkIndex: lhr?.environment?.benchmarkIndex ?? null, failedRequests: lhr ? extractFailedRequests(lhr) : null,
      error, env: { ...env, chromeVersion: lhr ? extractChromeVersion(lhr) : null, lighthouseVersion: lhr?.lighthouseVersion ?? null },
      gitSha: sha, timestamp });
    const issues = measurementIssues(record);
    if (issues.length) { manifest.failures.push({ index, variant, issues }); if (index < 0) warmupErrors++; }
    await writeFile(`${out}/evidence/${name}.json`, JSON.stringify({ index, variant, expected, evidence, issues, record }, null, 2) + '\n');
    if (index >= 0) await appendFile(`${out}/runs.jsonl`, JSON.stringify(record) + '\n');
    manifest.completed_slots++; await save();
    console.log(name, expected ? 'STALL' : 'clean', 'TBT', record.metrics.tbt, 'duration', evidence?.durationMs, issues.join('; '));
  }
}
manifest.finished = new Date().toISOString(); manifest.warmup_errors = warmupErrors; await save();
if (manifest.failures.length) process.exitCode = 2;
