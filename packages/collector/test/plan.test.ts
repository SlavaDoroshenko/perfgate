import { describe, expect, it } from "vitest";

import { planRuns } from "../src/plan.js";

const labels = (slots: ReturnType<typeof planRuns>) => slots.map((s) => `${s.variant[0]}${s.runIndex}`);

describe("planRuns", () => {
  it("sequential runs all base loads before pr", () => {
    expect(labels(planRuns(2, "sequential", true))).toEqual(["b0", "b1", "p0", "p1"]);
  });

  it("abab interleaves variants", () => {
    expect(labels(planRuns(3, "abab", true))).toEqual(["b0", "p0", "b1", "p1", "b2", "p2"]);
  });

  it("plans only base loads without a pr url", () => {
    expect(labels(planRuns(3, "abab", false))).toEqual(["b0", "b1", "b2"]);
  });

  it("numbers order globally", () => {
    expect(planRuns(2, "abab", true).map((s) => s.order)).toEqual([0, 1, 2, 3]);
  });

  it.each([0, -1, 1.5, Number.NaN])("rejects runs=%s", (n) => {
    expect(() => planRuns(n, "abab", true)).toThrow();
  });
});
