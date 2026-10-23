import { expect, test, type Page } from "@playwright/test";

async function signIn(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/$/);
}

test("doctor's prescription is checked live against the patient's allergies", async ({ page }) => {
  await signIn(page, "ananya.rao@gmsclinic.local", "Clinic@2026");
  await expect(page.getByText("Today's patients")).toBeVisible();
  await page.getByRole("link", { name: "Rohit Verma" }).first().click();
  await page.getByRole("link", { name: "Consultation", exact: true }).click();

  await expect(page.getByRole("button", { name: /^(Start|Complete) consultation$/ })).toBeVisible();
  const start = page.getByRole("button", { name: "Start consultation" });
  if (await start.isVisible()) await start.click();
  await expect(page.getByText("Consultation notes")).toBeVisible();

  await expect(page.getByText(/No prescription yet|Every line is checked/).first()).toBeVisible();
  const write = page.getByRole("button", { name: "Write prescription" });
  if (await write.isVisible()) await write.click();
  const med = page.getByPlaceholder(/Medicine — e.g./).last();
  await med.fill("Septran DS");
  await expect(page.getByText("Allergy: Sulfa drugs").first()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Stop & check").first()).toBeVisible();

  // Clean up: remove the line and complete so the test can run again.
  await page.getByRole("button", { name: "Remove", exact: true }).last().click();
  await page.waitForTimeout(1500);
  await page.getByRole("button", { name: "Complete consultation" }).click();
  await expect(page.getByText("Consultation completed")).toBeVisible();
});

test("front desk sees the day list and paperwork, never clinical content", async ({ page }) => {
  await signIn(page, "meera.pillai@gmsclinic.local", "Desk@2026");
  await expect(page.getByRole("heading", { name: "Today's list", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Assistant" })).toHaveCount(0);
  await page.getByRole("link", { name: "Rohit Verma" }).first().click();
  await expect(page.getByText("Upload a report")).toBeVisible();
  await expect(page.getByText("Filed documents")).toBeVisible();
  expect((await page.request.get(`/api${new URL(page.url()).pathname}/overview`)).status()).toBe(403);
  await page.goto("/assistant");
  await expect(page).toHaveURL(/\/$/);
});
