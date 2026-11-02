// Reference screenshots of the pages the film uses (planning only).
import { chromium } from "/home/user/med-ai/frontend/node_modules/@playwright/test/index.mjs";
import { api, BASE, session } from "./lib.mjs";
const OUT = process.argv[2];
const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
const page = await session(browser, { email: "ananya.rao@lifecaremedico.in", password: "Clinic@2026" });
const all = await api(page, "GET", "/api/patients");
const id = (m) => all.find((p) => p.mrn === m).id;
const R = id("LCM-10231"), K = id("LCM-10238"), H = id("LCM-10232"), S = id("LCM-10245");
const pages = process.argv.slice(3).length ? process.argv.slice(3) : [
  `home:/`, `rohit:/patients/${R}`, `rohit-consult:/patients/${R}/consult`, `rohit-docs:/patients/${R}/documents`, `rohit-results:/patients/${R}/results`,
  `kavita:/patients/${K}`, `kavita-results:/patients/${K}/results`, `kavita-assistant:/patients/${K}/assistant`, `harish:/patients/${H}`, `harish-docs:/patients/${H}/documents`, `suresh-docs:/patients/${S}/documents`,
];
for (const p of pages) {
  const [name, url] = p.split(/:(.*)/s);
  await page.goto(`${BASE}${url}`); await page.waitForLoadState("networkidle").catch(() => {}); await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
}
console.log(JSON.stringify({ R, K, H, S }));
await browser.close();
