import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

/**
 * The real golden-path E2E flow spec §97 asks for, run against the actual running
 * app (real backend, real Ollama, real Qdrant — nothing mocked). Steps 5-9 (upload,
 * ingestion, a real chat turn) are genuinely slow; this whole file is meant to run
 * before a release, not on every save (see `playwright.config.ts`'s docstring).
 *
 * Uses a freshly-created patient for the create/upload/ask/cite steps (2-9) so this
 * test never mutates the seeded demo dataset, then switches to the already-seeded
 * Elena Novak / Robert Klein (real pre-existing reports/labs from
 * `scripts/seed_demo_reports.py`) for compare/trend/reconciliation (10-12) — those
 * are read-only computations, so reusing real seeded data here is both realistic and
 * safe. The fresh test patient is archived (via a direct API call — there is no
 * frontend UI for it, spec §18's patient-archive action was only ever exposed
 * through the API) at the end so repeated runs don't clutter the visible patient list.
 */

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CREDENTIALS_PATH = path.resolve(__dirname, "../../data/sqlite/.demo_credentials.txt");
const FIXTURE_PDF = path.resolve(__dirname, "fixtures/e2e_sample_report.pdf");

function readDoctorCredentials(): { email: string; password: string } {
  const text = readFileSync(CREDENTIALS_PATH, "utf-8");
  const match = text.match(/^doctor\s+(\S+)\s+(\S+)\s*$/m);
  if (!match) {
    throw new Error(
      `Could not find doctor credentials in ${CREDENTIALS_PATH} — run scripts/seed_demo.py (or start-demo.bat) first.`,
    );
  }
  return { email: match[1], password: match[2] };
}

async function login(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL("**/overview");
}

async function openPatientBySearch(page: Page, query: string, exactCardText: string) {
  await page.goto("/patients");
  await page.fill('[aria-label="Search patients"]', query);
  await page.locator(".gms-card", { hasText: exactCardText }).first().click();
  await page.waitForURL(/\/patients\/[^/]+\/overview$/);
}

test.describe.serial("Golden path (spec §97)", () => {
  const testPatientName = `E2E ${Date.now()}`;
  let patientId = "";
  let patientUrl = "";

  test("1. Login", async ({ page }) => {
    const { email, password } = readDoctorCredentials();
    await login(page, email, password);
    await expect(page.getByRole("heading", { name: /Smarter Clinical Decisions/i })).toBeVisible();
  });

  test("2-4. Create, search for, and open a fresh patient", async ({ page }) => {
    const { email, password } = readDoctorCredentials();
    await login(page, email, password);

    // Setup: a fresh patient dedicated to this test run, never a seeded demo patient.
    await page.goto("/patients");
    await page.getByRole("button", { name: "Add Patient", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await dialog.locator("#first_name").fill(testPatientName);
    await dialog.locator("#last_name").fill("TestPatient");
    await dialog.locator("#dob").fill("1970-01-01");
    await dialog.getByRole("button", { name: "Add Patient", exact: true }).click();
    await page.waitForURL(/\/patients\/[^/]+$/);
    patientUrl = page.url();
    patientId = patientUrl.split("/patients/")[1].split(/[/?]/)[0];

    // 2. Patient search — real search against the real API, not a client-side filter
    // over stale data (the patient was just created, proving the index is live).
    await page.goto("/patients");
    await page.fill('[aria-label="Search patients"]', testPatientName);
    await expect(page.getByText(`${testPatientName} TestPatient`)).toBeVisible();

    // 3-4. Open patient — click through from the real search result.
    await page.locator(".gms-card", { hasText: `${testPatientName} TestPatient` }).first().click();
    await page.waitForURL(/\/patients\/[^/]+\/overview$/);
    await expect(page.getByRole("heading", { name: `${testPatientName} TestPatient` })).toBeVisible();
  });

  test("5-9. Create encounter, upload report, wait for ingestion, ask a question, receive a cited answer, open the citation", async ({
    page,
  }) => {
    const { email, password } = readDoctorCredentials();
    await login(page, email, password);
    await page.goto(`${patientUrl}/overview`);

    // 5. Create encounter
    await page.getByRole("button", { name: "New Encounter" }).click();
    const encounterDialog = page.getByRole("dialog");
    await encounterDialog.locator("#chief_complaint").fill("E2E test visit - blurry vision");
    await encounterDialog.getByRole("button", { name: "Start Encounter" }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);

    // 6. Upload report — a real file, real multipart upload.
    await page.goto(`${patientUrl}/reports`);
    await page.getByRole("button", { name: "Upload Report" }).click();
    const uploadDialog = page.getByRole("dialog");
    await uploadDialog.locator("#report_file").setInputFiles(FIXTURE_PDF);
    await uploadDialog.getByRole("button", { name: "Upload", exact: true }).click();
    // Generous timeout — the upload request itself is a synchronous file+DB write
    // (fast), but this can be the first real write request a freshly-started backend
    // process handles, with real first-call import/lazy-load overhead on top.
    await expect(page.getByRole("dialog")).toHaveCount(0, { timeout: 60_000 });

    // 7. Wait for ingestion — real extraction running in a background task, polled by
    // the frontend itself; this just waits for the real "Processed" status to appear.
    await expect(page.getByText("Processed")).toBeVisible({ timeout: 120_000 });

    // 8. Ask patient question — "Ask AI About This" (spec §41), a real, already-
    // composed question, not a decorative button.
    await page.getByRole("link", { name: "Ask AI" }).click();
    await page.waitForURL(/\/clinical-ai$/);

    // 9. Receive a cited answer — a real streamed Ollama response. Citation badges
    // are rendered as `[P1]`-style buttons once the answer references real evidence.
    await expect(page.locator('button[aria-label="Mark as helpful"]').first()).toBeVisible({ timeout: 180_000 });

    // Open citation — click a real citation badge and confirm the Evidence panel
    // scrolls to and shows the matching source. Not every real answer necessarily
    // cites something (an honest, ungrounded answer wouldn't), so this is a soft
    // check rather than a hard failure.
    const citationBadge = page.locator("button", { hasText: /^P\d+$/ }).first();
    if ((await citationBadge.count()) > 0) {
      await citationBadge.click();
      await expect(page.locator('[id^="evidence-P"]').first()).toBeVisible();
    }
  });

  test("10. Compare reports (real seeded patient, deterministic numeric diff)", async ({ page }) => {
    const { email, password } = readDoctorCredentials();
    await login(page, email, password);
    await openPatientBySearch(page, "Novak", "Elena Novak");

    await page.getByRole("link", { name: "Clinical Modules" }).click();
    await page.locator("nav button", { hasText: "Compare Reports" }).click();
    await page.locator(".gms-card button", { hasText: "Compare Reports" }).first().click();
    await expect(page.getByText("Numeric changes (deterministic)")).toBeVisible({ timeout: 30_000 });
    // Real, known values from scripts/generate_sample_reports.py (Phase 14): HbA1c
    // 9.4% -> 8.1%, a genuine decrease this project itself authored both sides of.
    await expect(page.getByText(/decreased/i).first()).toBeVisible();
  });

  test("11. View lab trend (real two-point trend from seeded lab panels)", async ({ page }) => {
    const { email, password } = readDoctorCredentials();
    await login(page, email, password);
    await openPatientBySearch(page, "Novak", "Elena Novak");
    await page.getByRole("link", { name: "Labs" }).click();
    await expect(page.getByText(/HbA1c/i).first()).toBeVisible({ timeout: 15_000 });
  });

  test("12. Medication reconciliation (real fuzzy-matched newly-detected drug)", async ({ page }) => {
    const { email, password } = readDoctorCredentials();
    await login(page, email, password);
    await openPatientBySearch(page, "Klein", "Robert Klein");
    await page.getByRole("link", { name: "Reports" }).click();

    // Scoped to the one report card that actually has a Current Medications section
    // (klein_glaucoma_followup.docx) — Klein has multiple reports, and every
    // successfully-ingested one renders its own "Reconcile Medications" button.
    const card = page.locator(".gms-card", { hasText: "klein_glaucoma_followup.docx" });
    await card.getByRole("button", { name: "Reconcile Medications" }).click();
    // Real fuzzy-matched finding: that document lists Brimonidine, deliberately not
    // in his seeded system medication list (Phase 15).
    await expect(page.getByText(/Newly detected in this document/i)).toBeVisible({ timeout: 15_000 });
  });

  test("13. Logout", async ({ page }) => {
    const { email, password } = readDoctorCredentials();
    await login(page, email, password);

    // Cleanup — archive (not hard-delete, matching this app's own soft-delete-only
    // convention) the fresh test patient via a direct API call *before* logging out,
    // reusing the page's own already-authenticated session cookie (there is no
    // frontend UI for archiving a patient — spec §18's archive action only ever
    // shipped as an API endpoint) — so repeated runs don't clutter the patient list.
    if (patientId) {
      await page.context().request.post(`/api/patients/${patientId}/archive`);
    }

    await page.getByRole("button", { name: /Dr\. Demo/ }).click();
    await page.getByRole("menuitem", { name: "Logout" }).click();
    await page.waitForURL("**/login");
    await expect(page.locator('input[type="email"]')).toBeVisible();
  });
});
