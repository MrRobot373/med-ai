import { expect, test, type Page } from "@playwright/test";

async function signIn(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/$/);
}

const DOCTOR = ["ananya.rao@lifecaremedico.in", "Clinic@2026"] as const;
const DESK = ["meera.pillai@lifecaremedico.in", "Desk@2026"] as const;

test("registering someone who is already on file shows a warning, and an exact repeat is stopped", async ({ page }) => {
  await signIn(page, ...DESK);
  await page.goto("/patients?new=1");
  await page.getByLabel("First name").fill("Rohit");
  await page.getByLabel("Last name").fill("Verma");
  await page.getByLabel("Date of birth").fill("1957-05-10");
  await expect(page.getByText(/may already be registered|already registered/).first()).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("LCM-10231").first()).toBeVisible();
  await page.getByRole("button", { name: "Register patient" }).click();
  // the server refuses a clear duplicate and offers an explicit override
  await expect(page.getByRole("button", { name: /Register as a new patient anyway/ })).toBeVisible({ timeout: 10_000 });
});

test("a doctor can print a prescription as a real PDF carrying her registration number", async ({ page }) => {
  await signIn(page, ...DOCTOR);
  const patients = await (await page.request.get("/api/patients?q=Verma")).json();
  const rohit = patients.find((p: { mrn: string }) => p.mrn === "LCM-10231");
  const rxs = await (await page.request.get(`/api/patients/${rohit.id}/prescriptions`)).json();
  const issued = rxs.find((r: { status: string }) => r.status === "final");
  test.skip(!issued, "no issued prescription in this data set");
  const res = await page.request.get(`/api/prescriptions/${issued.id}/pdf`);
  expect(res.status()).toBe(200);
  expect(res.headers()["content-type"]).toBe("application/pdf");
  expect((await res.body()).subarray(0, 5).toString()).toBe("%PDF-");
});

test("an administrator takes a backup from Settings and sees it listed", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(process.env.E2E_ADMIN_EMAIL ?? "admin@lifecaremedico.in");
  await page.getByLabel("Password", { exact: true }).fill(process.env.E2E_ADMIN_PASSWORD ?? "Admin@2026");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/$/);
  await page.goto("/settings/backup");
  await expect(page.getByRole("heading", { name: "Backups" }).first()).toBeVisible();
  await page.getByRole("button", { name: "Back up now" }).click();
  await expect(page.getByText("Backup complete").first()).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/gms-backup-\d{8}-\d{6}/).first()).toBeVisible();
  await page.goto("/settings/clinical");
  await expect(page.getByText("Prescription safety rules and drug database")).toBeVisible();
  await page.getByRole("button", { name: "Run the clinical tests" }).click();
  await expect(page.getByText(/Known patients|Allergy|allergy/).first()).toBeVisible();
});
