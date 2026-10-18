// Run both actual collectors sequentially on the same machine and app build.
// Use RUNS=10, CASE=aa|fcp2|tbt10, REPEAT=1..3, CHROME_PATH and PYTHON.
import { spawnSync } from 'node:child_process';
import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import os from 'node:os';

const root = resolve(import.meta.dirname, '../..');
const runs = Number(process.env.RUNS ?? 10);
const repeat = Number(process.env.REPEAT ?? 1);
const name = process.env.CASE ?? 'aa';
const cases = { aa: '', fcp2: '?inject=script-delay:36', tbt10: '?inject=long-task:99' };
if (!(name in cases) || !Number.isInteger(runs) || runs < 2) throw new Error('invalid CASE or RUNS');
const out = resolve(process.env.RESULT_DIR ?? `results/sitespeed/${name}-${repeat}`);
const base = 'http://127.0.0.1:4173/heavy.html';
const pr = base + cases[name];
const executable = process.env.SITESPEED_BIN ?? resolve(import.meta.dirname, 'node_modules/sitespeed.io/bin/sitespeed.js');
const script = resolve(import.meta.dirname, 'throttle.mjs');
const config = resolve(import.meta.dirname, 'config.json');
const capture = resolve(import.meta.dirname, 'capture.mjs');
await mkdir(out, { recursive: true });
if ((await readdir(out)).length) throw new Error('RESULT_DIR must be empty; use a new directory for each comparison');
await mkdir(`${out}/baseline`, { recursive: true });
const times = {};
function run(command, args, env = {}) {
  const result = spawnSync(command, args, { cwd: root, env: { ...process.env, ...env }, stdio: 'inherit' });
  if (result.error || result.status !== 0) throw result.error ?? new Error(`${command} exited ${result.status}`);
}
function sitespeed() {
  const start = performance.now();
  for (const [variant, url] of [['base', base], ['pr', pr]]) {
    // Each call creates fresh profiles. Warm-up loads are never included in the baseline.
    for (const warm of [true, false]) {
      const folder = `${out}/${variant}${warm ? '-warmup' : ''}`;
      const args = [executable, script, '--config', config, '-n', String(warm ? 2 : runs),
        '--outputFolder', folder, '--compare.baselinePath', warm ? folder : `${out}/baseline`,
        '--compare.saveBaseline', String(!warm && variant === 'base')];
      if (process.env.CHROME_PATH) args.push('--chrome.binaryPath', process.env.CHROME_PATH);
      if (!warm && variant === 'pr') args.push('--plugins.add', capture);
      run(process.execPath, args, { PERFGATE_URL: url, PERFGATE_COMPARE_OUT: `${out}/compare.json` });
    }
  }
  times.sitespeed_seconds = (performance.now() - start) / 1000;
}
function lighthouse() {
  const start = performance.now();
  const build = spawnSync('git', ['ls-tree', 'HEAD', '--', 'apps/demo-spa'], { cwd: root, encoding: 'utf8' }).stdout.split(/\s+/)[2]?.slice(0, 12);
  run('pnpm', ['perfgate', 'collect', '--url', base, '--pr-url', pr, '--runs', String(runs),
    '--mode', 'abab', '--throttling', 'devtools', '--warmup', '2', '--app', 'demo-heavy',
    '--app-build', build, '--label', name === 'aa' ? 'aa' : 'injected',
    '--experiment', `sitespeed-${process.env.GITHUB_RUN_ID ?? 'local'}-${name}-${repeat}`,
    '--out', `${out}/lighthouse.jsonl`]);
  times.lighthouse_seconds = (performance.now() - start) / 1000;
}
// Alternate which tool runs first. They never measure concurrently on the same runner.
const order = repeat % 2 ? [sitespeed, lighthouse] : [lighthouse, sitespeed];
for (const collect of order) collect();
const comparison = JSON.parse(await readFile(`${out}/compare.json`, 'utf8'));
if (!comparison.metrics || !comparison.raw) throw new Error('sitespeed compare plugin returned no result');
for (const side of ['baseline', 'current']) {
  const data = comparison.raw[side].browsertime;
  if (data.timestamps.length !== runs || data.errors?.flat().length || data.markedAsFailure) {
    throw new Error(`incomplete or failed sitespeed ${side} loads`);
  }
}
const loads = (await readFile(`${out}/lighthouse.jsonl`, 'utf8')).trim().split('\n').map(JSON.parse);
if (loads.length !== 2 * runs || loads.some(r => r.error || r.failedRequests > 0)) throw new Error('incomplete or failed Lighthouse loads');
const toolPackage = JSON.parse(await readFile(resolve(executable, '../../package.json'), 'utf8'));
await writeFile(`${out}/metadata.json`, JSON.stringify({
  case: name, repeat, runs, warmup_per_variant: 2, order: order.map(f => f.name),
  sitespeed_version: toolPackage.version, node: process.version, platform: process.platform,
  cpu: os.cpus()[0]?.model, github_run: process.env.GITHUB_RUN_ID ?? null,
  chrome: loads[0].env.chromeVersion, app_build: loads[0].appBuild,
  measured_at: new Date().toISOString(), ...times,
}, null, 2) + '\n');
