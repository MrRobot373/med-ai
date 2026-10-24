// Records a "shot" of the real app as a list of timed screenshots plus the cursor, click,
// key and camera events the film adds on top. Video time is set here, not by how long the
// browser took: each frame is shown from its `t` until the next frame.
import fs from "node:fs";
import path from "node:path";

export const VIEWPORT = { width: 1600, height: 900 };
export const SCALE = 2;
export const BASE = process.env.APP_URL ?? "http://localhost:8011";

export async function session(browser, account) {
  // The browser runs on the app server's clock and in India time, so greetings and
  // "just now" labels agree with what the server recorded.
  const ctx = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: SCALE, timezoneId: "Asia/Kolkata", locale: "en-IN" });
  const page = await ctx.newPage();
  // Dismissed in a real session; kept out of the recording.
  await page.addInitScript(() => {
    const css = "div.w-64.rounded-2xl.backdrop-blur-xl{display:none!important}";
    document.addEventListener("DOMContentLoaded", () => { const st = document.createElement("style"); st.textContent = css; document.head.append(st); });
    document.addEventListener("focusin", (e) => { if (e.target && "spellcheck" in e.target) e.target.spellcheck = false; }, true);
  });
  const head = await page.request.get(`${BASE}/api/health`);
  await page.clock.install({ time: new Date(head.headers()["date"]) });
  if (account) {
    const r = await page.request.post(`${BASE}/api/auth/login`, { data: account });
    if (!r.ok()) throw new Error(`login ${account.email}: ${r.status()}`);
  }
  return page;
}

export async function api(page, method, url, body) {
  const r = await page.request.fetch(`${BASE}${url}`, { method, data: body });
  if (!r.ok()) throw new Error(`${method} ${url}: ${r.status()} ${await r.text()}`);
  const t = await r.text();
  try { return JSON.parse(t); } catch { return t; }
}

// Small deterministic jitter so typing has a human rhythm and renders identically every time.
function rng(seed) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32);
}

export class Shot {
  constructor(page, name, outRoot) {
    this.page = page;
    this.name = name;
    this.dir = path.join(outRoot, name);
    fs.rmSync(this.dir, { recursive: true, force: true });
    fs.mkdirSync(path.join(this.dir, "frames"), { recursive: true });
    this.t = 0;
    this.frames = [];
    this.events = [];
    this.marks = {};
    this.cursor = { x: VIEWPORT.width * 0.62, y: VIEWPORT.height * 1.08 };
    this.rand = rng(name.length * 7919);
  }

  /** Screenshot the page as it is now; it shows from the current time. */
  async snap(advance = 0) {
    const file = `frames/${String(this.frames.length).padStart(4, "0")}.jpg`;
    await this.page.screenshot({ path: path.join(this.dir, file), type: "jpeg", quality: 94 });
    this.frames.push({ file, t: +this.t.toFixed(3) });
    this.t += advance;
  }

  /** Hold the current frame. */
  hold(s) { this.t += s; }

  /** Name the current time so the film can cue a title or a sound to it. */
  mark(name) { this.marks[name] = +this.t.toFixed(3); }

  sfx(name, offset = 0, volume) { this.events.push({ type: "sfx", t: +(this.t + offset).toFixed(3), name, volume }); }

  async rect(target) {
    const loc = typeof target === "string" ? this.page.locator(target).first() : target;
    await loc.waitFor({ state: "visible", timeout: 20_000 });
    await loc.scrollIntoViewIfNeeded().catch(() => {});
    const b = await loc.boundingBox();
    return { x: b.x, y: b.y, w: b.width, h: b.height };
  }

  /** Move the camera to frame a box (page px), or back to the full screen with "full". */
  async camera(target, { dur = 0.9, pad = 48, ease = "power2.inOut", zoom, at } = {}) {
    let rect = null;
    if (target && target !== "full") {
      rect = target.x !== undefined && target.w !== undefined ? target : await this.rect(target);
      rect = { x: rect.x - pad, y: rect.y - pad, w: rect.w + pad * 2, h: rect.h + pad * 2 };
    }
    this.events.push({ type: "camera", t: +((at ?? this.t)).toFixed(3), dur, rect, zoom, ease });
  }

  /** Glide the cursor to an element (its centre, or an offset inside it) and hover it. */
  async move(target, { dur = 0.6, dx = 0.5, dy = 0.5, hover = true } = {}) {
    let x, y;
    if (target.x !== undefined && target.w === undefined) ({ x, y } = target);
    else {
      const r = target.w !== undefined ? target : await this.rect(target);
      x = r.x + r.w * dx; y = r.y + r.h * dy;
    }
    this.events.push({ type: "cursor", t: +this.t.toFixed(3), dur, x, y });
    this.cursor = { x, y };
    this.t += dur;
    if (hover) { await this.page.mouse.move(x, y, { steps: 4 }); await this.page.waitForTimeout(120); await this.snap(); }
  }

  /** Move to an element and click it. `settle` waits in real time for the app to react. */
  async click(target, { dur = 0.6, settle = 500, waitFor, after = 0.35, dx, dy, sound = "click" } = {}) {
    const loc = typeof target === "string" ? this.page.locator(target).first() : target.w === undefined && target.x === undefined ? target : null;
    const r = loc ? await this.rect(loc) : null;
    await this.move(r ?? target, { dur, dx, dy });
    this.hold(0.12);
    this.events.push({ type: "click", t: +this.t.toFixed(3), x: this.cursor.x, y: this.cursor.y });
    if (sound) this.sfx(sound);
    if (loc) await loc.click({ position: { x: this.cursor.x - r.x, y: this.cursor.y - r.y } });
    else { await this.page.mouse.down(); await this.page.mouse.up(); }
    if (waitFor) await this.page.locator(waitFor).first().waitFor({ state: "visible", timeout: 30_000 });
    await this.page.waitForTimeout(settle);
    this.hold(0.08);
    await this.snap(after);
  }

  /** Type like a person: one frame per key, ~13 keys a second with a natural rhythm. */
  async type(text, { cps = 13, settle = 25 } = {}) {
    for (const ch of text) {
      await this.page.keyboard.type(ch);
      if (settle) await this.page.waitForTimeout(settle);
      this.events.push({ type: "key", t: +this.t.toFixed(3) });
      await this.snap();
      const base = 1 / cps;
      this.t += ch === " " ? base * 1.5 : base * (0.7 + this.rand() * 0.6);
    }
  }

  async press(key, { settle = 300, after = 0.3 } = {}) {
    this.events.push({ type: "key", t: +this.t.toFixed(3), heavy: true });
    await this.page.keyboard.press(key);
    await this.page.waitForTimeout(settle);
    await this.snap(after);
  }

  /** Scroll the page smoothly to a y (page px) or to put an element near the top. */
  async scroll(target, { dur = 0.9, steps = 18, offset = 90 } = {}) {
    const from = await this.page.evaluate(() => window.scrollY);
    let to = typeof target === "number" ? target : null;
    if (to === null) {
      const loc = typeof target === "string" ? this.page.locator(target).first() : target;
      const b = await loc.boundingBox();
      to = Math.max(0, from + b.y - offset);
    }
    for (let i = 1; i <= steps; i++) {
      const p = i / steps;
      const e = p < 0.5 ? 4 * p ** 3 : 1 - (-2 * p + 2) ** 3 / 2;
      await this.page.evaluate((y) => window.scrollTo(0, y), from + (to - from) * e);
      await this.snap(dur / steps);
    }
  }

  /** Record a UI that changes on its own (streaming text, loading) for `seconds` of film time. */
  async watch(seconds, { every = 0.2, until } = {}) {
    const end = this.t + seconds;
    while (this.t < end - 1e-6) {
      await this.page.waitForTimeout(every * 1000);
      await this.snap(every);
      if (until && (await this.page.locator(until).count()) > 0) break;
    }
  }

  save(extra = {}) {
    const duration = +(this.t + 0.001).toFixed(3);
    const data = { name: this.name, viewport: VIEWPORT, scale: SCALE, duration, frames: this.frames, events: this.events, marks: this.marks, ...extra };
    fs.writeFileSync(path.join(this.dir, "shot.json"), JSON.stringify(data, null, 1));
    return data;
  }
}
