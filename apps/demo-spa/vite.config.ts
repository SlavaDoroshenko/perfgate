import { resolve } from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        // light page: minimal main-thread work
        index: resolve(import.meta.dirname, "index.html"),
        // heavy page: large DOM + post-paint computation, so TBT and CLS are not degenerate
        heavy: resolve(import.meta.dirname, "heavy.html"),
      },
    },
  },
});
