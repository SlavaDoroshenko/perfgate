import { describe, expect, it } from "vitest";

import { busyWait, parseInject } from "../src/inject";

describe("parseInject", () => {
  it("returns null without the param", () => {
    expect(parseInject("")).toBeNull();
    expect(parseInject("?foo=1")).toBeNull();
  });

  it.each([
    ["?inject=script-delay:200", { type: "script-delay", size: 200 }],
    ["?inject=long-task:150", { type: "long-task", size: 150 }],
    ["?inject=layout-shift:120", { type: "layout-shift", size: 120 }],
    ["?inject=lcp-delay:500", { type: "lcp-delay", size: 500 }],
  ])("parses %s", (search, expected) => {
    expect(parseInject(search)).toEqual(expected);
  });

  it.each(["?inject=unknown:1", "?inject=long-task", "?inject=long-task:x", "?inject=long-task:-5"])(
    "rejects %s",
    (search) => {
      expect(() => parseInject(search)).toThrow();
    },
  );
});

describe("busyWait", () => {
  it("blocks for at least the given time", () => {
    const start = performance.now();
    busyWait(20);
    expect(performance.now() - start).toBeGreaterThanOrEqual(20);
  });
});
