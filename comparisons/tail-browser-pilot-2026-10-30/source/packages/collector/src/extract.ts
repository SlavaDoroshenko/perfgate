import type { Inject, Metrics } from "./schema.js";

// Minimal slice of the Lighthouse result (LHR) we depend on.
export interface LhrLike {
  lighthouseVersion?: string;
  runtimeError?: { code?: string; message?: string };
  runWarnings?: string[];
  environment?: { hostUserAgent?: string; benchmarkIndex?: number };
  audits: Record<
    string,
    { numericValue?: number; details?: { items?: { statusCode?: number; url?: string }[] } } | undefined
  >;
}

const AUDITS: Record<keyof Metrics, string> = {
  lcp: "largest-contentful-paint",
  fcp: "first-contentful-paint",
  tbt: "total-blocking-time",
  cls: "cumulative-layout-shift",
  si: "speed-index",
  ttfb: "server-response-time",
};

export function extractMetrics(lhr: LhrLike): Metrics {
  const pick = (id: string) => {
    const v = lhr.audits[id]?.numericValue;
    return typeof v === "number" && Number.isFinite(v) ? v : null;
  };
  return {
    lcp: pick(AUDITS.lcp),
    fcp: pick(AUDITS.fcp),
    tbt: pick(AUDITS.tbt),
    cls: pick(AUDITS.cls),
    si: pick(AUDITS.si),
    ttfb: pick(AUDITS.ttfb),
  };
}

export function extractChromeVersion(lhr: LhrLike): string | null {
  const ua = lhr.environment?.hostUserAgent ?? "";
  return ua.match(/(?:Headless)?Chrome\/([\d.]+)/)?.[1] ?? null;
}

export function extractError(lhr: LhrLike): string | null {
  if (!lhr.runtimeError) return null;
  return [lhr.runtimeError.code, lhr.runtimeError.message].filter(Boolean).join(": ");
}

/**
 * Requests the page failed to load. A page whose script 404s still produces metrics,
 * so without this a broken build measures as a fast one.
 */
export function extractFailedRequests(lhr: LhrLike): number | null {
  const items = lhr.audits["network-requests"]?.details?.items;
  if (!items) return null;
  return items.filter(
    (r) =>
      typeof r.statusCode === "number" &&
      r.statusCode >= 400 &&
      // the browser asks for a favicon on its own; a missing one is not a broken page
      !(r.url ?? "").endsWith("/favicon.ico"),
  ).length;
}

/** Parses `?inject=type:size`, e.g. `script-delay:200`. */
export function parseInject(url: string): Inject | null {
  const raw = new URL(url).searchParams.get("inject");
  if (!raw) return null;
  const [type, size] = raw.split(":");
  const n = Number(size);
  if (!type || size === undefined || !Number.isFinite(n)) {
    throw new Error(`bad inject param "${raw}", expected type:number`);
  }
  return { type, size: n };
}
