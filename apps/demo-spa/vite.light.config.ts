import { resolve } from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The light page is built on its own, so that editing the heavy page can never change
// its bundle (a shared chunk would add a request and shift the metrics).
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: resolve(import.meta.dirname, "index.html"),
    },
  },
});
