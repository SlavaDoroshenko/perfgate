import { describe, expect, it } from "vitest";

import { buildSeries, mulberry32, sparkline, summarize } from "../src/work";

describe("deterministic work", () => {
  it("produces the same series for the same seed", () => {
    expect(Array.from(buildSeries(5, 1))).toEqual(Array.from(buildSeries(5, 1)));
    expect(Array.from(buildSeries(5, 1))).not.toEqual(Array.from(buildSeries(5, 2)));
  });

  it("mulberry32 stays in [0, 1)", () => {
    const rnd = mulberry32(7);
    for (let i = 0; i < 100; i++) {
      const v = rnd();
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
    }
  });

  it("summarize returns ordered statistics", () => {
    const s = summarize(buildSeries(1000));
    expect(s.p95).toBeLessThanOrEqual(s.max);
    expect(s.buckets.reduce((a, b) => a + b, 0)).toBe(1000);
  });

  it("sparkline draws a path inside the box", () => {
    const path = sparkline(buildSeries(1000), 600, 120);
    expect(path.startsWith("M")).toBe(true);
    const ys = [...path.matchAll(/,(\d+\.\d)/g)].map((m) => Number(m[1]));
    expect(Math.max(...ys)).toBeLessThanOrEqual(120);
  });
});
