import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

async function signIn(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/$/);
}

const PAGES = ["/", "/patients", "/inbox", "/assistant", "/settings/profile", "/settings/print", "/settings/clinical"];

test.setTimeout(240_000);
for (const theme of ["light", "dark"]) {
  test(`no serious accessibility violations (WCAG 2 A/AA) — ${theme} theme`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: theme as "light" | "dark" });
    await page.goto("/login");
    // the sign-in page itself
    let r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    const bad = (v: typeof r.violations) => v.filter((x) => x.impact === "serious" || x.impact === "critical");
    expect(bad(r.violations).map((v) => `${v.id} (${v.nodes.length}): ${v.help}`), "login").toEqual([]);

    await signIn(page, process.env.E2E_ADMIN_EMAIL ?? "admin@lifecaremedico.in", process.env.E2E_ADMIN_PASSWORD ?? "Admin@2026");
    const found: string[] = [];
    for (const path of PAGES) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
      for (const v of bad(r.violations)) found.push(`${path}: ${v.id} (${v.nodes.length}) ${v.help} e.g. ${v.nodes[0].target.join(" ")} :: ${v.nodes[0].html.slice(0, 160)} :: ${(v.nodes[0].any[0]?.message ?? "").slice(0, 200)}`);
    }
    expect(found).toEqual([]);
  });
}
