#!/usr/bin/env node
import { appendFile, mkdir } from "node:fs/promises";
import { dirname } from "node:path";
import { parseArgs } from "node:util";

import { collectEnv, gitSha } from "./env.js";
import { extractChromeVersion, extractError, extractMetrics, parseInject } from "./extract.js";
import { measure } from "./lighthouse.js";
import { planRuns } from "./plan.js";
import { Mode, Run, SCHEMA_VERSION, Throttling } from "./schema.js";

const USAGE = `Usage: perfgate collect --url <base> [--pr-url <pr>] [options]

Options:
  --runs <n>           measured loads per variant (default 10)
  --mode <m>           sequential | abab (default abab)
  --throttling <t>     simulate | devtools | none (default simulate)
  --app <name>         app label stored with each run (default "app")
  --experiment <id>    experiment id (default: generated)
  --out <file>         JSONL file to append to (default results/runs.jsonl)
  --no-warmup          skip the unrecorded warm-up load per variant
`;

async function collect(argv: string[]) {
  const { values } = parseArgs({
    args: argv,
    options: {
      url: { type: "string" },
      "pr-url": { type: "string" },
      runs: { type: "string", default: "10" },
      mode: { type: "string", default: "abab" },
      throttling: { type: "string", default: "simulate" },
      app: { type: "string", default: "app" },
      experiment: { type: "string" },
      out: { type: "string", default: "results/runs.jsonl" },
      "no-warmup": { type: "boolean", default: false },
    },
    strict: true,
  });

  if (!values.url) throw new UsageError("--url is required");
  const mode = Mode.parse(values.mode);
  const throttling = Throttling.parse(values.throttling);
  const runs = Number(values.runs);
  const urls = { base: values.url, pr: values["pr-url"] };
  const experimentId =
    values.experiment ?? `${new Date().toISOString().replace(/[:.]/g, "-")}-${mode}-${throttling}`;

  const slots = planRuns(runs, mode, Boolean(urls.pr));
  const env = collectEnv();
  const sha = gitSha();
  await mkdir(dirname(values.out), { recursive: true });

  if (!values["no-warmup"]) {
    for (const url of [urls.base, urls.pr].filter((u): u is string => Boolean(u))) {
      log(`warm-up ${url}`);
      await measure(url, throttling).catch((err: unknown) => log(`warm-up failed: ${String(err)}`));
    }
  }

  let failed = 0;
  for (const slot of slots) {
    const url = slot.variant === "base" ? urls.base : urls.pr!;
    const timestamp = new Date().toISOString();
    let run: Run;
    try {
      const lhr = await measure(url, throttling);
      run = {
        schemaVersion: SCHEMA_VERSION,
        experimentId,
        app: values.app,
        variant: slot.variant,
        url,
        inject: parseInject(url),
        mode,
        throttling,
        runIndex: slot.runIndex,
        order: slot.order,
        metrics: extractMetrics(lhr),
        benchmarkIndex: lhr.environment?.benchmarkIndex ?? null,
        error: extractError(lhr),
        env: { ...env, chromeVersion: extractChromeVersion(lhr), lighthouseVersion: lhr.lighthouseVersion ?? null },
        gitSha: sha,
        timestamp,
      };
    } catch (err) {
      // a crashed load is still recorded, so failure rate is visible in the data
      run = {
        schemaVersion: SCHEMA_VERSION,
        experimentId,
        app: values.app,
        variant: slot.variant,
        url,
        inject: parseInject(url),
        mode,
        throttling,
        runIndex: slot.runIndex,
        order: slot.order,
        metrics: { lcp: null, fcp: null, tbt: null, cls: null, si: null, ttfb: null },
        benchmarkIndex: null,
        error: err instanceof Error ? err.message : String(err),
        env: { ...env, chromeVersion: null, lighthouseVersion: null },
        gitSha: sha,
        timestamp,
      };
    }
    if (run.error) failed++;
    await appendFile(values.out, JSON.stringify(Run.parse(run)) + "\n");
    const m = run.metrics;
    log(
      `[${slot.order + 1}/${slots.length}] ${slot.variant}#${slot.runIndex} ` +
        (run.error ? `ERROR ${run.error}` : `fcp=${fmt(m.fcp)} lcp=${fmt(m.lcp)} tbt=${fmt(m.tbt)} cls=${m.cls?.toFixed(3)}`),
    );
  }

  log(`done: ${slots.length} runs, ${failed} failed → ${values.out}`);
  if (failed === slots.length) process.exitCode = 1;
}

class UsageError extends Error {}

const fmt = (v: number | null) => (v === null ? "-" : `${Math.round(v)}ms`);
const log = (msg: string) => process.stderr.write(msg + "\n");

async function main() {
  const [command, ...rest] = process.argv.slice(2);
  try {
    if (command === "collect") return await collect(rest);
    if (command === undefined || command === "--help" || command === "-h") {
      process.stdout.write(USAGE);
      return;
    }
    throw new UsageError(`unknown command "${command}"`);
  } catch (err) {
    if (err instanceof UsageError) {
      log(`${err.message}\n\n${USAGE}`);
      process.exitCode = 2;
      return;
    }
    throw err;
  }
}

await main();
