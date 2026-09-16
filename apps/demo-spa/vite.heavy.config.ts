import { resolve } from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Built separately into the same dist, with its own assets directory, so the two pages
// share no chunks and stay independent experiment subjects.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: false,
    assetsDir: "assets-heavy",
    rollupOptions: {
      input: resolve(import.meta.dirname, "heavy.html"),
    },
  },
});
