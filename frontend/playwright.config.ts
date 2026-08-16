import { defineConfig, devices } from "@playwright/test";

/**
 * Real end-to-end tests (spec §97) against the actual running app — real backend,
 * real Ollama, real Qdrant, no mocking. Several steps involve genuine LLM generation
 * and report ingestion, so this suite is intentionally slow (minutes, not seconds) —
 * it is meant to be run before a release, not on every save.
 *
 * Prerequisites: Qdrant + Ollama running, backend migrated/seeded (see README.md's
 * "Setup" and "Running" sections, or just run start-demo.bat first). This config's
 * `webServer` entries only start the two Node/Python HTTP servers themselves, with
 * `reuseExistingServer: true` so a manually-started backend/frontend (the normal case
 * during development) is used as-is rather than spawning a second copy.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 5 * 60 * 1000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command:
        "cd ../backend && .venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000",
      url: "http://localhost:8000/api/health",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:5173",
      reuseExistingServer: true,
      timeout: 30_000,
    },
  ],
});
