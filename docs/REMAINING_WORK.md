# What remains — your checklist

Everything that could be done in code has been done (version 3.0 plus the final pass: FHIR e-prescription view, metrics endpoint,
CI pipeline, Windows installer, accessibility fixes, performance tuning, user guides). **What is left needs a GPU, a person with
a licence or a signature, or money.** This file is the whole list, in the order to do it. Tick as you go.

> **The one-line status:** ready for a **pilot** in a friendly clinic once Part A items 1–3 are done; ready for **general sale**
> once Parts A and B are done.

---

## Part A — Before any real patient data (gating)

### ☐ A1. Create your licence signing key — *you, 10 minutes, once*
Without it, no customer licence can ever be verified (installs stay in "evaluation": 2 doctors, 2 staff, 1 branch).
```
cd med-ai
backend/.venv/bin/python tools/licence.py keygen --out ~/gms-vendor-keys
cp ~/gms-vendor-keys/licence_public.pem backend/app/assets/licence_public.pem
git add backend/app/assets/licence_public.pem && git commit -m "Add vendor licence public key"
scripts/make-bundle.sh            # rebuild: the public key is now inside the product
```
**Back up `~/gms-vendor-keys/licence_private.pem` in two separate safe places and never commit it.**
Then issue a test licence for your own demo install (`docs/VENDOR_RELEASE.md`) and confirm Settings → Licence shows "Licensed".

### ☐ A2. Run every AI feature on a real model — *you provide a GPU, I fix what it finds; 1–2 days*
Everything that calls a language model was only ever tested on the bundled test model.
1. Get a machine with an NVIDIA GPU (24 GB recommended for the 27B clinical model; 12–16 GB runs the 9B general model alone). Install **Ollama**.
2. Pull the models the product is configured for: `ollama pull qwen3.5:9b`, `ollama pull qwen3-embedding:0.6b`, and `ollama pull medgemma:27b`
   (names are the defaults in `.env.example`; change them in Settings → AI models if you choose others).
3. On the clinic server: Settings → AI models → **Test** each of the four roles until green.
4. Load the reference library and measure:
   ```
   docker compose exec app python -m app.seed knowledge
   docker compose exec app python -m app.cli eval
   ```
   Targets: lab extraction ≥ 95 % recall / ≥ 90 % precision (already 99 % / 96 %); right source in top-5 ≥ 90 %; declines ≥ 90 % of questions it cannot answer;
   ≥ 95 % of answers cite evidence and none cite what was not provided.
5. Use each clinical feature by hand on 10–15 patients (pre-visit brief, diagnosis second look, prescription review, result reading, the 7 tools, image/scan reading).
   Note: wrong JSON, slow answers (> 30 s), made-up facts, ignored instructions.
6. **Bring back to me**: the `eval` report (`data/evals/eval-*.json`), your notes, and which models you settled on. I will tune prompts, add a repair step for malformed model output if needed,
   set the supported-model list and minimum hardware per clinic size, and write the validation report.

### ☐ A3. Appoint and brief the Clinical Lead and the Pharmacist — *you, 1–3 weeks to find, then 3–4 days each*
Who and why: `docs/CLINICAL_GOVERNANCE.md`. Steps:
1. Find the two people (teaching-hospital general-medicine faculty; clinical pharmacist / pharmacology department). Sign a written retainer (independence, right to refuse, indemnity — template points in that file).
2. Create their accounts (Settings → Users). Each adds their **registration number** in Profile.
3. Give them `docs/CLINICAL_GOVERNANCE.md` and `backend/app/clinical/testbank.json` (27 plain-language cases) and the formulary files in `backend/app/formulary/data/`.
4. They run **Settings → Clinical content → Run the clinical tests**, review, add cases for anything they disagree with (send those to me: I change the rules until the cases pass),
   then **sign** (password + registration number). Both areas must show "Approved for this version".
5. Every release that changes medical content needs fresh signatures (the product tells you).

### ☐ A4. Medical content is thin — *clinical reviewers decide what; I can do the data entry*
Today: 114 generic medicines (186 brands), 32 interactions, 10 short reference notes. Enough for common outpatient prescribing, **not** a complete drug database.
- Ask the Clinical Lead and Pharmacist for the **top 150 medicines actually prescribed** in the pilot clinic; I add each with brands, dose limits, renal/hepatic/paediatric/pregnancy rules and interactions, **plus a test case for each**, and they review the diff.
- **Reference library**: needs content you own or have licensed (do not copy guidelines without permission). Typical route: the Clinical Lead writes or edits 30–50 one-page summaries of the most common outpatient conditions in Indian practice, citing ICMR / national guidelines; drop them in `knowledge-packs/<domain>/*.md` and run `python -m app.seed knowledge`.
- Decide the **medicine scope statement** you will print in the sales material ("covers N medicines; not a replacement for a drug reference").

### ☐ A5. Regulatory, legal, insurance, security test — *you hire; drafts are ready for them*
All drafts are in `docs/compliance/` (start with its README). In order:
1. **Regulatory consultant** — a written opinion on whether the decision-support features are a medical device under the Medical Devices Rules, 2017, and the route if so (`DEVICE_REGULATORY_POSITION.md`). Until then, market as "record-keeping with decision support" — see the wording guidance in that file.
2. **Lawyer** — review/finish `TERMS_DRAFT.md` (licence, support, liability), `DPDP_READINESS.md` (patient notice, rights procedure, retention period) and `INCIDENT_RESPONSE.md`.
3. **Insurance broker** — technology professional indemnity (with a medical-software extension) and cyber cover. Give them the compliance pack.
4. **Penetration test** — an independent firm tests the installer, update channel, partner API and web app. Give them a test installation from the demo bundle. Fix findings (send them to me), retest, keep the letter.
5. **Hazard log sign-off** — the Clinical Lead and Pharmacist review `HAZARD_LOG.md`, add hazards, and accept residual risks in writing.

### ☐ A6. Pilot with one friendly clinic — *4–8 weeks*
Install from the **customer** bundle (`docs/INSTALL.md`), real staff, real workflow, under a written pilot agreement (data stays on their server; you have no access without their request).
Measure weekly: doctors' minutes per consultation, how often each alert is overridden (too many = alert fatigue → tell me which), any wrong/missing alert (patient-safety report), report-reading errors found,
support calls. Sit and **watch** 5–8 doctors use it (usability observation). Exit criteria: no unresolved safety issue; override rate stable; doctors would pay for it.

---

## Part B — Engineering still open (none blocks a pilot)

| # | Item | Size | Notes / what I need from you |
|---|---|---|---|
| B1 | **Test `install.ps1` on a real Windows 10/11 machine** | S | Written to mirror `install.sh` but never run on Windows. Run it on a spare PC with Docker Desktop and send me any errors. Updates/rollback on Windows use `wsl ./update.sh` |
| B2 | **First CI run** | S | `.github/workflows/ci.yml` is written but has never run on GitHub. Push, watch the Actions tab, send me any red job |
| B3 | **PostgreSQL option** for groups with > ~30 simultaneous staff | M–L | SQLite measured fine to ~15 simultaneous staff and 20,000 patients (`docs/PERFORMANCE.md`); writes queue beyond ~30. Needed only for large customers. Needs a test server |
| B4 | **Multiple application workers / high availability** | L | Today one process; the background jobs (webhooks, backup scheduler) assume one. Needed only with PostgreSQL |
| B5 | **Validate FHIR output against the ABDM profile** | M | The FHIR view exists (`/api/integration/v1/prescriptions/{id}/fhir`) but is not validated against any national profile. Needs the ABDM sandbox / a pharmacy partner |
| B6 | **ABDM / ABHA linkage** | L | Needs ABDM registration and sandbox credentials from you |
| B7 | **Appointment reminders (SMS / WhatsApp)** | M | Needs a gateway account (and DLT/template approval in India) — your decision which provider |
| B8 | **Hindi / Marathi / Tamil screens and patient copy** | L | Needs a translator who knows medical terms; the visit summary is the best first translation |
| B9 | **Digital signature certificate on PDFs / drawn signature pad** | M | Needs a Class-3 DSC from a certifying authority if you want legally signed PDFs |
| B10 | **Container hardening**: image vulnerability scan, SBOM, signed images | S–M | Add to CI (Trivy/Grype); sign release bundles with your own key |
| B11 | **Observability dashboard** | S–M | `/api/integration/v1/metrics` (Prometheus format, needs a `metrics:read` key) exists; a Grafana dashboard/alerts are not built |
| B12 | **Tablet/phone layout check** | S | Desktop is audited (see below); phones/tablets were not tested by me. Open each screen on the devices doctors use and list problems |
| B13 | **Growing the formulary / library** | — | See A4 |
| B14 | **User manual videos** | M | Written guides exist: `DOCTOR_GUIDE.md`, `FRONT_DESK_GUIDE.md`, `INSTALL.md`, `OPERATIONS.md`. Screencasts are yours to record |

## Part C — Business

☐ Pricing (per doctor per year? one-time + support?) — the licence supports doctors / other staff / branches limits and expiry.
☐ Support offer and hours (draft levels in `compliance/TERMS_DRAFT.md`); who answers the phone; ticket tool.
☐ Training: a one-hour session for doctors + 30 minutes for front desk using the guides.
☐ Sales claims reviewed against the regulatory opinion (never "diagnoses", "prevents errors"). The film needs disclaimers and credits for the open image datasets (listed in each patient folder's `IMAGE_SOURCES.md`).
☐ Customer ledger for licences (customer, Installation ID, limits, expiry) — `docs/VENDOR_RELEASE.md`.
☐ ISO 27001 later (`compliance/INSURANCE_AND_CERTIFICATION.md`); ISO 13485 only if the regulator says the software is a device.

## Part D — Honest limits of what exists today

- **AI quality is unmeasured on real models** (A2). Lab-value reading is measured (99 % / 96 %); the rest is not.
- **Medical content is a starting set** (A4) and **unsigned** (A3). The product shows this in Settings and the security checklist.
- **Tested concurrency**: 15 staff comfortable, 30 works but writes queue; single server, no failover. Backups are daily — a disk failure can lose up to a day unless the off-site copy runs more often.
- **Windows installer, CI pipeline, FHIR profile validation** are written but have not run in their real environments (B1, B2, B5).
- **Accessibility**: automated WCAG 2 A/AA audit passes on the 8 main screens in light and dark themes; that finds about a third of real problems. A manual keyboard/screen-reader review is still advisable.
- **The compliance files are drafts, not legal or regulatory advice** (A5).
- **Licence checking is a business control**, not copy protection (`VENDOR_RELEASE.md`).

## How to hand work back to me

For each item above, bring: (A2) the eval JSON + notes; (A3/A4) the reviewers' comments or the medicine list; (A5) the consultant's/lawyer's/pentester's findings; (A6) the pilot weekly numbers and the alert-override list;
(B1/B2) error text. I turn each into code, tests and updated documents, and rebuild the bundle (`scripts/make-bundle.sh`).
