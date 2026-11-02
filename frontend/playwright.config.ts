import { defineConfig } from "@playwright/test";

// Runs against an already-running, seeded stack:
//   backend: python -m app.seed demo  (optionally `use-mock-ai` first) then uvicorn
//   E2E_BASE_URL defaults to the backend serving the built UI on :8000.
export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  retries: 0,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8000",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
    launchOptions: process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : undefined,
  },
});
