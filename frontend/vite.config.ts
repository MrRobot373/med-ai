/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Backend runs on 8000 in dev (see backend/app/config/settings.py APP_PORT).
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    // Real, fast unit/component tests live in tests/ only — `e2e/` (added in Phase
    // 16, spec §97) holds Playwright specs meant for `npx playwright test`, not this
    // runner; without this exclude, vitest's default glob also matches `*.spec.ts`
    // there and tries (and fails) to run them as jsdom component tests.
    include: ["tests/**/*.{test,spec}.{ts,tsx}"],
  },
});
