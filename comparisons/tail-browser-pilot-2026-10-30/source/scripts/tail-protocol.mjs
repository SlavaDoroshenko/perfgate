import { createHash } from 'node:crypto';
export function stallIndices(condition, runs, seed) {
  if (!['aa', 'rare', 'dense'].includes(condition) || !Number.isInteger(runs) || runs < 1 || !Number.isSafeInteger(seed)) {
    throw new Error('Invalid tail schedule');
  }
  const count = condition === 'aa' ? 0 : condition === 'dense' ? runs : Math.round(runs * 0.15);
  return Array.from({ length: runs }, (_, index) => ({ index, key: createHash('sha256').update(`${seed}:${index}`).digest('hex') }))
    .sort((a, b) => a.key.localeCompare(b.key)).slice(0, count).map(x => x.index).sort((a, b) => a - b);
}
export function stallEvidence(events, expected) {
  const marks = events.filter(e => e.cat?.includes('user_timing') && e.name.startsWith('perfgate-'));
  const named = name => marks.filter(e => e.name === name);
  const start = named('perfgate-stall-start'), end = named('perfgate-stall-end');
  const issues = [];
  for (const name of ['perfgate-tail-ready', 'perfgate-tail-done']) {
    if (named(name).length !== 1) issues.push(`Missing or duplicate ${name}`);
  }
  if (start.length !== Number(expected) || end.length !== Number(expected)) issues.push('Stall execution differs from schedule');
  const durationMs = start.length === 1 && end.length === 1 ? (end[0].ts - start[0].ts) / 1000 : null;
  if (durationMs !== null && durationMs < 0) issues.push('Negative stall duration');
  return { expected, durationMs, marks, issues };
}
