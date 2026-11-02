// Captures every shot of the film from the running app.
//   node capture.mjs [shot ...]      (no names = all shots, in story order)
// Needs the app on APP_URL (default http://localhost:8011), freshly seeded with `python -m app.seed demo`.
// Shots build on each other (the consultation, then the prescription, then the order), so run
// them in order on a fresh seed.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "/home/user/med-ai/frontend/node_modules/@playwright/test/index.mjs";
import { api, BASE, session, Shot } from "./lib.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(HERE, "out");
const FILES = path.join(HERE, "..", "..", "patient-files");
const DOCTOR = { email: "ananya.rao@lifecaremedico.in", password: "Clinic@2026" };
const DESK = { email: "meera.pillai@lifecaremedico.in", password: "Desk@2026" };
const browser = await chromium.launch({ executablePath: process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });

const ids = {};
async function load(page) {
  if (!ids.rohit) {
    const all = await api(page, "GET", "/api/patients");
    const by = (mrn) => all.find((p) => p.mrn === mrn).id;
    Object.assign(ids, { rohit: by("LCM-10231"), harish: by("LCM-10232"), kavita: by("LCM-10238"), suresh: by("LCM-10245") });
  }
  return ids;
}
async function open(url, { wait = 1600 } = {}) {
  const page = await session(browser, DOCTOR);
  await load(page);
  await page.goto(`${BASE}${typeof url === "function" ? url(ids) : url}`);
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(wait);
  return page;
}
const card = (loc) => loc.locator("xpath=ancestor::*[contains(@class,'rounded-2xl') or contains(@class,'rounded-3xl')][1]");

const SHOTS = {
  // Off camera: the film is about decisions, so the misfiled report is taken out of Harish's chart.
  async prep() {
    const page = await session(browser, DOCTOR);
    await load(page);
    for (const d of await api(page, "GET", `/api/patients/${ids.harish}/documents`)) {
      if (d.identity_status === "mismatch") await api(page, "DELETE", `/api/documents/${d.id}`);
    }
    await page.context().close();
    return null;
  },

  // Dr. Rao signs in to Life Care Medico.
  async login() {
    const page = await session(browser, null);
    await page.goto(`${BASE}/login`);
    await page.waitForTimeout(1200);
    const s = new Shot(page, "login", OUT);
    await s.snap(0.7);
    await s.click("#email", { dur: 0.75 });
    await s.type(DOCTOR.email, { cps: 15 });
    s.hold(0.25);
    await s.click("#password", { dur: 0.45 });
    await s.type(DOCTOR.password, { cps: 10 });
    s.hold(0.3);
    s.mark("continue");
    await s.click(page.getByRole("button", { name: "Continue" }), { dur: 0.5, settle: 2200, waitFor: "text=Today's patients", after: 1.4 });
    return s.save();
  },

  // Her day on one screen: who is coming and what has changed for each.
  async dashboard() {
    const page = await open("/", { wait: 2200 });
    const s = new Shot(page, "dashboard", OUT);
    await s.snap(1.0);
    const list = card(page.getByText("Today's patients").first());
    await s.camera(list, { dur: 1.2, pad: 20 });
    s.hold(1.6);
    const name = page.getByRole("link", { name: "Rohit Verma" }).first();
    const row = name.locator("xpath=ancestor::*[.//a[contains(@href,'/consult')]][1]");
    await s.camera(row, { dur: 0.9, pad: 40 });
    await s.move(row, { dur: 0.8, dx: 0.62, dy: 0.7 });
    s.mark("rohit");
    s.hold(1.4);
    await s.camera("full", { dur: 0.6 });
    await s.click(name, { dur: 0.6, settle: 2200, waitFor: "text=Key areas of concern", after: 0.6 });
    return s.save();
  },

  // Rohit's chart: every report already read into scores, trends and the values that matter.
  async overview() {
    const page = await open((i) => `/patients/${i.rohit}`, { wait: 2600 });
    const s = new Shot(page, "overview", OUT);
    await s.snap(0.8);
    await s.camera(card(page.getByText("Glycaemic control").first()), { dur: 1.1, pad: 24 });
    s.hold(2.0);
    await s.camera({ x: 1085 / 1.25, y: 380 / 1.25, w: 890 / 1.25, h: 150 / 1.25 }, { dur: 0.9, pad: 24 });
    s.hold(2.0);
    const concern = card(page.getByText("Key areas of concern").first());
    await s.camera(concern, { dur: 0.9, pad: 24 });
    await s.move(page.getByText("Creatinine", { exact: true }).first(), { dur: 0.7 });
    s.hold(1.8);
    await s.camera("full", { dur: 0.8 });
    s.hold(0.3);
    await s.click(page.getByText("View full report").first(), { dur: 0.7, settle: 2600, after: 0.5 });
    const viewer = page.locator("img[alt]").filter({ hasNot: page.locator("xpath=ancestor::button") }).first();
    await s.camera(viewer, { dur: 1.1, pad: 12 });
    s.hold(2.6);
    return s.save();
  },

  // Before the patient walks in: what happened last time, what changed, what to ask.
  async brief() {
    const page = await open((i) => `/patients/${i.rohit}/consult`, { wait: 2000 });
    const s = new Shot(page, "brief", OUT);
    await s.snap(0.8);
    const before = card(page.getByText("Before you see the patient").first());
    await s.camera(before, { dur: 1.1, pad: 16 });
    s.hold(1.4);
    await s.camera(card(page.getByText("Results since then").first()), { dur: 0.9, pad: 28 });
    s.hold(2.2);
    await s.camera(before, { dur: 0.8, pad: 16 });
    await s.click(page.getByRole("button", { name: "Prepare brief" }), { dur: 0.8, settle: 250, after: 0 });
    await s.watch(2.4, { every: 0.2 });
    await page.waitForTimeout(1500);
    await s.scroll(page.getByText("Ask about", { exact: true }).first(), { dur: 1.0, offset: 200 });
    await s.camera(card(page.getByText("Ask about", { exact: true }).first()), { dur: 0.9, pad: 16 });
    s.hold(3.2);
    return s.save();
  },

  // Notes, vitals, a diagnosis — and a second look at it against the whole history.
  async consult() {
    const page = await open((i) => `/patients/${i.rohit}/consult`, { wait: 2000 });
    const s = new Shot(page, "consult", OUT);
    await s.snap(0.6);
    await s.click(page.getByRole("button", { name: "Start consultation" }), { dur: 0.7, settle: 1800, waitFor: "text=Consultation notes", after: 0.4 });
    await s.scroll(page.getByText("Consultation notes").first(), { dur: 0.8, offset: 110 });
    await s.camera(card(page.getByText("Consultation notes").first()), { dur: 0.9, pad: 12 });
    await s.click(page.getByPlaceholder(/Onset, character/), { dur: 0.6, after: 0.1 });
    await s.type("Burning epigastric pain for 2 days, worse after meals and at night. No vomiting, no black stools.", { cps: 22 });
    s.hold(0.3);
    const vitals = [["120/80", "136/84"], ["76", "80"], ["98.6", "98.4"], ["98", "98"], ["70", "78"]];
    for (const [ph, v] of vitals) {
      await s.click(page.locator(`input[placeholder="${ph}"]`).first(), { dur: 0.35, after: 0.05 });
      await s.type(v, { cps: 14 });
    }
    s.hold(0.3);
    await s.click(page.getByPlaceholder("Findings"), { dur: 0.45, after: 0.05 });
    await s.type("Mild epigastric tenderness. No guarding. Murphy's sign negative.", { cps: 22 });
    await s.click(page.getByPlaceholder("e.g. Acute gastritis"), { dur: 0.5, after: 0.05 });
    await s.type("Acute gastritis", { cps: 14 });
    await s.press("Enter", { settle: 500, after: 0.6 });
    await s.camera("full", { dur: 0.7 });
    const check = page.getByRole("button", { name: "Check diagnosis" });
    await s.scroll(check, { dur: 0.9, offset: 420 });
    await s.click(check, { dur: 0.7, settle: 300, after: 0 });
    await s.watch(1.6, { every: 0.2 });
    await page.waitForTimeout(1500);
    await s.snap(0.2);
    const look = card(page.getByText("Diagnosis — second look").first());
    await s.scroll(page.getByText("Diagnosis — second look").first(), { dur: 0.8, offset: 120 });
    await s.camera(look, { dur: 0.9, pad: 12 });
    s.hold(3.4);
    return s.save();
  },

  // The prescription: every line checked as it is written.
  async rx() {
    const page = await open((i) => `/patients/${i.rohit}/consult`, { wait: 2200 });
    const s = new Shot(page, "rx", OUT);
    await s.snap(0.6);
    await s.click(page.getByRole("button", { name: "Write prescription" }), { dur: 0.8, settle: 1500, after: 0.3 });
    const rxCard = card(page.getByText("Every line is checked", { exact: false }).first());
    const checked = page.getByText("Checked against").first().locator("xpath=..");
    await s.camera(checked, { dur: 1.0, pad: 30 });
    s.mark("checked");
    s.hold(2.4);
    await s.camera(rxCard, { dur: 0.9, pad: 12 });
    const meds = [["Pan", "Pan-D"], ["Meftal", "Meftal-Spas"], ["Septran", "Septran DS"]];
    for (let i = 0; i < meds.length; i++) {
      const [q, pick] = meds[i];
      if (i > 0) await s.click(page.getByRole("button", { name: "Add medicine" }), { dur: 0.6, settle: 400, after: 0.1 });
      const input = page.getByPlaceholder(/Medicine — e.g./).last();
      await s.click(input, { dur: 0.45, after: 0.05 });
      await s.type(q, { cps: 11 });
      await page.waitForTimeout(700);
      await s.snap(0.35);
      const option = page.locator("button").filter({ hasText: new RegExp(`^${pick.replace(/[-]/g, "\\-")}\\s·`) }).first();
      await s.click(option, { dur: 0.45, settle: 2200, after: 0.3 });
      const row = input.locator("xpath=ancestor::*[.//button[@aria-label='Remove']][1]");
      await s.camera(row, { dur: 0.8, pad: 24 });
      s.mark(`med${i}`);
      s.hold(i === 2 ? 3.6 : 2.4);
      await s.camera(rxCard, { dur: 0.7, pad: 12 });
    }
    const review = page.getByRole("button", { name: "Review with clinical AI" });
    await s.scroll(review, { dur: 0.9, offset: 380 });
    await s.click(review, { dur: 0.6, settle: 300, after: 0 });
    await s.watch(1.4, { every: 0.2 });
    await page.waitForTimeout(1500);
    await s.snap(0.2);
    await s.camera(card(page.getByText("Clinical review").first()), { dur: 0.9, pad: 16 });
    s.hold(3.0);
    return s.save();
  },

  // Septran comes off; the prescription is finalised and printed on the clinic letterhead.
  async finalise() {
    const page = await open((i) => `/patients/${i.rohit}/consult`, { wait: 2200 });
    const s = new Shot(page, "finalise", OUT);
    const septran = page.getByPlaceholder(/Medicine — e.g./).last();
    await septran.scrollIntoViewIfNeeded();
    await page.evaluate(() => window.scrollBy(0, -160));
    await page.waitForTimeout(400);
    await s.snap(0.5);
    const remove = page.getByRole("button", { name: "Remove", exact: true }).last();
    await s.click(remove, { dur: 0.7, settle: 1800, after: 0.6 });
    const fin = page.getByRole("button", { name: "Finalise prescription" });
    await s.scroll(fin, { dur: 0.8, offset: 500 });
    await s.click(fin, { dur: 0.7, settle: 2000, after: 0.9 });
    return s.save();
  },

  async print() {
    const doc = await session(browser, DOCTOR);
    await load(doc);
    const rx = (await api(doc, "GET", `/api/patients/${ids.rohit}/prescriptions`)).find((r) => r.status === "final");
    await doc.goto(`${BASE}/print/prescription/${rx.id}`);
    await doc.waitForTimeout(2000);
    const s = new Shot(doc, "print", OUT);
    await s.snap(4.0);
    return s.save({ fullHeight: await doc.evaluate(() => document.body.scrollHeight) });
  },

  // An ultrasound is ordered with the question it should answer.
  async order() {
    const page = await open((i) => `/patients/${i.rohit}/consult`, { wait: 2200 });
    const s = new Shot(page, "order", OUT);
    const inv = page.getByText("Investigations").first();
    await inv.scrollIntoViewIfNeeded();
    await page.evaluate(() => window.scrollBy(0, -120));
    await page.waitForTimeout(400);
    await s.snap(0.5);
    await s.camera(card(inv), { dur: 0.9, pad: 16 });
    await s.click(page.getByRole("button", { name: /Order test/ }), { dur: 0.7, settle: 600, after: 0.2 });
    await s.click(page.getByPlaceholder(/Test or scan/), { dur: 0.45, after: 0.05 });
    await s.type("USG abdomen and pelvis", { cps: 14 });
    await s.click(page.getByPlaceholder(/What should it answer/), { dur: 0.45, after: 0.05 });
    await s.type("Epigastric pain in an elderly diabetic — exclude gallstones or a pancreatic cause", { cps: 24 });
    s.hold(0.3);
    await s.click(page.getByRole("button", { name: "Order", exact: true }), { dur: 0.5, settle: 1500, after: 1.6 });
    return s.save();
  },

  // Later: the report arrives, lands on the order and is read against the question.
  async result() {
    const desk = await session(browser, DESK);
    await load(desk);
    const dir = fs.readdirSync(FILES).find((d) => d.includes("LCM-10231"));
    const folder = path.join(FILES, dir, "To upload");
    const name = fs.readdirSync(folder)[0];
    const r = await desk.request.post(`${BASE}/api/patients/${ids.rohit}/documents`, {
      multipart: { file: { name, mimeType: "application/pdf", buffer: fs.readFileSync(path.join(folder, name)) } },
    });
    if (!r.ok()) throw new Error(`upload ${r.status()}`);
    await desk.context().close();
    await new Promise((res) => setTimeout(res, 6000));

    const page = await open((i) => `/patients/${i.rohit}/consult`, { wait: 2200 });
    const s = new Shot(page, "result", OUT);
    const inv = page.getByText("Investigations").first();
    await inv.scrollIntoViewIfNeeded();
    await page.evaluate(() => window.scrollBy(0, -120));
    await page.waitForTimeout(400);
    await s.snap(0.4);
    const order = card(page.getByText("USG abdomen and pelvis").first());
    await s.camera(order, { dur: 1.0, pad: 20 });
    s.mark("back");
    s.hold(1.8);
    await s.click(page.getByRole("button", { name: /Read report against the question/ }), { dur: 0.7, settle: 300, after: 0 });
    await s.watch(1.4, { every: 0.2 });
    await page.waitForTimeout(1500);
    await s.snap(0.2);
    await s.camera(order, { dur: 0.9, pad: 16 });
    s.hold(3.6);
    await s.click(page.getByRole("button", { name: "Mark reviewed" }), { dur: 0.7, settle: 1500, after: 1.2 });
    return s.save();
  },

  // Kavita Joshi: a year of kidney function, read from three reports.
  async trends() {
    const page = await open((i) => `/patients/${i.kavita}/results`, { wait: 2200 });
    const s = new Shot(page, "trends", OUT);
    await s.snap(0.6);
    const item = (t) => page.getByText(t, { exact: true }).first();
    for (const [t, hold] of [["Creatinine", 2.4], ["eGFR", 2.4], ["Urine albumin/creatinine", 2.6]]) {
      await s.click(item(t), { dur: 0.6, settle: 900, after: 0.1 });
      if (t === "Creatinine") await s.camera({ x: 345, y: 150, w: 890, h: 445 }, { dur: 0.9, pad: 10 });
      s.mark(t);
      s.hold(hold);
    }
    await s.camera("full", { dur: 0.8 });
    s.hold(0.4);
    return s.save();
  },

  // The same reports, turned into a stage she can act on.
  async ckd() {
    const page = await open((i) => `/patients/${i.kavita}`, { wait: 2600 });
    const s = new Shot(page, "ckd", OUT);
    await s.snap(0.5);
    const score = card(page.getByText("CKD stage (KDIGO)").first());
    await s.camera(score, { dur: 1.0, pad: 24 });
    s.mark("ckd");
    s.hold(2.6);
    const uacr = card(page.getByText("Urine albumin/creatinine has").first()).locator("xpath=..");
    await s.camera(uacr, { dur: 0.9, pad: 20 });
    s.hold(2.6);
    await s.camera(score, { dur: 0.8, pad: 24 });
    await s.click(page.getByText("How it's calculated").first(), { dur: 0.6, settle: 1200, after: 0.2 });
    const panel = page.getByRole("dialog").first();
    if (await panel.count()) await s.camera(panel, { dur: 0.9, pad: 20 });
    s.hold(3.0);
    return s.save();
  },

  // Ask the chart; every answer shows where it came from.
  async ask() {
    const page = await open((i) => `/patients/${i.kavita}/assistant`, { wait: 2000 });
    const s = new Shot(page, "ask", OUT);
    await s.snap(0.5);
    const box = page.getByPlaceholder(/Ask about Kavita Joshi/);
    await s.click(box, { dur: 0.7, after: 0.05 });
    await s.type("How has her kidney function changed over the last year?", { cps: 18 });
    await s.press("Enter", { settle: 200, after: 0 });
    await s.watch(3.0, { every: 0.2 });
    await page.getByRole("button", { name: /Why this answer/ }).first().waitFor({ timeout: 30_000 }).catch(() => {});
    await page.waitForTimeout(800);
    await s.snap(0.3);
    const answer = page.getByRole("button", { name: /Why this answer/ }).first().locator("xpath=ancestor::*[contains(@class,'rounded')][2]");
    await s.camera(answer, { dur: 0.9, pad: 20 });
    s.hold(2.4);
    const cite = page.locator("button").filter({ hasText: /^(S?\d+|R)$/ }).first();
    if (await cite.count()) {
      await s.click(cite, { dur: 0.6, settle: 1200, after: 0.2 });
      await s.camera("full", { dur: 0.8 });
      s.hold(2.6);
    }
    return s.save();
  },

  // Harish Chandra Gupta: echo, BNP and a stroke-risk score in one view.
  async heart() {
    const page = await open((i) => `/patients/${i.harish}`, { wait: 2800 });
    const s = new Shot(page, "heart", OUT);
    await s.snap(0.6);
    const viewer = page.locator("img[alt='2D Echo and Colour Doppler report']").first();
    if (await viewer.count()) await s.camera(viewer, { dur: 1.1, pad: 10 });
    s.hold(2.2);
    await s.camera(card(page.getByText("CHA₂DS₂-VASc").first()), { dur: 1.0, pad: 20 });
    s.hold(2.2);
    await s.camera(card(page.getByText("BNP has").first()).locator("xpath=.."), { dur: 0.9, pad: 20 });
    s.hold(2.4);
    await s.camera("full", { dur: 0.8 });
    s.hold(0.5);
    return s.save();
  },

  // A CT scan, straight from the DICOM file.
  async ct() {
    const page = await open((i) => `/patients/${i.suresh}/documents`, { wait: 1800 });
    const docs = await api(page, "GET", `/api/patients/${ids.suresh}/documents`);
    const ct = docs.find((d) => d.mime_type === "application/dicom");
    await page.goto(`${BASE}/patients/${ids.suresh}/documents?doc=${ct.id}`);
    await page.waitForLoadState("networkidle").catch(() => {});
    await page.waitForTimeout(2200);
    const s = new Shot(page, "ct", OUT);
    await s.snap(0.6);
    const img = page.locator(`img[alt='${ct.title}']`).first();
    await s.camera(img, { dur: 1.0, pad: 30 });
    s.hold(0.6);
    await s.click(page.getByRole("button", { name: "Zoom in" }), { dur: 0.7, settle: 700, after: 0.6 });
    await s.click(page.getByRole("button", { name: "Zoom in" }), { dur: 0.25, settle: 700, after: 1.4 });
    return s.save();
  },
};

const want = process.argv.slice(2);
for (const name of want.length ? want : Object.keys(SHOTS)) {
  const t0 = Date.now();
  try {
    const d = await SHOTS[name]();
    for (const c of browser.contexts()) await c.close();
    if (d) console.log(`${name}: ${d.frames.length} frames, ${d.duration.toFixed(1)} s (${((Date.now() - t0) / 1000).toFixed(0)} s)`);
  } catch (e) {
    console.log(`${name}: FAILED ${e.message.split("\n")[0]}`);
    const pages = browser.contexts().flatMap((c) => c.pages());
    if (pages.length) await pages.at(-1).screenshot({ path: path.join(OUT, `${name}-failed.png`) }).catch(() => {});
    for (const c of browser.contexts()) await c.close();
  }
}
await browser.close();
