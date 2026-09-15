import { execFileSync } from "node:child_process";
import os from "node:os";

import type { Env } from "./schema.js";

export function collectEnv(): Omit<Env, "chromeVersion" | "lighthouseVersion"> {
  const cpus = os.cpus();
  const e = process.env;
  return {
    nodeVersion: process.version,
    platform: os.platform(),
    osRelease: os.release(),
    arch: os.arch(),
    cpuModel: cpus[0]?.model.trim() ?? "unknown",
    cpuCount: cpus.length,
    totalMemMb: Math.round(os.totalmem() / 2 ** 20),
    ci: e.CI === "true",
    // set on GitHub-hosted runners
    runnerImage: e.ImageOS && e.ImageVersion ? `${e.ImageOS}-${e.ImageVersion}` : null,
    runnerName: e.RUNNER_NAME ?? null,
  };
}

export function gitSha(): string | null {
  if (process.env.GITHUB_SHA) return process.env.GITHUB_SHA;
  try {
    return execFileSync("git", ["rev-parse", "HEAD"], { stdio: ["ignore", "pipe", "ignore"] })
      .toString()
      .trim();
  } catch {
    return null;
  }
}
