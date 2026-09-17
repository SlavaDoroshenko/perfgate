import { z } from "zod";

// One JSONL line = one measured page load. Bump SCHEMA_VERSION on breaking changes:
// the analysis side validates against schema/run.schema.json.
export const SCHEMA_VERSION = 1;

export const Variant = z.enum(["base", "pr"]);
export const Mode = z.enum(["sequential", "abab"]);
export const Throttling = z.enum(["simulate", "devtools", "none"]);

export const Inject = z.object({
  type: z.string(),
  size: z.number(),
});

// Lab metrics in milliseconds, except cls (unitless). null = audit did not produce a value.
export const Metrics = z.object({
  lcp: z.number().nullable(),
  fcp: z.number().nullable(),
  tbt: z.number().nullable(),
  cls: z.number().nullable(),
  si: z.number().nullable(),
  ttfb: z.number().nullable(),
});

export const Env = z.object({
  chromeVersion: z.string().nullable(),
  lighthouseVersion: z.string().nullable(),
  nodeVersion: z.string(),
  platform: z.string(),
  osRelease: z.string(),
  arch: z.string(),
  cpuModel: z.string(),
  cpuCount: z.number().int(),
  totalMemMb: z.number().int(),
  ci: z.boolean(),
  runnerImage: z.string().nullable(),
  runnerName: z.string().nullable(),
});

export const Run = z.object({
  schemaVersion: z.literal(SCHEMA_VERSION),
  experimentId: z.string(),
  app: z.string(),
  variant: Variant,
  url: z.string(),
  // injected regression parsed from the url `inject` query param; null for clean loads
  inject: Inject.nullable(),
  mode: Mode,
  throttling: Throttling,
  // unrecorded loads before the series; optional, absent in data collected before 2026-09-17
  warmup: z.number().int().nonnegative().optional(),
  runIndex: z.number().int().nonnegative(),
  // global position of this load within the series (0-based), for drift analysis
  order: z.number().int().nonnegative(),
  metrics: Metrics,
  benchmarkIndex: z.number().nullable(),
  error: z.string().nullable(),
  env: Env,
  gitSha: z.string().nullable(),
  timestamp: z.iso.datetime(),
});

export type Variant = z.infer<typeof Variant>;
export type Mode = z.infer<typeof Mode>;
export type Throttling = z.infer<typeof Throttling>;
export type Inject = z.infer<typeof Inject>;
export type Metrics = z.infer<typeof Metrics>;
export type Env = z.infer<typeof Env>;
export type Run = z.infer<typeof Run>;
