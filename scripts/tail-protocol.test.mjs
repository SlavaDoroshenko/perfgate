import test from 'node:test';
import assert from 'node:assert/strict';
import { stallIndices, stallEvidence } from './tail-protocol.mjs';
test('fixed sparse schedule has exactly three distinct positions and replays by seed', () => {
  const slots = stallIndices('rare', 20, 2026103001);
  assert.equal(slots.length, 3); assert.equal(new Set(slots).size, 3);
  assert.deepEqual(slots, stallIndices('rare', 20, 2026103001));
  assert.notDeepEqual(slots, stallIndices('rare', 20, 2026103002));
  assert.deepEqual(stallIndices('aa', 20, 1), []);
  assert.equal(stallIndices('dense', 20, 1).length, 20);
  assert.throws(() => stallIndices('typo', 20, 1));
});
const mark = (name, ts) => ({ name, ts, cat: 'blink.user_timing' });
const normal = [mark('perfgate-tail-ready', 0), mark('perfgate-tail-done', 1000000)];
test('missing probe or missing expected stall invalidates acquisition', () => {
  assert.ok(stallEvidence([], false).issues.length);
  assert.ok(stallEvidence(normal, true).issues.length);
  assert.deepEqual(stallEvidence(normal, false).issues, []);
});
test('trace timestamps establish actual duration, unexpected stalls are rejected', () => {
  const rows = [...normal, mark('perfgate-stall-start', 10000), mark('perfgate-stall-end', 810000)];
  assert.equal(stallEvidence(rows, true).durationMs, 800);
  assert.deepEqual(stallEvidence(rows, true).issues, []);
  assert.ok(stallEvidence(rows, false).issues.length);
});
