import { describe, expect, it } from "vitest";

import { extractChromeVersion, extractError, extractMetrics, parseInject, type LhrLike } from "../src/extract.js";

const lhr: LhrLike = {
  lighthouseVersion: "12.0.0",
  environment: {
    hostUserAgent: "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/140.0.7339.80 Safari/537.36",
    benchmarkIndex: 2500,
  },
  audits: {
    "largest-contentful-paint": { numericValue: 1234.5 },
    "first-contentful-paint": { numericValue: 800 },
    "total-blocking-time": { numericValue: 0 },
    "cumulative-layout-shift": { numericValue: 0.02 },
    "speed-index": { numericValue: 900 },
    "server-response-time": {},
  },
};

describe("extractMetrics", () => {
  it("maps audits to metrics and keeps missing values as null", () => {
    expect(extractMetrics(lhr)).toEqual({ lcp: 1234.5, fcp: 800, tbt: 0, cls: 0.02, si: 900, ttfb: null });
  });

  it("treats non-finite values as missing", () => {
    expect(extractMetrics({ audits: { "total-blocking-time": { numericValue: Number.NaN } } }).tbt).toBeNull();
  });
});

describe("extractChromeVersion", () => {
  it("reads headless chrome version from user agent", () => {
    expect(extractChromeVersion(lhr)).toBe("140.0.7339.80");
  });
});

describe("extractError", () => {
  it("returns null without runtime error", () => {
    expect(extractError(lhr)).toBeNull();
  });

  it("joins code and message", () => {
    expect(extractError({ audits: {}, runtimeError: { code: "NO_FCP", message: "no paint" } })).toBe("NO_FCP: no paint");
  });
});

describe("parseInject", () => {
  it("returns null for clean urls", () => {
    expect(parseInject("http://localhost:4173/")).toBeNull();
  });

  it("parses type and size", () => {
    expect(parseInject("http://localhost:4173/?inject=script-delay:200")).toEqual({ type: "script-delay", size: 200 });
  });

  it("rejects malformed values", () => {
    expect(() => parseInject("http://localhost/?inject=script-delay")).toThrow();
    expect(() => parseInject("http://localhost/?inject=long-task:abc")).toThrow();
  });
});
