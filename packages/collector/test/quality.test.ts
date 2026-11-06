import { expect, it } from "vitest";
import { measurementIssues } from "../src/quality.js";
import type { Run } from "../src/schema.js";

const sample = { error: null, failedRequests: 0, metrics: { fcp: 10, lcp: 20, tbt: 0, cls: 0 } } as Run;
it("accepts zero metrics but rejects incomplete audits and missing network status", () => {
  expect(measurementIssues(sample)).toEqual([]);
  expect(measurementIssues({ ...sample, failedRequests: null })).toContain("network status unknown");
  expect(measurementIssues({ ...sample, metrics: { ...sample.metrics, lcp: null } })).toContain("invalid lcp");
});
it("marks an asset failure even when Lighthouse produced metrics", () => {
  expect(measurementIssues({ ...sample, failedRequests: 1 })).toContain("1 failed requests");
});
