import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev server and preview only. Production builds go through vite.light.config.ts and
// vite.heavy.config.ts, which build each page separately.
export default defineConfig({
  plugins: [react()],
});
