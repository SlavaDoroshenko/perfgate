import type { Mode, Variant } from "./schema.js";

export interface Slot {
  variant: Variant;
  runIndex: number;
  order: number;
}

/**
 * Order of page loads in a series.
 * sequential: all base runs, then all pr runs.
 * abab: base and pr interleaved, so slow drift of the machine hits both variants equally.
 * Without a pr url only base runs are planned.
 */
export function planRuns(runs: number, mode: Mode, hasPr: boolean): Slot[] {
  if (!Number.isInteger(runs) || runs < 1) {
    throw new Error(`runs must be a positive integer, got ${runs}`);
  }
  const variants: Variant[] = hasPr ? ["base", "pr"] : ["base"];
  const slots: Omit<Slot, "order">[] = [];

  if (mode === "sequential" || !hasPr) {
    for (const variant of variants) {
      for (let i = 0; i < runs; i++) slots.push({ variant, runIndex: i });
    }
  } else {
    for (let i = 0; i < runs; i++) {
      for (const variant of variants) slots.push({ variant, runIndex: i });
    }
  }

  return slots.map((s, order) => ({ ...s, order }));
}
