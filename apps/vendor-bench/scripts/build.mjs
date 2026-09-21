// Builds the same pages twice: once against the older library versions ("a"),
// once against the newer ones ("b"). The two dist trees are served side by side,
// so a measurement compares two real releases of somebody else's code.
import { resolve } from "node:path";

import { build } from "vite";

const root = resolve(import.meta.dirname, "..");

for (const variant of ["a", "b"]) {
  process.env.VENDOR_VARIANT = variant;
  await build({
    root,
    configFile: resolve(root, "vite.config.ts"),
    logLevel: "warn",
    build: { outDir: resolve(root, "dist", variant), emptyOutDir: true },
  });
  process.stdout.write(`vendor-bench: built variant ${variant}\n`);
}
