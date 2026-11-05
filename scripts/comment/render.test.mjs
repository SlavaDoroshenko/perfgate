import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtemp, mkdir, readFile, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { escapeText, loadReports, marker, overallStatus, parseComparison, renderComment } from './render.mjs';

const fixture = async name => JSON.parse(await readFile(new URL(`./fixtures/${name}.json`, import.meta.url), 'utf8'));
const SHA = '0123456789abcdef0123456789abcdef01234567';

async function reportTree(layout) {
  const root = await mkdtemp(join(tmpdir(), 'perfgate-comment-'));
  for (const [path, content] of Object.entries(layout)) {
    await mkdir(join(root, path, '..'), { recursive: true });
    await writeFile(join(root, path), typeof content === 'string' ? content : JSON.stringify(content));
  }
  return root;
}

test('fixtures produced by perfgate_analysis.compare validate', async () => {
  assert.equal(parseComparison(await fixture('aa')).status, 'no_regression_detected');
  const regression = parseComparison(await fixture('regression'));
  assert.equal(regression.status, 'regression');
  assert.deepEqual(regression.metrics.map(m => m.regression), [true, false, false, false]);
  assert.equal(parseComparison(await fixture('broken')).issues.length, 1);
});

test('inconsistent or malformed reports are rejected, not rendered', async () => {
  const aa = await fixture('aa');
  const regression = await fixture('regression');
  assert.throws(() => parseComparison({ ...aa, status: 'regression' }), /without a regressed metric/);
  assert.throws(() => parseComparison({ ...regression, status: 'no_regression_detected' }), /inconsistent/);
  assert.throws(() => parseComparison({ ...aa, metrics: [] }), /inconsistent/);
  assert.throws(() => parseComparison({ ...aa, issues: ['x'] }), /issues/);
  assert.throws(() => parseComparison({ ...aa, status: 'pass' }), /unknown status/);
  assert.throws(() => parseComparison({ ...aa, metrics: [{ ...aa.metrics[0], p: 'tiny' }] }), /finite/);
  assert.throws(() => parseComparison({ ...aa, metrics: [{ ...aa.metrics[0], p: 2 }] }), /outside/);
  assert.throws(() => parseComparison({ ...aa, metrics: [{ ...aa.metrics[0], unit: 's' }] }), /unit/);
  assert.throws(() => parseComparison([]), /object/);
});

test('overall status: any regression wins, any invalid or missing report is inconclusive', () => {
  const quiet = { comparison: { status: 'no_regression_detected' } };
  assert.equal(overallStatus([quiet]), 'no_regression_detected');
  assert.equal(overallStatus([quiet, { comparison: null, error: 'x' }]), 'inconclusive');
  assert.equal(overallStatus([quiet, { comparison: { status: 'invalid' } }]), 'inconclusive');
  assert.equal(overallStatus([{ comparison: { status: 'invalid' } }, { comparison: { status: 'regression' } }]), 'regression');
  assert.equal(overallStatus([]), 'inconclusive');
});

test('comment shows verdict, effects, intervals and links, worst comparison first', async () => {
  const root = await reportTree({
    'perfgate-aa-1/comparison.json': await fixture('aa'),
    'perfgate-pr-1/comparison.json': await fixture('regression'),
    'perfgate-pr-1/execution.json': { total_seconds: 321.4 },
  });
  const reports = await loadReports(root);
  const { status, body } = renderComment(reports, {
    key: 'web', runUrl: 'https://github.com/o/r/actions/runs/7', sha: SHA,
    artifactLinks: { 'perfgate-pr-1': 'https://github.com/o/r/actions/runs/7/artifacts/9' },
  });
  assert.equal(status, 'regression');
  assert.ok(body.startsWith('<!-- perfgate-comment:web -->\n'));
  assert.match(body, /### perfgate: Performance regression detected/);
  assert.match(body, /commit `0123456`/);
  assert.match(body, /\[measurement run\]\(https:\/\/github.com\/o\/r\/actions\/runs\/7\)/);
  assert.match(body, /\[report artifact\]\(https:\/\/github.com\/o\/r\/actions\/runs\/7\/artifacts\/9\)/);
  assert.match(body, /\| demo\\-heavy · FCP \| 1000 ms \| 1100 ms \| \+100 ms \(\+10\.0%\) \| \[\+99\.0 ms, \+102 ms\] \| <0\.0001 \| \*\*regression\*\* \|/);
  assert.match(body, /TBT \| 0\.0 ms \| 0\.0 ms \| 0\.0 ms \(zero base\)/);
  assert.match(body, /321 s measurement/);
  assert.match(body, /not proof that performance is unchanged/);
  assert.ok(body.indexOf('perfgate\\-pr\\-1') < body.indexOf('perfgate\\-aa\\-1'), 'regression listed first');
});

test('quiet, invalid and missing reports are distinguished', async () => {
  const quiet = await loadReports(await reportTree({ 'a/comparison.json': await fixture('aa') }));
  assert.match(renderComment(quiet).body, /### perfgate: No regression detected/);
  const invalid = await loadReports(await reportTree({ 'a/comparison.json': await fixture('broken') }));
  const invalidBody = renderComment(invalid).body;
  assert.match(invalidBody, /Inconclusive/);
  assert.match(invalidBody, /Measurement issues \(1\); no verdict was computed/);
  assert.match(invalidBody, /failed audit or network request/);
  const crashed = await loadReports(await reportTree({ 'a/execution.json': { total_seconds: 3 } }));
  assert.match(renderComment(crashed).body, /comparison\\\.json missing/);
  assert.match(renderComment([]).body, /produced no perfgate report/);
  const garbage = await loadReports(await reportTree({ 'a/comparison.json': '{not json' }));
  assert.equal(renderComment(garbage).status, 'inconclusive');
  assert.match(renderComment(garbage).body, /unreadable comparison\\\.json/);
});

test('untrusted text cannot inject markup, mentions or table cells', async () => {
  const evil = await fixture('regression');
  evil.metrics[0].name = '@octocat <img src=x onerror=alert(1)> | [x](javascript:alert(1))\n### fake/fcp';
  evil.issues = [];
  const root = await reportTree({ 'perfgate-x/comparison.json': evil });
  const { body } = renderComment(await loadReports(root), { runUrl: 'javascript:alert(1)' });
  assert.ok(!body.includes('<img'));
  assert.ok(!body.includes('@octocat'));
  assert.ok(!body.includes('](javascript'));
  assert.ok(!body.includes('\n### fake'));
  assert.ok(!body.includes('measurement run'), 'non-https run URL is dropped');
  const row = body.split('\n').find(line => line.includes('octocat'));
  assert.equal(row.split(/(?<!\\)\|/).length, 9, 'one table row with seven cells');
  assert.equal(escapeText('a'.repeat(500), 10).length, 10);
});

test('policy names outside the expected alphabet are not echoed', async () => {
  const odd = { ...(await fixture('aa')), policy: '`rm -rf`' };
  const { body } = renderComment(await loadReports(await reportTree({ 'a/comparison.json': odd })));
  assert.match(body, /policy unrecognized/);
});

test('compare-refs layout: refs.json beside comparison/ is reported', async () => {
  const refs = { base: 'a'.repeat(40), pr: 'b'.repeat(40) };
  const root = await reportTree({ 'perfgate-refs/refs.json': refs, 'perfgate-refs/comparison/comparison.json': await fixture('aa') });
  const reports = await loadReports(root);
  assert.equal(reports.length, 1);
  assert.deepEqual(reports[0].refs, refs);
  assert.match(renderComment(reports).body, /base `aaaaaaa` → PR `bbbbbbb`/);
});

test('symbolic links and oversized files are not read', async () => {
  const outside = await reportTree({ 'secret/comparison.json': await fixture('regression') });
  const root = await reportTree({ 'a/comparison.json': await fixture('aa'), 'big/comparison.json': ' '.repeat(1024 * 1024 + 1) });
  await symlink(join(outside, 'secret'), join(root, 'link'));
  await symlink(join(outside, 'secret', 'comparison.json'), join(root, 'a', 'execution.json'));
  const reports = await loadReports(root);
  assert.deepEqual(reports.map(r => r.path), ['a', 'big']);
  assert.match(reports[1].error, /too large/);
  assert.equal(reports[0].seconds, null);
});

test('comment length is bounded and keeps the sticky marker', async () => {
  const reports = await loadReports(await reportTree({ 'a/comparison.json': await fixture('regression') }));
  const { body } = renderComment(reports, { maxLength: 900 });
  assert.ok(body.length <= 900);
  assert.ok(body.startsWith(marker()));
  assert.match(body, /comment truncated/);
});

test('marker keys are restricted', () => {
  assert.equal(marker('web-1'), '<!-- perfgate-comment:web-1 -->');
  assert.throws(() => marker('a -->'), /comment key/);
});

test('render command writes the comment without network access', async () => {
  const root = await reportTree({ 'a/comparison.json': await fixture('aa') });
  const out = join(root, 'comment.md');
  const cli = new URL('./cli.mjs', import.meta.url).pathname;
  const result = spawnSync(process.execPath, [cli, 'render', '--reports', root, '--out', out, '--sha', SHA], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stderr, /no_regression_detected, 1 report/);
  assert.match(await readFile(out, 'utf8'), /No regression detected/);
  const skipped = spawnSync(process.execPath, [cli, 'github', '--reports', root], {
    encoding: 'utf8', env: { ...process.env, GITHUB_EVENT_PATH: join(root, 'event.json') },
  });
  assert.equal(skipped.status, 1, 'missing event file is an error');
});
