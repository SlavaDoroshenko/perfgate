#!/usr/bin/env node
// Compares the built assets of two build output directories.
//
//   node scripts/assets/diff.mjs --base DIR --pr DIR [--out assets.json]
//
// Files are matched across sides by their path with content hashes stripped
// (`index-BmXy3_aZ.js`, `main.3f2a1b9c.chunk.js` -> `index-[hash].js`,
// `main.[hash].chunk.js`). A file whose bytes are equal, or equal once the hash
// tokens of both builds are masked, is unchanged. Sizes are raw and gzip level 9.
// Source maps and precompressed copies (.gz, .br) are skipped: browsers do not
// download them in a page load. Symbolic links are never followed.
import { createHash } from 'node:crypto';
import { lstat, readdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import { gzipSync } from 'node:zlib';

export const SCHEMA = 'perfgate-assets/1';
export const TYPES = ['js', 'css', 'img', 'font', 'other'];
const MAX_FILES = 20000;
const MAX_DEPTH = 32;
const MAX_ENTRIES = 1000; // keeps assets.json well below the renderer's 1 MB limit
const MAX_MASK_BYTES = 8 * 1024 * 1024;
const SKIPPED = /\.(map|gz|br)$/i;
const EXTENSIONS = {
  js: ['js', 'mjs', 'cjs'],
  css: ['css'],
  img: ['png', 'jpg', 'jpeg', 'gif', 'webp', 'avif', 'svg', 'ico', 'bmp'],
  font: ['woff', 'woff2', 'ttf', 'otf', 'eot'],
};
const TEXT = new Set(['js', 'mjs', 'cjs', 'css', 'html', 'htm', 'json', 'svg', 'txt', 'xml', 'webmanifest']);

export function assetType(path) {
  const ext = path.slice(path.lastIndexOf('.') + 1).toLowerCase();
  return TYPES.find(type => EXTENSIONS[type]?.includes(ext)) ?? 'other';
}

/**
 * Whether a name segment looks like a content hash rather than a word: hex with a
 * digit (webpack, Parcel, Next.js), or base64url/base32 with a digit or at least
 * two capitals (Rollup/Vite, esbuild). All-capital words count only after a
 * separator (`chunk-ABCDEFGH`), so `CHANGELOG.md` stays a name, as do `fallback`,
 * `myWidget` or `deadbeef`. A rare hash that looks like a word is matched by the
 * looser second pass in diffAssets.
 */
export function looksLikeHash(text, { suffix = false } = {}) {
  if (text.length < 8 || text.length > 64 || !/^[A-Za-z0-9_-]+$/.test(text)) return false;
  // - and _ occur in 8-character Rollup hashes; longer runs with them are names.
  if (/[-_]/.test(text) && text.length !== 8) return false;
  if (/^[0-9a-f]+$/i.test(text)) return /[0-9]/.test(text) || text.length >= 16;
  if (/[0-9]/.test(text)) return true;
  return (text.match(/[A-Z]/g)?.length ?? 0) >= 2 && (suffix || /[a-z]/.test(text));
}

// Next.js build ids: 21-character nanoids, which may contain - and _.
function isBuildId(dir) {
  return /^[A-Za-z0-9_-]{16,64}$/.test(dir) && /[0-9]/.test(dir) && /[a-z]/.test(dir) && /[A-Z]/.test(dir);
}

/**
 * Strips content hashes from one path. Returns the normalized path and the hash
 * tokens removed. Directory names that are hashes (Next.js build ids) become `[hash]`.
 */
export function stripHash(path) {
  const hashes = [];
  const segments = path.split('/');
  const base = segments.pop();
  const dirs = segments.map(dir => looksLikeHash(dir) || isBuildId(dir) ? (hashes.push(dir), '[hash]') : dir);
  const parts = base.split('.');
  const ext = parts.length > 1 ? parts.pop() : null;
  const kept = parts.map((part, i) => {
    if (i > 0 && looksLikeHash(part)) { hashes.push(part); return '[hash]'; }
    // `name-<hash>`: Rollup/Vite hashes are 8 base64url characters and may contain - or _.
    for (const pattern of [/^(.+)[-_~]([A-Za-z0-9_-]{8})$/, /^(.+)[-_~]([A-Za-z0-9]{9,64})$/]) {
      const match = pattern.exec(part);
      if (match && looksLikeHash(match[2], { suffix: true })) { hashes.push(match[2]); return `${match[1]}${part[match[1].length]}[hash]`; }
    }
    if (looksLikeHash(part)) { hashes.push(part); return '[hash]'; }
    return part;
  });
  if (ext !== null) kept.push(ext);
  return { name: [...dirs, kept.join('.')].join('/'), hashes };
}

/** Loose key for the second matching pass: an 8-character suffix, the default
 * Rollup/Vite hash length, is a wildcard (`lazy-abcdefgh.js` -> `lazy-*.js`). */
export function looseKey(name) {
  return name.replace(/([-_~.])[A-Za-z0-9_-]{8}(\.[^./]+)$/, '$1*$2');
}

async function walk(root) {
  const files = [];
  let skipped = 0;
  async function visit(dir, rel, depth) {
    if (depth > MAX_DEPTH) throw new Error(`${root}: directory tree deeper than ${MAX_DEPTH}`);
    const entries = await readdir(dir, { withFileTypes: true });
    for (const entry of entries.sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0))) {
      const path = rel ? `${rel}/${entry.name}` : entry.name;
      if (entry.isDirectory()) await visit(join(dir, entry.name), path, depth + 1);
      else if (!entry.isFile()) skipped++; // symbolic links, sockets
      else if (SKIPPED.test(entry.name)) skipped++;
      else {
        if (files.length >= MAX_FILES) throw new Error(`${root}: more than ${MAX_FILES} files`);
        files.push(path);
      }
    }
  }
  if (!(await lstat(root)).isDirectory()) throw new Error(`${root}: not a directory`);
  await visit(root, '', 0);
  return { files, skipped };
}

async function readSide(root) {
  const { files, skipped } = await walk(root);
  const out = [];
  for (const path of files) {
    const bytes = await readFile(join(root, path));
    const { name, hashes } = stripHash(path);
    out.push({
      path, name, hashes, bytes, type: assetType(path), raw: bytes.length,
      gzip: gzipSync(bytes, { level: 9 }).length,
      digest: createHash('sha256').update(bytes).digest('hex'),
    });
  }
  return { files: out, skipped };
}

function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Digest of a text file with every known hash token masked, so that a chunk
 * that only references renamed chunks compares equal. */
function maskedDigest(file, pattern) {
  if (!pattern || file.raw > MAX_MASK_BYTES || !TEXT.has(file.path.slice(file.path.lastIndexOf('.') + 1).toLowerCase())) return file.digest;
  return createHash('sha256').update(file.bytes.toString('latin1').replace(pattern, '[hash]'), 'latin1').digest('hex');
}

function sum(files) {
  return { files: files.length, raw: files.reduce((a, f) => a + f.raw, 0), gzip: files.reduce((a, f) => a + f.gzip, 0) };
}
function side(files) {
  return files.length ? { ...sum(files), paths: files.map(f => f.path) } : null;
}

/** Matches files of two sides that share a key. Returns matched entries and leftovers. */
function match(base, pr, keyOf) {
  const groups = new Map();
  for (const [index, list] of [base, pr].entries()) {
    for (const file of list) {
      const key = keyOf(file);
      if (!groups.has(key)) groups.set(key, [[], []]);
      groups.get(key)[index].push(file);
    }
  }
  const entries = [], left = [[], []];
  for (const [key, [b, p]] of groups) {
    if (!b.length || !p.length) { left[0].push(...b); left[1].push(...p); continue; }
    // Many-to-one (several `index-[hash].js`): pair identical files first, then
    // report what remains of the group as one entry.
    const unmatched = [...p];
    const residual = [];
    for (const file of b) {
      const twin = unmatched.findIndex(other => other.masked === file.masked);
      if (twin >= 0) {
        entries.push({ name: key, type: file.type, status: 'unchanged', base: side([file]), pr: side([unmatched[twin]]) });
        unmatched.splice(twin, 1);
      } else residual.push(file);
    }
    if (residual.length && unmatched.length) {
      entries.push({ name: key, type: residual[0].type, status: 'changed', base: side(residual), pr: side(unmatched) });
    } else { left[0].push(...residual); left[1].push(...unmatched); }
  }
  return { entries, left };
}

export async function diffAssets(baseDir, prDir) {
  const [base, pr] = await Promise.all([readSide(baseDir), readSide(prDir)]);
  const tokens = [...new Set([...base.files, ...pr.files].flatMap(f => f.hashes))].sort((a, b) => b.length - a.length);
  const pattern = tokens.length ? new RegExp(tokens.map(escapeRegExp).join('|'), 'g') : null;
  for (const file of [...base.files, ...pr.files]) file.masked = maskedDigest(file, pattern);

  const first = match(base.files, pr.files, f => f.name);
  const second = match(first.left[0], first.left[1], f => looseKey(f.name));
  const entries = [...first.entries, ...second.entries];
  for (const file of second.left[0]) entries.push({ name: file.name, type: file.type, status: 'removed', base: side([file]), pr: null });
  for (const file of second.left[1]) entries.push({ name: file.name, type: file.type, status: 'added', base: null, pr: side([file]) });

  const totals = {};
  for (const type of [...TYPES, 'all']) {
    const pick = list => list.filter(f => type === 'all' || f.type === type);
    totals[type] = { base: sum(pick(base.files)), pr: sum(pick(pr.files)) };
  }
  const gzipChange = e => (e.pr?.gzip ?? 0) - (e.base?.gzip ?? 0);
  const rawChange = e => (e.pr?.raw ?? 0) - (e.base?.raw ?? 0);
  const differing = entries.filter(e => e.status !== 'unchanged')
    .sort((a, b) => Math.abs(gzipChange(b)) - Math.abs(gzipChange(a)) || Math.abs(rawChange(b)) - Math.abs(rawChange(a)) || (a.name < b.name ? -1 : 1));
  const count = status => entries.filter(e => e.status === status).length;
  return {
    schema: SCHEMA,
    gzip_level: 9,
    skipped: { base: base.skipped, pr: pr.skipped },
    totals,
    counts: { unchanged: count('unchanged'), changed: count('changed'), added: count('added'), removed: count('removed') },
    files: differing.slice(0, MAX_ENTRIES),
    files_truncated: Math.max(0, differing.length - MAX_ENTRIES),
  };
}

async function main() {
  const { values } = parseArgs({ strict: true, options: { base: { type: 'string' }, pr: { type: 'string' }, out: { type: 'string' } } });
  if (!values.base || !values.pr) throw new Error('usage: diff.mjs --base <directory> --pr <directory> [--out assets.json]');
  const result = await diffAssets(values.base, values.pr);
  const json = `${JSON.stringify(result, null, 2)}\n`;
  if (values.out) await writeFile(values.out, json); else process.stdout.write(json);
  const { counts } = result;
  process.stderr.write(`perfgate assets: ${counts.changed} changed, ${counts.added} added, ${counts.removed} removed, ${counts.unchanged} unchanged\n`);
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) {
  main().catch(error => { process.stderr.write(`perfgate assets failed: ${error.message}\n`); process.exitCode = 1; });
}
