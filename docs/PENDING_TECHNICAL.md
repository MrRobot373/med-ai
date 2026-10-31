# GMS Clinical AI — Pending technical work

**Verdict: the product is not complete.** It is a working, tested **pilot-grade build** (v2.0.0): all the
features in [FEATURES.md](FEATURES.md) exist, 96 backend + 8 frontend + 6 browser tests pass, and it deploys
cleanly with Docker. It is suitable for **demonstrations and supervised testing with fictional or
consented test data**. It is **not ready for real patients** until the items marked **P0** are done.

Management, regulatory and legal items are in [PENDING_MANAGEMENT.md](PENDING_MANAGEMENT.md).

How this list was made: every item was checked against the code, and against the original specification
(`MASTER BUILD PROMPT…md`, 144 sections). Where the spec asked for something that was later changed by the
owner, that is recorded under [Decided differently](#decided-differently-not-pending). Estimates are rough
relative sizes for one engineer: **S** ≤ 1 day · **M** 2–5 days · **L** 1–3 weeks · **XL** more than 3 weeks.

---

## The five things that matter most

| # | Gap | Why it matters |
|---|---|---|
| 1 | **No AI feature has ever run against a real model.** Everything (brief, second look, dose review, result reading, chat, tools, vision) was built and tested against the bundled test AI. | The quality, speed and reliability of the headline features are unknown. [T-01] |
| 2 | **No evaluation suite or golden question set** (spec §95–96, demo priority #43). | There are no measured numbers for retrieval, citation accuracy, hallucination or abstention. [T-02] |
| 3 | **Medical content is thin.** Formulary: 114 generics, 186 brands, 32 interactions. Knowledge library: 10 short placeholder notes. None reviewed by a pharmacist or clinician. | The safety checks only cover what is in the data. [T-03, T-04] |
| 4 | **Security hardening is incomplete**: no MFA, no lockout, no security headers, no encryption at rest, the server starts in production with the default secret key. | Required before any real patient data. [T-06] |
| 5 | **PyMuPDF is AGPL-3.0.** | Distributing or hosting the product for others needs a commercial licence or a replacement library. [T-05] |

---

## P0 — Must be done before real-patient use

### T-01 · Validate every AI feature with real models — **L** · needs a GPU endpoint
**Now:** all AI parts are marked 🧪 in FEATURES.md. The test AI returns well-formed, predictable output; real models
do not.
**To do**
- Run each clinical-model feature (pre-visit brief, diagnosis second look, prescription review, result reading),
  chat, the 7 tools and vision against the intended models (MedGemma 27B / 4B, the general model, the embedding
  model).
- Measure per feature: valid-JSON rate, schema-conformance, latency (first token and total), citation validity,
  refusal/abstention behaviour, failure modes. Tune prompts; set timeouts and context sizes.
- Add a **repair path** for malformed JSON (today one request is retried only for JSON-mode / `think`
  switches; an unparsable answer becomes an error).
- Decide the supported model list and **minimum hardware** per clinic size.
- Verify scanned-page transcription and image analysis on real scans (not only on generated PDFs).
**Done when:** a written validation report with pass thresholds per feature.

### T-02 · Evaluation suite and golden dataset (spec §95–96) — **L**
**Now:** nothing exists.
**To do**
- Create `evaluation/` with `golden_questions.jsonl` and scripts for: Recall@5/10/20, MRR, nDCG, citation
  precision and coverage, groundedness, hallucination, abstention accuracy, vision extraction, patient
  isolation, latency; an HTML/Markdown report generator.
- Golden set (≈100–150 questions) over the 15 patient folders — the ground truth is known because the
  reports were written from the registration data — covering exact-drug, semantic-symptom, numeric-lab,
  history, comparison, guideline, **no-evidence**, **patient-isolation attack** and **prompt-injection
  document** cases.
- Run retrieval metrics with a real embedding model; run answer metrics when T-01 gives a real LLM.
**Done when:** a published report with baseline numbers and a regression gate in CI (T-10).

### T-03 · Formulary scale and validation — **XL** · needs a pharmacist/clinical pharmacologist
**Now:** 114 generics, 186 products, 32 interaction rules, 13 allergy groups, 24 duplicate classes, version 2026.10.
The Indian market has many thousands of brands and combinations; unrecognised medicines get *no rule checks*
(the doctor sees "not recognised").
**To do**
- Choose and **license** a source (e.g. a national formulary / commercial drug database) and build an importer
  with versioning and a monthly update process.
- Expand: injectables and IV, units (IU, mcg, mg/kg), topicals, inhalers, tapering and loading doses,
  **paediatric weight-based dosing**, pregnancy and **lactation** categories, more interactions with
  severity and mechanism, food/alcohol interactions, drug–disease and drug–lab rules.
- Schedule H/H1/X and narcotic flags.
- A **rule test-bank** (≥ 300 prescriptions with expected findings) reviewed and signed off by a clinical
  pharmacologist; run in CI.
- A visible "formulary version / last reviewed" stamp in the UI and on prints.
**Done when:** coverage target agreed (e.g. top-N Indian outpatient brands) and sign-off recorded.

### T-04 · Knowledge-library content — **L** · needs licensed content and a clinical reviewer
**Now:** 10 short notes in 6 domains, each labelled "demo reference summary".
**To do:** acquire/licence real guidelines (KDIGO, ADA/RSSDI, ESC/CSI, ICMR, API, etc.), ingest, check how tables
and algorithms chunk, set update cadence, show source + version + date on every citation. Domain owners
review. Until then the Guideline Q&A tool will mostly abstain.

### T-05 · Replace or license PyMuPDF (AGPL-3.0) — **M**
**Now:** PDF reading depends on PyMuPDF (word boxes, page images). Noted in `THIRD_PARTY_NOTICES.md`.
**Options:** (a) buy the Artifex commercial licence; (b) replace with permissive libraries — `pypdfium2`
(page images, text) + `pdfminer.six` / `pdfplumber` (word positions) — and re-verify the layout-based table
reconstruction (the 12.9 → 129 regression test must keep passing).
Dev scripts (patient-file generator, video) also use it; keep them out of the shipped image or switch too.

### T-06 · Security hardening — **L**
| Item | Now | To do |
|---|---|---|
| Secure start | Server starts in production with the default `APP_SECRET_KEY` and bootstrap password | Refuse to start (or loudly fail health) when `APP_ENV=production` and secrets are defaults; force admin password change at first login — **S** |
| MFA | None | TOTP for admin and clinician roles, recovery codes — **M** |
| Lockout | 8 attempts / 10 min per email+IP, in memory, per process | Persistent progressive lockout, admin unlock, shared store so it works with several workers — **M** |
| Password policy | Minimum 8 characters | ≥ 12, breached-password check, optional expiry — **S** |
| Sessions | Can be listed; **cannot be revoked**; changing or resetting a password leaves other sessions alive | Revoke-all on password change/reset, "sign out other devices", per-session revoke — **S** |
| Browser protections | CORS configured; cookie HttpOnly + SameSite=Lax; no CSP/HSTS/X-Frame-Options/nosniff/Referrer-Policy; no CSRF token | Add headers and a strict CSP; Origin check or double-submit CSRF token on state-changing routes — **S–M** |
| Encryption at rest | Only API keys are encrypted; database, uploads and the vector index are plain files | Documented disk encryption (LUKS) as a minimum; optional SQLCipher + per-file encryption of uploads — **M–L** |
| Key management | Changing `APP_SECRET_KEY` silently makes stored API keys unreadable | Key-rotation command that re-encrypts; secret loading from a vault/file — **M** |
| Upload scanning | Size, type, magic-byte, duplicate checks | ClamAV scan hook; page-count and image-dimension limits against decompression bombs; strip active content — **M** |
| Audit integrity | 35 actions logged; table is ordinary and editable | Hash-chained entries and scheduled signed export; add missing actions (appointment edit/delete, observation delete, AI-run views, search queries) — **M** |
| Verification | — | Dependency and image scanning in CI (T-10); an external penetration test (see management file) |

### T-07 · Backup, restore and retention — **M**
**Now:** none built in (documentation only). Patient deletion is a **permanent hard delete** with no recycle bin.
**To do:** one command that takes a consistent snapshot of database + uploads + vector index; scheduled
backups with off-site copy and encryption; a **tested restore drill**; retention settings; a recoverable
"archive" step before permanent erasure; a documented right-to-erasure workflow.

### T-08 · Reliability and scale — **L**
- **Stuck documents:** processing runs inside the server process; if the server restarts mid-way, documents stay
  "processing" until someone clicks *Reprocess*. Add startup recovery and a durable queue with retries and a
  concurrency cap.
- **Single writer / single process:** SQLite and the embedded Qdrant folder allow one server process. For
  more than a small clinic: PostgreSQL option (migrations are only tested on SQLite) and Qdrant server mode
  (already supported), then re-test.
- **Per-process state:** the sign-in limiter is in memory; the settings cache now refreshes every 3 s but is
  per process. Move both to the shared store.
- Graceful shutdown that lets streaming answers finish; request timeouts on every external call.
- Server-side stop of a generation: today *Stop* aborts the browser request; confirm the model call stops too.

### T-09 · Performance and load — **M**
No load or size testing has been done. Define targets (e.g. page < 1 s, first token < N s on the chosen model),
then test 10–20 concurrent users, a 10,000-document index, 200-page PDFs, and list endpoints (the patient list
is capped at 500 rows and has no paging). Profile for N+1 queries.

### T-10 · CI/CD — **M**
There is **no pipeline** (`.github/` does not exist). Add: Ruff + type-check (mypy/pyright; the backend has none),
pytest with a coverage gate, frontend `tsc`/ESLint/Vitest/build, Playwright on a seeded stack, Docker build,
image and dependency scans (Trivy, `pip-audit`, `npm audit`), SBOM, and tagged releases with a changelog.

### T-11 · Test depth — **M**
Today: 96 backend, 8 frontend unit, 6 browser tests; backend coverage has not been measured.
**Add:** a generated test that every route has an auth dependency and the role matrix is as intended;
prompt-injection document test (spec §98); migration upgrade 0001 → 0003 **with data**; concurrency tests;
more frontend component tests; automated accessibility checks (axe) in Playwright; Firefox and WebKit;
tablet and phone layouts (only two phone screens were checked); visual regression.

### T-12 · Observability — **M**
Structured JSON logs with request ids (and a test that PHI is not logged), metrics (Prometheus) for request
latency, AI latency/failure and queue depth, error tracking, and alerts when an AI endpoint is down.
Today there is a health page and plain logs.

---

## P1 — Functional gaps against the specification

| ID | Gap | What to build | Size |
|---|---|---|---|
| T-13 | **Prescription content and sharing.** The print shows doctor name and contact but **no registration number or qualifications**; there is no PDF download, no e-signature, no way to send it to the patient. | Registration no., qualifications, clinic address/phone on profile and print; generic-name print option; PDF download; share by WhatsApp/SMS/email; QR verification; optional digital signature | M |
| T-14 | **Standards and integrations.** No FHIR, HL7, LOINC/SNOMED, ABDM/ABHA, LIS or PACS links. Export is a plain-text summary. ICD-10 is a free-text field (no lookup). | FHIR R4 export/import (Patient, Observation, MedicationRequest, DiagnosticReport, DocumentReference); ICD-10 lookup; LOINC mapping for labs; ABHA linking and ABDM sandbox milestones; DICOMweb/LIS adapters. (CPT is US-specific; use a local procedure code set instead.) | XL |
| T-15 | **Imaging.** DICOM shows one frame (the middle one); no scroll through slices or series, no window/level control, no measurements; no previous-vs-current image comparison (spec §61); no de-identification utility or PHI warning (spec §62). | Series viewer with scroll and window/level, thumbnails per series, comparison view, de-identify-on-export | L |
| T-16 | **Source highlighting** (spec §127): citations show the quoted text but do not highlight the passage on the page. | Store word boxes at ingestion; draw them in the viewer | M |
| T-17 | **Voice consultation** (spec §91): not built. | Local speech-to-text (e.g. faster-whisper), manual Doctor/Patient speaker correction, SOAP draft, behind a feature flag | L |
| T-18 | **Consistency checks** (spec §37) only exist for the diagnosis second look. | Cross-document contradiction detection (e.g. conflicting allergies/medicines/dates), near-duplicate detection beyond identical files | M |
| T-19 | **Languages.** English only; no translation framework. | i18n framework, Hindi/Marathi (and others) for the UI and patient instructions, Devanagari fonts in print, native-clinician review | L |
| T-20 | **Chart completeness.** "No known allergies" cannot be recorded (the badge says "Allergies not documented"); no pregnancy/lactation field, height, weight history chart, growth charts, family/social history, immunisations. | Add the fields and show them in the safety checks (pregnancy and weight already feed the rules) | M |
| T-21 | **Orders and results.** No partial or multiple results per order, panel orders, order sets, critical-value call-back, or outside-lab feeds. | As listed | M–L |
| T-22 | **Reminders and notifications** (optional — appointments were meant to stay simple): none. | SMS/WhatsApp/email reminders and result alerts | M |
| T-23 | **Admin and enterprise.** No SSO (OIDC/LDAP), bulk user import, backup UI, usage dashboard. | As listed | M–L |
| T-24 | **Accessibility audit.** Contrast is designed to WCAG AA; no formal audit, screen-reader or keyboard-only test. | Audit and fixes | M |
| T-25 | **Reranker.** Implemented (local, remote, LLM judge) but **off by default** and never evaluated. | Evaluate with T-02 and pick the default profile | S |

## P2 — Operations, docs and polish

| ID | Item | Size |
|---|---|---|
| T-26 | **Demo reset** command (spec §87), **model warm-up** at start (spec §101), latency instrumentation beyond chat (spec §100) | S–M |
| T-27 | **Docs the spec asked for:** `rag-design.md`, `medical-safety.md`, `demo-guide.md`, troubleshooting guide, final completion report (spec §139); per-role user manuals; training slides; API guide; changelog | M |
| T-28 | **Product film:** end card has no "all patients are fictional" line and no dataset credits (the images are CC BY / CC0 / public — CC BY requires credit); voiceover and music not yet mixed in; no captions/subtitles; no short vertical cut | S–M |
| T-29 | **Repo tidy:** the 4,800-line master prompt sits in the repository root (move to `docs/spec/` or remove); remove dev-only tools (`devtools/mock_ai`, `scripts/patient_files`) from the production image | S |
| T-30 | **Release process:** semantic versions, tagged builds, upgrade notes, rollback plan | S |

---

## Decided differently (not pending)

These were in the original specification and were deliberately changed by the owner:

| Spec item | What happened |
|---|---|
| Web research (§64–72, §129): PubMed/FDA/SearXNG, de-identified queries, research UI, web cache | **Removed entirely** at the owner's request ("no need of research"); migration 0003 dropped its tables. The product works fully offline. |
| "Attached screenshots are the visual source of truth" (§20) | Replaced by the owner's later direction; the design is documented in DESIGN.md. |
| Platform scope | Extended beyond the spec: appointments, front-desk role, consultation co-pilot, India formulary, orders and auto-matching. |
| Demo accounts and "synthetic" labels | Removed; replaced with named staff and 15 realistic patient folders. |

---

## What I can do next

Grouped by what each needs. Nothing here requires waiting for a person unless stated.

### A · I can do now, here, without anything from you
| Item | What I would deliver |
|---|---|
| T-06 (most of it) | Secure-start guard, security headers + CSP, CSRF check, password policy, session revoke-all, persistent lockout, audit additions and hash chain, key-rotation command; tests for each |
| T-05 | Replace PyMuPDF with permissive libraries and keep all table/ingestion tests green |
| T-08 (part) | Startup recovery of stuck documents and a durable job queue |
| T-10, T-11 | GitHub Actions pipeline; route-auth matrix test; prompt-injection and migration tests; axe checks |
| T-02 (part) | The golden question set and the whole evaluation harness; retrieval metrics with a small real embedding model if it can be downloaded here |
| T-13 | Registration number and qualifications on profile and print, PDF download, share link |
| T-14 (part) | FHIR R4 export; ICD-10 lookup if a freely licensed code list is acceptable |
| T-15, T-16, T-20 | Multi-slice DICOM viewer, citation highlighting, chart fields |
| T-19 (scaffold) | i18n framework and string extraction (translations need review) |
| T-26–T-30 | Demo reset, warm-up, the missing docs, film end-card fix and re-render, repo tidy |
| T-12 | Structured logs, metrics endpoint |

### B · I can do it, but need something from you
| Item | Needs |
|---|---|
| T-01, T-02 (answer metrics), T-25 | A running endpoint for the real models (or a GPU machine) |
| T-03, T-04 | A licensed drug database and guideline content; a pharmacist and clinical reviewer to sign off |
| T-13 | Doctors' registration data and the clinic's print details |
| T-14 (ABDM) | ABDM sandbox credentials and a decision to pursue it |
| T-17 | Model download size and (ideally) a GPU |
| T-19 | Translation review by native-speaking clinicians |
| T-09 | A representative server to test on |
| T-28 | Your decision on credits wording; the recorded voiceover and music |

### C · Cannot be done in code
Regulatory classification, certifications, privacy and legal documents, clinical validation and ethics
approvals, insurance, trademarks, support contracts, training. See [PENDING_MANAGEMENT.md](PENDING_MANAGEMENT.md).

### Suggested order
1. **Hardening release** (group A): T-06, T-05, T-08, T-10, T-11 — makes the build safe to put in front of a pilot site.
2. **Measure it** : T-02 harness now; T-01 as soon as a model endpoint exists.
3. **Content**: T-03 and T-04 in parallel with the clinical reviewer.
4. **Pilot features**: T-13, T-15, T-16, T-20.
5. **Integrations and languages**: T-14, T-19.
