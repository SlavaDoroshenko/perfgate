import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtemp, mkdir, readFile, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { gzipSync } from 'node:zlib';
import { assetType, diffAssets, looksLikeHash, looseKey, stripHash } from './diff.mjs';

async function tree(layout) {
  const root = await mkdtemp(join(tmpdir(), 'perfgate-assets-'));
  for (const [path, content] of Object.entries(layout)) {
    await mkdir(join(root, path, '..'), { recursive: true });
    await writeFile(join(root, path), content);
  }
  return root;
}
const noise = (n, seed = 1) => Buffer.from(Array.from({ length: n }, (_, i) => (i * 7919 + seed * 104729) % 251));
const byName = result => Object.fromEntries(result.files.map(f => [f.name, f]));

test('content hashes of common bundlers are stripped', () => {
  const cases = {
    'assets/index-BmXy3_aZ.js': 'assets/index-[hash].js', // Vite/Rollup, base64url
    'assets/index-D-3xY_ab.js': 'assets/index-[hash].js', // hash containing -
    'assets/Inter-Bold-C3xY8kAa.woff2': 'assets/Inter-Bold-[hash].woff2',
    'chunk-ABCDEFGH.js': 'chunk-[hash].js', // esbuild, base32
    'main.3f2a1b9c.chunk.js': 'main.[hash].chunk.js', // webpack/CRA
    'static/js/2.a1b2c3d4.chunk.js': 'static/js/2.[hash].chunk.js',
    'app.3f2a1b9c4d5e6f708192.css': 'app.[hash].css',
    '3f2a1b9c4d5e6f70.js': '[hash].js', // [contenthash].js
    '_next/static/chunks/pages/index-a1b2c3d4e5f6a7b8.js': '_next/static/chunks/pages/index-[hash].js',
    '_next/static/Xk3jH-aB9cD_eFgHiJkLm/_buildManifest.js': '_next/static/[hash]/_buildManifest.js',
  };
  for (const [path, name] of Object.entries(cases)) assert.equal(stripHash(path).name, name, path);
  assert.deepEqual(stripHash('assets/index-BmXy3_aZ.js').hashes, ['BmXy3_aZ']);
});

test('names that merely look long are kept', () => {
  for (const path of ['index.html', 'CHANGELOG.md', 'lazy-my-route.js', 'my-fallback.js', 'vendor-myWidget.js',
    'logo.deadbeef.svg', 'polyfills-es2015.js', 'fonts/inter-latin-400-normal.woff2', 'robots.txt', 'LICENSE']) {
    assert.equal(stripHash(path).name, path, path);
  }
  assert.equal(looksLikeHash('abcdefgh'), false);
  assert.equal(looksLikeHash('ABCDEFGH'), false);
  assert.equal(looksLikeHash('ABCDEFGH', { suffix: true }), true);
  assert.equal(looksLikeHash('a1b2c3d4'), true);
  assert.equal(looksLikeHash('a1b2c3d'), false, 'too short');
  assert.equal(looseKey('assets/lazy-abcdefgh.js'), 'assets/lazy-*.js');
});

test('asset types', () => {
  assert.deepEqual(['a.mjs', 'b.CSS', 'c.webp', 'd.woff2', 'e.html', 'f'].map(assetType), ['js', 'css', 'img', 'font', 'other', 'other']);
});

test('sides are matched by hash-free name; sizes and gzip totals add up', async () => {
  const dom = noise(5000, 2);
  const base = await tree({
    'index.html': '<script src="/assets/index-Xy12ab3Z.js"></script>',
    'assets/index-Xy12ab3Z.js': 'import "./dom-Ab12Cd34.js";',
    'assets/dom-Ab12Cd34.js': noise(1000),
    'assets/style-AAbb1122.css': 'body{color:red}',
    'assets/logo-Qw12Er34.svg': '<svg/>',
    'assets/old.js': 'old',
    'assets/index-Xy12ab3Z.js.map': '{}',
  });
  const pr = await tree({
    'index.html': '<script src="/assets/index-Pq98zy7W.js"></script>',
    'assets/index-Pq98zy7W.js': 'import "./dom-Zz99Yy88.js";',
    'assets/dom-Zz99Yy88.js': dom,
    'assets/style-CCdd3344.css': 'body{color:red}',
    'assets/logo-Qw12Er34.svg': '<svg/>',
    'assets/new.woff2': 'font',
  });
  const result = await diffAssets(base, pr);
  assert.deepEqual(result.counts, { unchanged: 4, changed: 1, added: 1, removed: 1 });
  assert.deepEqual(result.skipped, { base: 1, pr: 0 });
  const files = byName(result);
  assert.equal(result.files[0].name, 'assets/dom-[hash].js', 'largest gzip change first');
  assert.deepEqual(Object.keys(files).sort(), ['assets/dom-[hash].js', 'assets/new.woff2', 'assets/old.js']);
  const changed = files['assets/dom-[hash].js'];
  assert.equal(changed.status, 'changed');
  assert.equal(changed.pr.raw, 5000);
  assert.equal(changed.pr.gzip, gzipSync(dom, { level: 9 }).length);
  assert.deepEqual(changed.pr.paths, ['assets/dom-Zz99Yy88.js']);
  assert.equal(files['assets/old.js'].pr, null);
  assert.equal(files['assets/new.woff2'].base, null);
  // index.html and index-*.js differ only in the hashes they reference: unchanged.
  assert.ok(!files['index.html'] && !files['assets/index-[hash].js']);
  assert.equal(result.totals.js.pr.raw, Buffer.byteLength('import "./dom-Zz99Yy88.js";') + 5000);
  assert.equal(result.totals.font.pr.files, 1);
  assert.equal(result.totals.font.base.files, 0);
  const all = result.totals.all;
  for (const k of ['files', 'raw', 'gzip']) {
    assert.equal(all.pr[k], ['js', 'css', 'img', 'font', 'other'].reduce((a, t) => a + result.totals[t].pr[k], 0));
  }
});

test('byte-identical builds with different hashes are unchanged', async () => {
  const base = await tree({ 'a/index-Ab12Cd34.js': 'x', 'a/x.3f2a1b9c.css': 'y', 'img.png': noise(300) });
  const pr = await tree({ 'a/index-Zz99Yy88.js': 'x', 'a/x.0e9d8c7b.css': 'y', 'img.png': noise(300) });
  const result = await diffAssets(base, pr);
  assert.deepEqual(result.counts, { unchanged: 3, changed: 0, added: 0, removed: 0 });
  assert.deepEqual(result.files, []);
});

test('several files with one normalized name: identical pairs first, the rest as a group', async () => {
  const base = await tree({ 'index-Aa11Bb22.js': 'one', 'index-Cc33Dd44.js': 'two', 'index-Ee55Ff66.js': 'three' });
  const pr = await tree({ 'index-Gg77Hh88.js': 'one', 'index-Ii99Jj00.js': 'two!', 'index-Kk11Ll22.js': 'three!', 'index-Mm33Nn44.js': 'four' });
  const result = await diffAssets(base, pr);
  assert.deepEqual(result.counts, { unchanged: 1, changed: 1, added: 0, removed: 0 });
  const [group] = result.files;
  assert.equal(group.name, 'index-[hash].js');
  assert.deepEqual([group.base.files, group.pr.files], [2, 3]);
  assert.equal(group.pr.raw, 'two!three!four'.length);
});

test('word-like hashes are matched by the loose second pass', async () => {
  const base = await tree({ 'lazy-abcdefgh.js': 'a', 'settings.js': 's' });
  const pr = await tree({ 'lazy-qwertyui.js': 'ab', 'settings-page.js': 's' });
  const files = byName(await diffAssets(base, pr));
  assert.equal(files['lazy-*.js'].status, 'changed');
  assert.equal(files['settings.js'].status, 'removed');
  assert.equal(files['settings-page.js'].status, 'added');
});

test('symbolic links are not followed', async () => {
  const outside = await tree({ 'secret.js': 'secret' });
  const base = await tree({ 'a.js': 'a' });
  const pr = await tree({ 'a.js': 'a' });
  await symlink(join(outside, 'secret.js'), join(pr, 'b.js'));
  await symlink(outside, join(pr, 'dir'));
  const result = await diffAssets(base, pr);
  assert.equal(result.counts.added, 0);
  assert.equal(result.skipped.pr, 2);
});

test('command writes assets.json and fails on a missing directory', async () => {
  const base = await tree({ 'a.js': 'a' });
  const pr = await tree({ 'a.js': 'ab' });
  const out = join(pr, '..', `${Date.now()}-assets.json`);
  const cli = new URL('./diff.mjs', import.meta.url).pathname;
  const ok = spawnSync(process.execPath, [cli, '--base', base, '--pr', pr, '--out', out], { encoding: 'utf8' });
  assert.equal(ok.status, 0, ok.stderr);
  assert.match(ok.stderr, /1 changed, 0 added, 0 removed, 0 unchanged/);
  assert.equal(JSON.parse(await readFile(out, 'utf8')).schema, 'perfgate-assets/1');
  const missing = spawnSync(process.execPath, [cli, '--base', join(base, 'nope'), '--pr', pr], { encoding: 'utf8' });
  assert.equal(missing.status, 1);
});
