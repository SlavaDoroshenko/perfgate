export const INJECT_TYPES = ["script-delay", "long-task", "layout-shift", "lcp-delay"] as const;
export type InjectType = (typeof INJECT_TYPES)[number];
export interface Inject {
  type: InjectType;
  size: number;
}

export function parseInject(raw: string | string[] | undefined): Inject | null {
  if (typeof raw !== "string" || !raw) return null;
  const [type, size] = raw.split(":");
  const n = Number(size);
  if (!INJECT_TYPES.includes(type as InjectType) || size === undefined || !Number.isFinite(n) || n < 0) {
    throw new Error(`bad inject param "${raw}"`);
  }
  return { type: type as InjectType, size: n };
}
