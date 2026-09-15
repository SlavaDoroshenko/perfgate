import { describe, expect, it } from "vitest";

import { Run, SCHEMA_VERSION } from "../src/schema.js";

const valid = {
  schemaVersion: SCHEMA_VERSION,
  experimentId: "exp-1",
  app: "demo-spa",
  variant: "base",
  url: "http://localhost:4173/",
  inject: null,
  mode: "abab",
  throttling: "simulate",
  runIndex: 0,
  order: 0,
  metrics: { lcp: 1000, fcp: 800, tbt: 0, cls: 0, si: 900, ttfb: 5 },
  benchmarkIndex: 2500,
  error: null,
  env: {
    chromeVersion: "140.0.0.0",
    lighthouseVersion: "12.0.0",
    nodeVersion: "v22.0.0",
    platform: "linux",
    osRelease: "6.8.0",
    arch: "x64",
    cpuModel: "AMD EPYC 7763",
    cpuCount: 4,
    totalMemMb: 16000,
    ci: true,
    runnerImage: "ubuntu24-20260901.1",
    runnerName: "GitHub Actions 12",
  },
  gitSha: "abc123",
  timestamp: "2026-09-16T10:00:00.000Z",
};

describe("Run schema", () => {
  it("accepts a complete run", () => {
    expect(Run.safeParse(valid).success).toBe(true);
  });

  it("rejects unknown variant", () => {
    expect(Run.safeParse({ ...valid, variant: "aa" }).success).toBe(false);
  });

  it("rejects non-ISO timestamp", () => {
    expect(Run.safeParse({ ...valid, timestamp: "yesterday" }).success).toBe(false);
  });
});
