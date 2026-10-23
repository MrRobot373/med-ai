import { expect, test, type Page } from "@playwright/test";

async function signIn(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/$/);
}

test("clinician reviews a chart and asks an evidence-grounded question", async ({ page }) => {
  await signIn(page, "doctor@gms.local", "Doctor@12345");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(/Good (morning|afternoon|evening)/);

  await page.goto("/patients");
  await page.getByText("James Carter").first().click();
  await expect(page.getByText("DEMO-1001").first()).toBeVisible();
  await expect(page.getByText("Penicillin").first()).toBeVisible();

  await page.getByRole("link", { name: "Results", exact: true }).click();
  await expect(page.getByText("Creatinine").first()).toBeVisible();

  await page.getByRole("link", { name: "Assistant", exact: true }).last().click();
  await page.getByPlaceholder(/Ask about James Carter/).fill("How has kidney function changed?");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: /Why this answer/ }).first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("button", { name: "R", exact: true }).first()).toBeVisible();
});

test("a wrong-patient document is quarantined and surfaced in the inbox", async ({ page }) => {
  await signIn(page, "doctor@gms.local", "Doctor@12345");
  await page.goto("/inbox");
  const item = page.getByText("Possible wrong-patient document").first();
  await expect(item).toBeVisible();
  await item.click();
  await expect(page.getByText("This document may belong to another patient")).toBeVisible();
});

test("administrator can test the configured language model", async ({ page }) => {
  await signIn(page, "admin@gms.local", "Admin@12345");
  await page.goto("/settings/models");
  await page.getByRole("button", { name: "Test connection" }).click();
  await expect(page.getByText(/Connection (successful|failed)/)).toBeVisible({ timeout: 30_000 });
});

test("viewer accounts are read-only", async ({ page }) => {
  await signIn(page, "viewer@gms.local", "Viewer@12345");
  await page.goto("/patients");
  await expect(page.getByRole("button", { name: "Register patient" })).toHaveCount(0);
});
