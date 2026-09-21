import { resolve } from "node:path";

import { defineConfig, type Plugin } from "vite";

// Which npm alias each workload imports. Variant "a" is the older release, "b" the newer one:
// a real change written by a real team, which is what an upgrade in a PR looks like.
const ALIASES: Record<string, { a: string; b: string }> = {
  marked: { a: "marked-a", b: "marked-b" },
  chart: { a: "chart-a", b: "chart-b" },
  dates: { a: "dates-a", b: "dates-b" },
};

function vendor(variant: "a" | "b"): Plugin {
  return {
    name: "vendor-alias",
    resolveId(id) {
      const lib = id.startsWith("vendor:") ? id.slice("vendor:".length) : null;
      return lib && ALIASES[lib] ? `\0vendor:${lib}` : null;
    },
    load(id) {
      const lib = id.startsWith("\0vendor:") ? id.slice("\0vendor:".length) : null;
      if (!lib || !ALIASES[lib]) return null;
      return `export * from "${ALIASES[lib][variant]}";`;
    },
  };
}

export default defineConfig(() => {
  const variant = (process.env.VENDOR_VARIANT ?? "a") as "a" | "b";
  const page = (name: string) => resolve(import.meta.dirname, `${name}.html`);
  return {
    // relative asset urls: the two variants are served from /a/ and /b/, and absolute
    // "/assets/..." urls would 404 there — a broken page still measures, silently
    base: "./",
    plugins: [vendor(variant)],
    build: {
      rollupOptions: { input: { marked: page("marked"), chart: page("chart"), dates: page("dates") } },
    },
  };
});
