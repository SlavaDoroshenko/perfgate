import { execFileSync } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { expect, it } from "vitest";
import { compareRefs, RefConfig } from "../src/compare-refs.js";

it("requires argument arrays instead of shell command strings", () => {
  expect(RefConfig.safeParse({ start: "node server.js" }).success).toBe(false);
  expect(RefConfig.safeParse({ start: ["node", "server.js"] }).success).toBe(true);
});

it("removes its worktree after a build failure and keeps diagnostics", async () => {
  const root = resolve(import.meta.dirname, "../../..");
  const temp = await mkdtemp(resolve(tmpdir(), "perfgate-ref-test-"));
  const trees = () => execFileSync("git", ["-C", root, "worktree", "list", "--porcelain"], { encoding: "utf8" });
  const before = trees();
  try {
    const config = resolve(temp, "config.json");
    await writeFile(config, JSON.stringify({ build: [process.execPath, "-e", "process.exit(7)"], start: [process.execPath, "never.js"] }));
    await expect(compareRefs(["--repo", root, "--base-ref", "HEAD", "--pr-ref", "HEAD", "--config", config,
      "--out", resolve(temp, "result")])).rejects.toThrow("base build failed");
    expect(trees()).toBe(before);
    const metadata = JSON.parse(await readFile(resolve(temp, "result/refs.json"), "utf8"));
    expect(metadata.cleanup_issues).toEqual([]);
    expect(metadata.base).toBe(metadata.pr);
  } finally { await rm(temp, { recursive: true, force: true }); }
});
