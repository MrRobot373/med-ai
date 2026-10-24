// Turns the captured shots (../capture/out) into HyperFrames scenes and the root timeline.
//   node build.mjs            encode shots + write compositions/*.html and index.html
//   node build.mjs --no-encode  rewrite the HTML only
// Hand-written scenes (hook, title, interstitials, claim, end) live in compositions/ too and
// are listed in FILM below with their own durations.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CAP = path.join(HERE, "..", "capture", "out");
const encode = !process.argv.includes("--no-encode");

// The app window on the frame: 1600x900 page px shown at 1760x990, centred.
const WIN = { x: 80, y: 45, w: 1760, h: 990 };
const K = WIN.w / 1600;
const MAX_ZOOM = 2.0;

// The film, in order. `shot` scenes come from captures; `file` scenes are hand-written.
// enter: "rise" (window rises in from the ground) or "cut" (continues the previous frame).
const FILM = [
  { file: "hook", dur: 8.5 },
  { file: "title", dur: 5.0 },
  {
    shot: "login", enter: "rise", captions: [[0.4, "Dr. Ananya Rao signs in", 3.2]],
    cameraStart: { x: 300, y: 200, w: 1000, h: 500 }, cameraAdd: [{ t: 7.3, rect: null, dur: 0.9 }],
  },
  { shot: "dashboard", enter: "cut", captions: [[1.0, "Today's patients, and what changed for each", 3.6]] },
  {
    shot: "overview", enter: "cut",
    captions: [[0.7, "Every report, already read", 3.0], ["cam:2", "Out-of-range values, flagged from the source", 3.2]],
    camera: { 4: { x: 120, y: 150, w: 330, h: 290 } },
  },
  { shot: "brief", enter: "cut", captions: [[0.6, "Before the patient walks in", 3.0], ["cam:3", "What changed, and what to ask today", 3.0]], camera: { 3: { x: 90, y: 370, w: 800, h: 420 } } },
  { shot: "consult", enter: "cut", rate: 1.25, captions: [[0.3, "Notes and vitals, as the doctor works", 3.2], ["cam:2", "A second look at the diagnosis", 3.2]], camera: { 0: { x: 90, y: 200, w: 690, h: 420 } } },
  {
    shot: "rx", enter: "cut",
    captions: [["checked", "Checked against his age, kidneys, medicines and allergies", 3.6], ["med2", "Sulfa allergy — stopped before it is prescribed", 3.6]],
  },
  { shot: "finalise", enter: "cut" },
  { shot: "print", enter: "rise", captions: [[0.4, "A clean prescription on the clinic letterhead", 3.2]] },
  { shot: "order", enter: "rise", rate: 1.2, captions: [[0.3, "Ordered with the question it should answer", 3.4]] },
  { file: "later", dur: 2.2 },
  {
    shot: "result", enter: "rise", captions: [["back", "The report lands on the right order", 3.0], ["cam:1", "Read against the question that was asked", 3.4]],
    camera: { 0: { x: 815, y: 600, w: 740, h: 150 }, 1: { x: 815, y: 330, w: 740, h: 400 } },
    cameraAdd: [{ t: 3.25, rect: { x: 815, y: 330, w: 740, h: 400 }, dur: 0.6 }],
  },
  { file: "kavita", dur: 3.0 },
  { shot: "trends", enter: "rise", captions: [["Creatinine", "Creatinine 1.30 → 1.45 → 1.62", 2.6], ["eGFR", "eGFR 46 → 41 → 36", 2.6], ["Urine albumin/creatinine", "Albumin in the urine, rising", 2.6]] },
  { shot: "ckd", enter: "cut", captions: [["ckd", "CKD stage G3b A3, worked out from her own reports", 3.4]] },
  { shot: "ask", enter: "cut", captions: [[0.4, "Ask the chart. See the source.", 3.2]], camera: { 0: { x: 450, y: 300, w: 900, h: 420 } } },
  { file: "harish", dur: 2.6 },
  { shot: "heart", enter: "rise", captions: [[0.6, "Echo, BNP and stroke risk in one view", 3.4]] },
  { shot: "ct", enter: "cut", captions: [[0.4, "CT and MRI straight from the scanner", 3.0]] },
  { file: "claim", dur: 5.4 },
  { file: "end", dur: 6.5 },
];

const r3 = (n) => +n.toFixed(3);

function encodeShot(name, d, rate) {
  const dir = path.join(CAP, name);
  const list = path.join(dir, "frames.txt");
  const lines = [];
  d.frames.forEach((f, i) => {
    const next = i + 1 < d.frames.length ? d.frames[i + 1].t : d.duration;
    lines.push(`file '${f.file}'`, `duration ${Math.max(0.001, (next - f.t) / rate).toFixed(4)}`);
  });
  lines.push(`file '${d.frames.at(-1).file}'`);
  fs.writeFileSync(list, lines.join("\n") + "\n");
  const out = path.join(HERE, "assets", "shots", `${name}.mp4`);
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list,
    "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-movflags", "+faststart", out]);
}

// Camera state that frames a page-px rect inside the window, without showing past its edges.
function frame(rect, zoomOverride) {
  if (!rect) return { x: 0, y: 0, scale: 1 };
  const z = Math.max(1, Math.min(zoomOverride ?? Math.min(WIN.w / (rect.w * K), WIN.h / (rect.h * K)), MAX_ZOOM));
  const cx = (rect.x + rect.w / 2) * K, cy = (rect.y + rect.h / 2) * K;
  const x = Math.min(0, Math.max(WIN.w - WIN.w * z, WIN.w / 2 - cx * z));
  const y = Math.min(0, Math.max(WIN.h - WIN.h * z, WIN.h / 2 - cy * z));
  return { x: r3(x), y: r3(y), scale: r3(z) };
}

const CURSOR_SVG = `<svg viewBox="0 0 28 32" width="28" height="32" xmlns="http://www.w3.org/2000/svg"><path d="M3 2.5v23.2l6.1-5.6 3.9 9.1 4.3-1.9-3.9-8.9 8.4-.6L3 2.5z" fill="#0f172a" stroke="#ffffff" stroke-width="2" stroke-linejoin="round"/></svg>`;

function captionHTML(id, text, start, dur) {
  const words = text.split(" ").map((w, i) => `<span class="w" id="${id}-w${i}">${w}</span>`).join(" ");
  return `<div id="${id}" class="clip cap" data-start="${start}" data-duration="${dur}" data-track-index="3"><div class="cap-in" id="${id}-in">${words}</div></div>`;
}

function shotScene(item, lastCursor) {
  const name = item.shot;
  const d = JSON.parse(fs.readFileSync(path.join(CAP, name, "shot.json"), "utf8"));
  const rate = item.rate ?? 1;
  if (encode) encodeShot(name, d, rate);
  const T = (t) => r3(t / rate);
  const dur = r3(d.duration / rate);
  const tw = [];
  const audio = [];
  let a = 0;
  const lanes = [];
  const sfx = (file, t, vol, len) => {
    const id = `${name}-a${a++}`;
    const start = r3(Math.max(0, t));
    // First Studio lane that is free at this time, so no two sounds share a lane.
    let lane = lanes.findIndex((end) => end <= start);
    if (lane < 0) lane = lanes.push(0) - 1;
    lanes[lane] = start + len;
    audio.push(`<audio id="${id}" class="clip" data-hf-media-start-basis="local" data-start="${start}" data-duration="${r3(len)}" data-track-index="${10 + lane}" data-volume="${vol}" src="assets/sfx/${file}"></audio>`);
  };

  // Entrance
  if (item.enter === "rise") {
    tw.push(`tl.fromTo("#${name}-win", { y: 70, scale: 0.94, opacity: 0, filter: "blur(10px)" }, { y: 0, scale: 1, opacity: 1, filter: "blur(0px)", duration: 0.8, ease: "expo.out" }, 0);`);
    sfx("whoosh.mp3", 0, 0.32, 0.57);
  } else {
    tw.push(`tl.set("#${name}-win", { y: 0, scale: 1, opacity: 1 }, 0);`);
  }

  // Camera: the captured moves, with per-film overrides where the captured target was off.
  const cams = d.events.filter((e) => e.type === "camera").map((e, i) => (item.camera?.[i] ? { ...e, rect: item.camera[i] } : e));
  cams.push(...(item.cameraAdd ?? []).map((e) => ({ type: "camera", ease: "power2.inOut", ...e })));
  cams.sort((p, q) => p.t - q.t);
  let cam = frame(item.cameraStart ?? null);
  tw.push(`tl.set("#${name}-cam", { x: ${cam.x}, y: ${cam.y}, scale: ${cam.scale} }, 0);`);
  let whoosh = 0;
  for (const e of cams) {
    const next = frame(e.rect, e.zoom);
    tw.push(`tl.to("#${name}-cam", { x: ${next.x}, y: ${next.y}, scale: ${next.scale}, duration: ${T(e.dur)}, ease: "${e.ease ?? "power2.inOut"}" }, ${T(e.t)});`);
    if (Math.abs(next.scale - cam.scale) > 0.25) sfx(whoosh++ % 2 ? "whoosh-short.mp3" : "whoosh.mp3", T(e.t) + 0.05, 0.14, 0.57);
    cam = next;
  }

  // Cursor
  const start = lastCursor ?? { x: 1600 * 0.62, y: 900 * 1.12 };
  tw.push(`tl.set("#${name}-cursor", { x: ${r3(start.x * K)}, y: ${r3(start.y * K)}, scale: 1 }, 0);`);
  let cur = start;
  for (const e of d.events) {
    if (e.type === "cursor") {
      tw.push(`tl.to("#${name}-cursor", { x: ${r3(e.x * K)}, y: ${r3(e.y * K)}, duration: ${T(e.dur)}, ease: "power3.inOut" }, ${T(e.t)});`);
      cur = { x: e.x, y: e.y };
    } else if (e.type === "click") {
      tw.push(`tl.to("#${name}-cursor", { scale: 0.82, duration: 0.07, ease: "power2.in" }, ${T(e.t) - 0.04});`);
      tw.push(`tl.to("#${name}-cursor", { scale: 1, duration: 0.16, ease: "power2.out" }, ${T(e.t) + 0.04});`);
    }
  }

  // Sound on the real events
  let c = 0;
  for (const e of d.events.filter((e) => e.type === "sfx" && e.name === "click")) sfx(c++ % 2 ? "click-soft.mp3" : "click.mp3", T(e.t) - 0.01, 0.55, 0.36);
  const keys = d.events.filter((e) => e.type === "key");
  for (const e of keys.filter((k) => k.heavy)) sfx("key-press.mp3", T(e.t), 0.5, 0.43);
  const light = keys.filter((k) => !k.heavy).map((k) => T(k.t));
  for (let i = 0; i < light.length;) {
    let j = i;
    while (j + 1 < light.length && light[j + 1] - light[j] < 0.3) j++;
    const s0 = light[i], s1 = light[j] + 0.12;
    for (let t = s0; t < s1; t += 1.5) sfx("typing.mp3", t, 0.32, Math.min(1.5, s1 - t));
    i = j + 1;
  }

  // Captions
  const caps = [];
  const startOf = (at) => {
    if (typeof at === "number") return at;
    if (at.startsWith("cam:")) return T(d.events.filter((e) => e.type === "camera")[+at.slice(4)].t) + 0.35;
    if (!(at in d.marks)) throw new Error(`${name}: no mark "${at}"`);
    return T(d.marks[at]) + 0.2;
  };
  (item.captions ?? []).forEach(([at, text, len], i, all) => {
    const t0 = startOf(at);
    const id = `${name}-cap${i}`;
    const next = i + 1 < all.length ? startOf(all[i + 1][0]) - 0.15 : dur - 0.05;
    const end = Math.min(len, next - t0, dur - t0 - 0.05);
    if (end < 1) return;
    caps.push(captionHTML(id, text, r3(t0), r3(end)));
    const n = text.split(" ").length;
    tw.push(`tl.fromTo("#${id}-in", { y: 18, opacity: 0 }, { y: 0, opacity: 1, duration: 0.45, ease: "expo.out" }, ${r3(t0)});`);
    for (let w = 0; w < n; w++) tw.push(`tl.fromTo("#${id}-w${w}", { opacity: 0, filter: "blur(6px)" }, { opacity: 1, filter: "blur(0px)", duration: 0.14, ease: "power2.out" }, ${r3(t0 + 0.05 + w * 0.06)});`);
    tw.push(`tl.to("#${id}-in", { opacity: 0, filter: "blur(6px)", duration: 0.2, ease: "power2.in" }, ${r3(t0 + end - 0.24)});`);
  });

  const html = `<template>
  <style>
    #root { position: absolute; inset: 0; overflow: hidden; }
    #${name}-ground { position: absolute; inset: 0; background: #e9eef6; }
    #${name}-win { position: absolute; left: ${WIN.x}px; top: ${WIN.y}px; width: ${WIN.w}px; height: ${WIN.h}px; border-radius: 22px; overflow: hidden; background: #f3f6fb;
      box-shadow: 0 40px 90px -40px rgba(15, 27, 61, 0.45), 0 0 0 1px rgba(15, 27, 61, 0.07); }
    #${name}-cam { position: absolute; left: 0; top: 0; width: ${WIN.w}px; height: ${WIN.h}px; transform-origin: 0 0; }
    #${name}-video { position: absolute; left: 0; top: 0; width: ${WIN.w}px; height: ${WIN.h}px; object-fit: cover; }
    #${name}-cursor { position: absolute; left: 0; top: 0; width: ${r3(28 * K)}px; height: ${r3(32 * K)}px; transform-origin: 3px 3px; filter: drop-shadow(0 2px 3px rgba(0,0,0,.25)); }
    #${name}-cursor svg { width: 100%; height: 100%; display: block; }
    .cap { position: absolute; left: 192px; bottom: 112px; }
    .cap-in { display: inline-block; padding: 18px 28px; border-radius: 14px; background: #0f1b3d; color: #ffffff; font-family: Inter, sans-serif; font-weight: 600;
      font-size: 34px; letter-spacing: -0.015em; box-shadow: 0 18px 40px -18px rgba(15, 27, 61, 0.6); }
    .w { display: inline-block; }
  </style>
  <div id="root" data-composition-id="${name}" data-width="1920" data-height="1080">
    <div id="${name}-ground"></div>
    <div id="${name}-win">
      <div id="${name}-cam">
        <video id="${name}-video" class="clip" data-start="0" data-duration="${dur}" data-track-index="1" muted playsinline src="assets/shots/${name}.mp4"></video>
        <div id="${name}-cursor">${CURSOR_SVG}</div>
      </div>
    </div>
    ${caps.join("\n    ")}
    ${audio.join("\n    ")}
  </div>
  <script>
    const tl = gsap.timeline({ paused: true });
    ${tw.join("\n    ")}
    tl.set({}, {}, ${dur});
    window.__timelines["${name}"] = tl;
  </script>
</template>
`;
  fs.writeFileSync(path.join(HERE, "compositions", `${name}.html`), html);
  return { dur, cursor: cur };
}

let t = 0;
let cursor = null;
const hosts = [];
for (const item of FILM) {
  const id = item.shot ?? item.file;
  let dur = item.dur;
  if (item.shot) {
    const out = shotScene(item, item.enter === "cut" ? cursor : null);
    dur = out.dur;
    cursor = out.cursor;
  } else cursor = null;
  hosts.push(`      <div id="${id}" data-composition-id="${id}" data-composition-src="compositions/${id}.html" data-start="${r3(t)}" data-duration="${r3(dur)}" data-track-index="1" data-track-kind="graphics" data-width="1920" data-height="1080"></div>`);
  t += dur;
}
const total = r3(t);
const index = `<!doctype html>
<html lang="en" data-resolution="landscape">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body { margin: 0; width: 1920px; height: 1080px; overflow: hidden; background: #e9eef6; }
      #bg { position: absolute; inset: 0; background: #e9eef6; }
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="${total}" data-width="1920" data-height="1080">
      <div id="bg"></div>
${hosts.join("\n")}
    </div>
    <script>
      const tl = gsap.timeline({ paused: true });
      tl.set({}, {}, ${total});
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
`;
fs.writeFileSync(path.join(HERE, "index.html"), index);
console.log(`film: ${FILM.length} scenes, ${total.toFixed(1)} s`);
fs.writeFileSync(path.join(HERE, "timeline.json"), JSON.stringify(FILM.map((f, i) => ({ id: f.shot ?? f.file, start: +hosts[i].match(/data-start="([\d.]+)"/)[1] })), null, 1));
