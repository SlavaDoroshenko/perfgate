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
declare module "vendor:zod" {
  // zod 3 and zod 4 have incompatible types; the workload only builds and parses
  export const z: any;
}
declare module "vendor:vue-compile" {
  export function createApp(options: Record<string, unknown>): { mount(selector: string): unknown };
}
declare module "vendor:vue-reactive" {
  export function createApp(options: Record<string, unknown>): { mount(selector: string): unknown };
  export function reactive<T extends object>(value: T): T;
  export function computed<T>(getter: () => T): { readonly value: T };
  export function h(type: string, propsOrChildren?: unknown, children?: unknown): unknown;
}
declare module "vendor:immer" {
  export function produce<T>(base: T, recipe: (draft: T) => void): T;
}
declare module "vendor:yaml" {
  export function parse(src: string, options?: Record<string, unknown>): unknown;
}
declare module "vendor:luxon" {
  interface DateTime {
    toISO(): string | null;
    toISODate(): string | null;
    toISOTime(): string | null;
    toSQLDate(): string | null;
  }
  export const DateTime: { fromMillis(ms: number, options?: { zone?: string }): DateTime };
}
declare module "vendor:jquery" {
  interface JQuery {
    append(...content: unknown[]): JQuery;
    text(value: string): JQuery;
    data(key: string, value: unknown): JQuery;
    toggleClass(name: string, state?: boolean): JQuery;
    on(event: string, handler: (this: HTMLElement) => void): JQuery;
    find(selector: string): JQuery;
    css(name: string, value: string): JQuery;
  }
  const $: (selector: string | HTMLElement) => JQuery;
  export default $;
}
declare module "vendor:purify" {
  const DOMPurify: { sanitize(dirty: string): unknown };
  export default DOMPurify;
}
