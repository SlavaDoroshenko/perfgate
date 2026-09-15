// Regressions of known size, switched on by `?inject=type:size`, so base and PR
// are the same build and differ only in the url.
export const INJECT_TYPES = [
  "script-delay", // blocking JS before the first render, ms → FCP/LCP
  "long-task", // blocking JS right after the first frame, ms → TBT
  "layout-shift", // banner of `size` px inserted above content → CLS
  "lcp-delay", // hero image src assigned after `size` ms → LCP
] as const;

export type InjectType = (typeof INJECT_TYPES)[number];

export interface Inject {
  type: InjectType;
  size: number;
}

export function parseInject(search: string): Inject | null {
  const raw = new URLSearchParams(search).get("inject");
  if (!raw) return null;
  const [type, size] = raw.split(":");
  const n = Number(size);
  if (!INJECT_TYPES.includes(type as InjectType) || size === undefined || !Number.isFinite(n) || n < 0) {
    throw new Error(`bad inject param "${raw}"`);
  }
  return { type: type as InjectType, size: n };
}

export function busyWait(ms: number): void {
  const end = performance.now() + ms;
  while (performance.now() < end) {
    // intentionally blocking the main thread
  }
}
