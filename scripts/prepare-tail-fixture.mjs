import { readFile, writeFile } from 'node:fs/promises';
const root = new URL('../apps/demo-spa/dist/', import.meta.url);
const html = await readFile(new URL('heavy.html', root), 'utf8');
if (!html.includes('</body>')) throw new Error('Build demo-spa first');
await writeFile(new URL('tail-heavy.html', root), html.replace('</body>', '<script src="/tail-probe.js"></script></body>'), { flag: 'wx' });
await writeFile(new URL('tail-probe.js', root), await readFile(new URL('../experiments/rare-stalls/probe.js', import.meta.url)), { flag: 'wx' });
