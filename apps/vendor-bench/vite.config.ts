import { resolve } from "node:path";

import { defineConfig, type Plugin } from "vite";

// Which npm alias each workload imports. Variant "a" is the older release, "b" the newer one:
// a real change written by a real team, which is what an upgrade in a PR looks like.
// The key is the workload (page) name; two workloads may share one installed release.
// `default` also re-exports the default export, for libraries that export nothing else.
const ALIASES: Record<string, { a: string; b: string; default?: true }> = {
  marked: { a: "marked-a", b: "marked-b" },
  chart: { a: "chart-a", b: "chart-b" },
  dates: { a: "dates-a", b: "dates-b" },
  zod: { a: "zod-a", b: "zod-b" },
  // the full build with the runtime template compiler: the workload is the 3.4 parser rewrite
  "vue-compile": { a: "vue-33/dist/vue.esm-bundler.js", b: "vue-34/dist/vue.esm-bundler.js" },
  // the runtime-only build: the workload is the 3.5 reactivity refactor
  "vue-reactive": { a: "vue-34", b: "vue-35" },
  immer: { a: "immer-a", b: "immer-b" },
  yaml: { a: "yaml-a", b: "yaml-b" },
  luxon: { a: "luxon-a", b: "luxon-b" },
  jquery: { a: "jquery-a", b: "jquery-b", default: true },
  purify: { a: "purify-a", b: "purify-b", default: true },
};

function vendor(variant: "a" | "b"): Plugin {
  return {
    name: "vendor-alias",
    transformIndexHtml() {
      return [{ tag: "link", attrs: { rel: "icon", href: "data:," }, injectTo: "head" }];
    },
    resolveId(id) {
      const lib = id.startsWith("vendor:") ? id.slice("vendor:".length) : null;
      return lib && ALIASES[lib] ? `\0vendor:${lib}` : null;
    },
    load(id) {
      const lib = id.startsWith("\0vendor:") ? id.slice("\0vendor:".length) : null;
      if (!lib || !ALIASES[lib]) return null;
      const target = ALIASES[lib][variant];
      const named = `export * from "${target}";`;
      return ALIASES[lib].default ? `${named}\nexport { default } from "${target}";` : named;
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
    // compile-time flags of Vue's esm-bundler builds: production values, same in both variants
    define: {
      __VUE_OPTIONS_API__: "true",
      __VUE_PROD_DEVTOOLS__: "false",
      __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: "false",
    },
    build: {
      rollupOptions: {
        input: Object.fromEntries(Object.keys(ALIASES).map((name) => [name, page(name)])),
      },
    },
  };
});
