// The concrete package behind each of these is chosen at build time by vite.config.ts,
// so the workloads are typed loosely on purpose: the two versions differ in their types.
declare module "vendor:marked" {
  export const marked: { parse(src: string): string | Promise<string> };
}
declare module "vendor:chart" {
  export const Chart: {
    new (ctx: HTMLCanvasElement, config: unknown): { update(): void };
    register(...items: unknown[]): void;
  };
  export const registerables: unknown[];
}
declare module "vendor:dates" {
  export function format(date: Date | number, pattern: string): string;
  export function addDays(date: Date | number, amount: number): Date;
}
