# Product film

`film/` is a [HyperFrames](https://github.com/heygen-com/hyperframes) project that renders the GMS Clinical AI
product film from real screens of the app. `SCRIPT.md` is the voiceover script, timed to the film.

## Rebuild

1. Serve the app seeded with the demo data and the mock AI in plain mode
   (`MOCK_AI_PLAIN=1 python -m app.devtools.mock_ai`, `python -m app.seed use-mock-ai`, `python -m app.seed demo`,
   LLM model name set to `med-ai`) on `http://localhost:8011` (or set `APP_URL`).
   The film was captured with the server and browser clocks at 10:05 IST on 23 Oct 2026.
2. `node capture/capture.mjs` — drives the app in Chromium and saves every shot as timed frames plus the
   cursor, click, key and camera events (`capture/out/`, about 10 minutes). Shots build on each other, so
   run them in order on a fresh seed. `python capture/sheet.py <shot> 6 out.jpg` makes a contact sheet.
3. `node film/build.mjs` — encodes the shots and writes the scenes and `index.html`.
4. In `film/`: `npm run check`, then `npx hyperframes render -q delivery -o renders/gms-clinical-ai-film.mp4`.

The hand-made scenes (`hook`, `title`, `later`, `kavita`, `harish`, `claim`, `end`) live in `film/compositions/`;
captions, camera overrides and scene order are in the `FILM` list at the top of `film/build.mjs`.
