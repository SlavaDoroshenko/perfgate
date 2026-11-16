import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtemp, mkdir, readFile, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { escapeText, loadReports, marker, overallStatus, parseAssets, parseComparison, renderComment } from './render.mjs';

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
  assert.ok(!body.includes('measurement run'), 'non-http(s) run URL is dropped');
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

test('without assets.json the comment has no assets section', async () => {
  const reports = await loadReports(await reportTree({ 'a/comparison.json': await fixture('aa') }));
  assert.equal(reports[0].assets, null);
  assert.ok(!renderComment(reports).body.includes('Built assets'));
});

test('assets.json beside the report adds totals and differing files', async () => {
  const root = await reportTree({ 'a/comparison.json': await fixture('aa'), 'a/assets.json': await fixture('assets') });
  const { status, body } = renderComment(await loadReports(root));
  assert.equal(status, 'no_regression_detected', 'assets do not change the verdict');
  assert.ok(body.includes('**Built assets** (gzip; base → PR): 1 changed, 1 added, 1 removed, 3 unchanged.'));
  assert.ok(body.includes('| JS | 3 → 3 | 3.1 kB | 56.7 kB | +53.5 kB (+1701.3%) | +70.7 kB |'));
  assert.ok(body.includes('| **All** | 5 → 5 |'));
  assert.ok(!body.includes('| Images |'), 'types absent on both sides are omitted');
  assert.ok(body.includes('| assets/dom\\-\\[hash\\]\\.js | changed | 3.1 kB | 56.6 kB | +53.5 kB | +70.7 kB |'));
  assert.ok(body.includes('| assets/old\\.js | removed | 22 B | — | −22 B | −2 B |'));
  assert.ok(!body.includes('<details><summary>Differing files'), 'short lists are not collapsed');
  assert.match(body, /Built assets compare the two build outputs/);
});

test('compare-refs layout: assets.json beside refs.json is found', async () => {
  const root = await reportTree({ 'r/assets.json': await fixture('assets'), 'r/comparison/comparison.json': await fixture('aa') });
  const [report] = await loadReports(root);
  assert.equal(report.assets.counts.changed, 1);
});

test('identical builds render as one line; long lists are collapsed', async () => {
  const assets = await fixture('assets');
  const same = { ...assets, counts: { unchanged: 5, changed: 0, added: 0, removed: 0 }, files: [] };
  const quiet = renderComment(await loadReports(await reportTree({ 'a/comparison.json': await fixture('aa'), 'a/assets.json': same }))).body;
  assert.ok(quiet.includes('**Built assets:** no differences in 5 files (56.8 kB gzip).'));
  const many = { ...assets, files: Array.from({ length: 12 }, (_, i) => ({ ...assets.files[0], name: `chunk-${i}.js` })), files_truncated: 3 };
  const body = renderComment(await loadReports(await reportTree({ 'a/comparison.json': await fixture('aa'), 'a/assets.json': many }))).body;
  assert.ok(body.includes('<details><summary>Differing files: top 10 of 15 by gzip change</summary>'));
  assert.ok(body.includes('5 more differing files are in assets.json.'));
  assert.ok(body.includes('chunk\\-9\\.js') && !body.includes('chunk\\-10'));
});

test('hostile asset names cannot inject markup, mentions or table cells', async () => {
  const assets = await fixture('assets');
  assets.files[0].name = '@octocat <img src=x onerror=alert(1)> | [x](javascript:alert(1))\n### fake</details>.js';
  const root = await reportTree({ 'a/comparison.json': await fixture('aa'), 'a/assets.json': assets });
  const { body } = renderComment(await loadReports(root));
  assert.ok(!body.includes('<img'));
  assert.ok(!body.includes('@octocat'));
  assert.ok(!body.includes('](javascript'));
  assert.ok(!body.includes('\n### fake'));
  assert.ok(!body.includes('fake</details>'));
  const row = body.split('\n').find(line => line.includes('octocat'));
  assert.equal(row.split(/(?<!\\)\|/).length, 8, 'one table row with six cells');
});

test('malformed assets.json is reported without hiding the verdict', async () => {
  const assets = await fixture('assets');
  assert.throws(() => parseAssets({ ...assets, schema: 'x' }), /schema/);
  assert.throws(() => parseAssets({ ...assets, counts: { ...assets.counts, added: -1 } }), /non-negative/);
  assert.throws(() => parseAssets({ ...assets, files: [{ ...assets.files[0], status: 'added' }] }), /sides/);
  assert.throws(() => parseAssets({ ...assets, files: [{ ...assets.files[0], type: 'all' }] }), /invalid/);
  const fractional = { ...assets.totals, js: { base: assets.totals.js.base, pr: { files: 1, raw: 1.5, gzip: 1 } } };
  assert.throws(() => parseAssets({ ...assets, totals: fractional }), /integer/);
  const root = await reportTree({ 'a/comparison.json': await fixture('regression'), 'a/assets.json': '{"schema":1}' });
  const { status, body } = renderComment(await loadReports(root));
  assert.equal(status, 'regression');
  assert.ok(body.includes('Built assets: unreadable assets\\.json \\(assets\\: unknown schema\\)'));
});

test('render command can diff two build directories itself', async () => {
  const root = await reportTree({
    'rep/comparison.json': await fixture('aa'),
    'base/assets/index-Ab12Cd34.js': 'x', 'pr/assets/index-Zz99Yy88.js': 'xy',
  });
  const cli = new URL('./cli.mjs', import.meta.url).pathname;
  const result = spawnSync(process.execPath, [cli, 'render', '--reports', join(root, 'rep'),
    '--base-dist', join(root, 'base'), '--pr-dist', join(root, 'pr')], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  assert.ok(result.stdout.includes('| assets/index\\-\\[hash\\]\\.js | changed | 21 B | 22 B | +1 B | +1 B |'), result.stdout);
  const half = spawnSync(process.execPath, [cli, 'render', '--reports', root, '--base-dist', root], { encoding: 'utf8' });
  assert.equal(half.status, 1);
});

test('plain http links of internal GitLab instances are kept', async () => {
  const root = await reportTree({ 'web/comparison/comparison.json': await fixture('regression') });
  const { body } = renderComment(await loadReports(root), {
    runUrl: 'http://gitlab.internal/g/app/-/jobs/5',
    artifactLinks: { web: 'http://gitlab.internal/g/app/-/jobs/5/artifacts/browse/perfgate' },
  });
  assert.match(body, /\[measurement run\]\(http:\/\/gitlab\.internal\/g\/app\/-\/jobs\/5\)/);
  assert.match(body, /\[report artifact\]\(http:\/\/gitlab\.internal\/g\/app\/-\/jobs\/5\/artifacts\/browse\/perfgate\)/);
  const { body: other } = renderComment(await loadReports(root), { runUrl: 'ftp://gitlab.internal/x' });
  assert.ok(!other.includes('measurement run'));
});
