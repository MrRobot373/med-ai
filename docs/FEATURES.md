# GMS Clinical AI — Features

What the product does today, how each part works, and the technology behind it. Everything here
was checked against the code in this repository (version 2.0.0). What is **not** done, and what stands between this
and a product that can be sold, is in [PRODUCT_READINESS.md](PRODUCT_READINESS.md),
[PENDING_TECHNICAL.md](PENDING_TECHNICAL.md) and [PENDING_MANAGEMENT.md](PENDING_MANAGEMENT.md).

**Status key**

| Mark | Meaning |
|---|---|
| ✅ | Built and covered by automated tests |
| 🟡 | Built and working, but limited (the limit is stated) |
| 🧪 | Built, but only exercised with the test AI so far (never run against a real clinical model) |

**One-line summary.** GMS Clinical AI is a private, on-premise co-pilot for a doctor's clinic. It reads every
report a patient has, keeps one organised chart, checks prescriptions against the patient as they are written,
and answers questions with citations to the exact source. The doctor always decides.

---

## Contents

1. [Technology stack](#1-technology-stack)
2. [Accounts, roles and security](#2-accounts-roles-and-security)
3. [Front desk](#3-front-desk)
4. [The doctor's day](#4-the-doctors-day)
5. [Patient chart](#5-patient-chart)
6. [Report ingestion](#6-report-ingestion)
7. [Lab results and trends](#7-lab-results-and-trends)
8. [Clinical scores](#8-clinical-scores)
9. [Consultation co-pilot](#9-consultation-co-pilot)
10. [Prescription safety engine and India formulary](#10-prescription-safety-engine-and-india-formulary)
11. [Investigations: orders and automatic matching](#11-investigations-orders-and-automatic-matching)
12. [Ask the chart (assistant) and retrieval](#12-ask-the-chart-assistant-and-retrieval)
13. [Clinical tools](#13-clinical-tools)
14. [Image and scan handling](#14-image-and-scan-handling)
15. [Knowledge library](#15-knowledge-library)
16. [AI providers and runtime settings](#16-ai-providers-and-runtime-settings)
17. [Administration](#17-administration)
18. [Appearance and white-labelling](#18-appearance-and-white-labelling)
19. [Demo data, test AI and tooling](#19-demo-data-test-ai-and-tooling)
20. [Deployment](#20-deployment)
21. [Quality: tests and checks](#21-quality-tests-and-checks)

---

## 1. Technology stack

| Layer | Technology | Why |
|---|---|---|
| Backend | Python 3.12, **FastAPI**, Pydantic 2, Uvicorn | Typed API, streaming responses, automatic validation |
| Database | **SQLite** (WAL mode, foreign keys on) via **SQLAlchemy 2** + **Alembic** migrations (3 so far); any SQLAlchemy URL via `DATABASE_URL` | Zero-ops for a clinic; one file to back up |
| Full-text search | SQLite **FTS5** (BM25) | Exact terms: drug names, lab codes, ICD codes |
| Vector search | **Qdrant** — embedded (local folder) or a Qdrant server | Meaning-based retrieval, no external service by default |
| AI providers | **Ollama** (native) or any **OpenAI-compatible** endpoint (LM Studio, vLLM, llama.cpp, OpenAI, OpenRouter, Groq, Together) | Bring your own models |
| Embeddings | Ollama, OpenAI-compatible, or in-process `sentence-transformers` | Choice of local or hosted |
| Reranking | none, in-process cross-encoder, remote reranker (TEI/llama.cpp shape) or the main LLM as judge | Optional quality step |
| Clinical reasoning model | Separate, configurable model slot (default `medgemma:27b`) | Dose and medical reasoning on a medical model |
| Document parsing | **PyMuPDF** (PDF text + page images), python-docx, openpyxl, CSV/TXT/MD/JSON, **Pillow**, **pydicom** | PDFs, Office files, images, DICOM |
| Security | **argon2** password hashes, **Fernet** (AES) for stored API keys, HttpOnly cookies | See §2 |
| Frontend | **React 18**, **Vite**, **TypeScript**, **Tailwind CSS 3**, **Radix UI**, React Router 7, TanStack Query, Recharts, cmdk, Sonner, Lucide icons | Fast, accessible, themeable |
| Delivery | One Docker image (FastAPI serves the built React app), `docker-compose` with optional Qdrant, Ollama and test-AI profiles | One thing to run |
| Tests | pytest (96), Vitest (8), Playwright (6) | See §21 |

Architecture, in one picture:

```
React app ──► FastAPI ──► SQLite (records, chunks, FTS5, audit, settings)
                 │   └──► Qdrant (vectors)
   ┌─────────────┼───────────────────────────┐
 Ingestion   Hybrid retrieval            Generation
 parse · OCR  dense + BM25 → fusion →     prompt with labelled evidence →
 identity     rerank → de-dup → budget    stream → validate citations
 lab extract         └────────────┬─────────┘
                                  ▼
            Provider layer (changeable at runtime): LLM · vision · clinical model · embeddings · reranker
```

---

## 2. Accounts, roles and security

| Feature | How it works | Technology | Status |
|---|---|---|---|
| Sign-in / sign-out | Email + password; a random session token is stored hashed in the database and sent as an **HttpOnly, SameSite=Lax** cookie (`Secure` when HTTPS is enabled). | argon2, `secrets`, FastAPI cookies | ✅ |
| Sliding session timeout | Each request extends the session; default 8 hours, set by the admin. | `user_sessions` table | ✅ |
| Four roles | **Admin** (everything), **Clinician** (clinical work + AI), **Viewer** (read-only; AI optional by setting), **Front desk** (registration, today's list, uploads — never clinical content, never AI). Enforced on the server per endpoint; the UI hides what a role cannot use. | `require_roles` dependencies | ✅ |
| Sign-in throttling | Sliding window per email + IP (default 8 attempts per 10 minutes, configurable); excess attempts get HTTP 429. Failed sign-ins are audited. | in-memory limiter | 🟡 per-process only |
| User management | Admin creates, edits, deactivates users and resets passwords; users change their own password and see their sessions. | `/users`, `/auth/*` | ✅ |
| Secrets at rest | AI endpoint API keys are encrypted with a key derived from `APP_SECRET_KEY` and never sent back to the browser (shown masked). | Fernet | ✅ |
| Patient isolation | Every patient-scoped search is filtered by that patient's id in both indexes and re-checked in code; an unscoped patient search is refused. | Qdrant filters, SQL | ✅ |
| Upload safety | Size limit (default 40 MB), extension **and** magic-byte check, safe file names, SHA-256 duplicate rejection. | `verify_magic`, sha256 | ✅ |
| Audit log | 35 kinds of action recorded (sign-in, patient view, document view/upload, prescription finalise, order result, AI run, settings change…) with user, patient, IP and outcome; searchable, filterable, CSV export. | `audit_logs` table | ✅ |

---

## 3. Front desk

| Feature | How it works | Status |
|---|---|---|
| Today's list | Shows the day's appointments with status (expected → waiting → seen / cancelled); one click marks a patient as arrived. | ✅ |
| Simple appointments | Add a patient to today's list with a time and reason; edit, cancel. (No calendar, slots or reminders by design.) | ✅ |
| Register patients | Name, date of birth, sex, phone, address, blood group, tags; a unique clinic ID (UHID/MRN). | ✅ |
| Upload reports | Drop PDFs, photos, scans or DICOM against a patient; files are read, dated, sorted and matched to open orders automatically. Doctors can upload too. | ✅ |
| Filed documents only | The front desk sees the list of filed documents and their status — not their contents, results or AI. The API refuses clinical endpoints (HTTP 403). | ✅ |

Technology: FastAPI routers (`care.py`, `patients.py`, `documents.py`), role guard `StaffUser`, React pages in `features/frontdesk`.

---

## 4. The doctor's day

| Feature | How it works | Status |
|---|---|---|
| Clinical dashboard | Greeting with date, open-item count and a workload bar; **Today's patients** (time, name, age/sex, reason, problems, "N result back", "N abnormal", "Brief ready", Open/Continue); abnormal-results and most-urgent tiles; patients needing attention; a review queue shown in the report viewer. | ✅ |
| Inbox | One work queue, urgent first: results back for ordered tests, suspected wrong-patient documents, abnormal labs, overdue follow-ups, failed documents, AI drafts awaiting review. Filter by type, acknowledge, open the chart. | ✅ |
| Global search and shortcuts | ⌘K / Ctrl K command palette (patients, pages, actions); `G` + letter navigation. | ✅ |

Technology: aggregate endpoints (`/dashboard`, `/today`, `/inbox`) computed in SQL from the chart; React Query for live updates.

---

## 5. Patient chart

One workspace per patient with a header that never scrolls away: name, age/sex, UHID, DOB, blood group, **allergies first** (red; "Allergies not documented" in amber when none), and active problems.

| Tab | What it holds | Status |
|---|---|---|
| Overview | Report viewer, patient-specific scores, now-vs-previous value comparison with a plain-language change sentence, key areas of concern (range bars), care overview (action plan / medications / scores / problems), AI case summary, recent encounters | ✅ (summary 🧪) |
| Consultation | The doctor's working screen (§9) | ✅ (AI parts 🧪) |
| Timeline | Visits, prescriptions, reports and results in date order, filterable | ✅ |
| Reports & imaging | Viewer, thumbnails, upload, filter, document details and extracted values | ✅ |
| Results | Every test with trend chart, reference range as stated by the source, source link per value | ✅ |
| Orders, Prescriptions | Investigations and prescriptions with their checks and review status | ✅ |
| Medications, Problems, Encounters | Editable lists; problems carry an optional ICD-10 code | ✅ |
| Assistant, Clinical tools | Ask the chart; run structured tools (§12–13) | 🧪 |

Technology: SQLAlchemy models (`patients`, `encounters`, `conditions`, `allergies`, `medications`, `observations`, `documents`), one overview endpoint, TanStack Query caching, Radix tabs.

---

## 6. Report ingestion

When a file is uploaded the server runs one pipeline, in the background so the screen stays responsive:

```
upload → size / type / magic check → duplicate check (SHA-256)
       → parse (text, tables, page images) → [scanned pages → vision model transcription]
       → identity check against the chart → document kind + date guess
       → lab-value extraction → match to open orders → chunk → embed → index (vector + BM25)
```

| Step | How it works | Technology | Status |
|---|---|---|---|
| Parsing | PDF text is rebuilt from word positions: words are grouped by baseline and wide gaps become column separators, which keeps table values intact (a past bug turned `12.9` into `129`). DOCX, XLSX, CSV, TXT, MD, JSON, PNG/JPG/WEBP, DICOM. | PyMuPDF, python-docx, openpyxl | ✅ |
| Scanned pages and photos | Page images are sent to the vision model for transcription; image-only files get a description. | vision model slot | 🧪 |
| **Identity check** | Looks for the patient's UHID, name and other labels in the header. A different name or ID → the document is **quarantined**: no values are extracted, it is excluded from AI answers, and an urgent inbox item is raised until a clinician confirms. A shared surname alone does not pass (the given name must match). Outside labs' own patient numbers are tolerated when the name matches. | regex + rules (`identity.py`) | ✅ |
| Duplicate detection | Identical file content (SHA-256) for the same patient is refused with the existing title. | hashlib | ✅ |
| Kind and date | Guesses lab report / imaging / ECG / discharge summary / prescription… and the report date from the text. | rules | ✅ |
| Chunking | ~550-token chunks with 80-token overlap, page numbers kept for citations. | tokenizer estimate | ✅ |
| Indexing | Each chunk is embedded into Qdrant and added to an FTS5 table, tagged with patient and document. | Qdrant, SQLite FTS5 | ✅ |
| Reprocess | One click re-runs the pipeline for a document or re-indexes the library when the embedding model changes. | `/documents/{id}/reprocess`, `/reindex` | ✅ |

---

## 7. Lab results and trends

| Feature | How it works | Status |
|---|---|---|
| Value extraction | A registry of ~50 common tests (HbA1c, creatinine, eGFR, UACR, electrolytes, CBC, lipids, LFTs, TSH, BNP, troponin, vitamins, vitals, echo EF…) with aliases. Reads table rows (`Serum Creatinine \| 1.62 \| H \| mg/dL \| 0.50–1.10`) and inline text (`eGFR by CKD-EPI 2021: 36 mL/min`). Each value keeps its page and the quoted source line. | ✅ |
| **Reference ranges are never invented** | A value is flagged high/low only from the range or H/L marker printed in the document itself. No built-in ranges. | ✅ |
| Trends | Per-test chart with the source's range as a shaded band, flagged points in red, change since previous. | Recharts | ✅ |
| Manual entry and acknowledge | Doctors can add a value by hand (marked "manual") and acknowledge abnormal results so the inbox clears. | ✅ |
| Deterministic comparison | Previous vs current values are subtracted by code, never by the AI. | ✅ |

---

## 8. Clinical scores

Only the scores that apply to *this* patient are shown, computed by code from documented data, with every input and its source listed. Missing inputs are named, never assumed.

| Score | Inputs |
|---|---|
| CKD stage (KDIGO G and A category, risk) | eGFR, UACR |
| CHA₂DS₂-VASc | age, sex, heart failure, hypertension, diabetes, stroke, vascular disease |
| Glycaemic control | HbA1c against the commonly used target |
| Metformin renal dosing | eGFR, current metformin dose |
| Apixaban dose criteria | age, weight, creatinine |

Technology: `clinical/scores.py`, pure Python. Status ✅ (unit-tested). Clinical sign-off pending (see management file).

---

## 9. Consultation co-pilot

The core of the product. Everything is saved as the doctor works and feeds the next visit.

| Step | What the doctor sees | How it works | Status |
|---|---|---|---|
| Start | On today's list → **Continue/Start consultation** | Creates an encounter linked to the appointment | ✅ |
| **Pre-visit brief** | What happened last time, results since then, reports and tests pending, and AI-suggested questions to ask, things to watch, and what to consider | Facts are computed from the chart in code (`previsit_facts`); the clinical model turns them into questions. Stored as a draft AI run. | ✅ facts / 🧪 AI text |
| Notes and vitals | Chief complaint, history, vitals (BP, pulse, temperature, SpO₂, weight), examination, diagnosis chips (optional "add to problem list"), assessment, plan | Autosave | ✅ |
| **Diagnosis second look** | A verdict (consistent / partly / inconsistent / insufficient), what supports and what argues against it, other diagnoses to consider, red flags, tests that would help | Clinical model, JSON-structured | 🧪 |
| **Prescription** | Medicine lines with live safety findings (§10), advice, follow-up, then the AI **clinical review** (dose assessment per line, fit with diagnosis, monitoring, counselling points) | Rule engine on every keystroke; clinical model for the second opinion | ✅ rules / 🧪 review |
| Finalise | Critical findings need a recorded reason to proceed (kept in the audit log) | Server-enforced | ✅ |
| Print | A4 prescription on the clinic letterhead (logo, name, doctor, patient, ℞ table with generic composition, advice, follow-up, signature line) | HTML print view | ✅ |
| Complete | Closes the visit and adds the diagnoses the doctor ticked to the problem list. (Finalising a prescription adds its medicines to the medication list.) | ✅ |

---

## 10. Prescription safety engine and India formulary

A **deterministic rules engine** (no AI) runs on every keystroke and returns findings in three severities: **critical** ("Stop & check"), **caution**, **info**. Rules never block the doctor; critical ones require a recorded reason.

What it checks, per medicine line:

| Check | Source of the rule |
|---|---|
| Drug recognised (brand or generic; combinations such as Pan-D = pantoprazole + domperidone, Septran DS = sulfamethoxazole + trimethoprim) | formulary products and synonyms |
| Dose per day against the adult maximum (and a usual-dose floor), frequency and course length; weekly-only drugs | generic dose limits, brand default frequency |
| **Kidney**: avoid / reduce below eGFR thresholds | patient eGFR: the reported value if newer than the creatinine, otherwise calculated with **CKD-EPI 2021** from creatinine, age and sex |
| **Liver**: caution / avoid in hepatic impairment | problem list + ALT/AST/bilirubin |
| **Older adults** (≥ 65): Beers 2023 criteria | formulary |
| Pregnancy, children (< 12) | formulary + age/sex/pregnancy problem |
| **Allergies**: documented allergen, its drug group and cross-reactivity (e.g. sulfonamide, penicillin → cephalosporin) | 13 allergy groups |
| **Drug–drug interactions** against the patient's current medicines and the same prescription | 32 interaction rules |
| Duplicate therapy (same class twice) | 24 duplicate classes |
| Problems (e.g. BPH with anticholinergics; GI bleeding risk with NSAID + aspirin) and labs (e.g. potassium with RAAS blockers) | condition and lab rules |

Each finding says *what, why and the patient fact behind it* ("Allergy: Sulfa drugs — documented Sulfa drugs allergy (reaction: itchy rash, 2019, after Septran)"). The prescription header shows what it was checked against: age, weight, eGFR, allergies, number of current medicines.

**The formulary today:** 114 generics, 186 brand products and combinations, 32 interactions, 13 allergy groups, 24 duplicate classes, 36 synonyms, version `2026.10`, region `IN`. Regions are data files (`formulary/data/in.json`), so another country is a new file. Optional reference photos of a generic come from Wikimedia Commons (lookup by generic name only; cached; can be switched off for offline use).

Technology: `formulary/catalog.py`, `dosing.py`, `facts.py`, `engine.py`; search endpoint `/formulary/search`. Status ✅ for the engine (tested); 🟡 for content size (see technical file).

---

## 11. Investigations: orders and automatic matching

| Feature | How it works | Status |
|---|---|---|
| Order a test | A name, the **question it should answer**, routine/urgent; quick-pick chips for common tests | ✅ |
| **Automatic matching** | When a report is uploaded (by anyone), its text is matched to the patient's open orders using test groups (e.g. KFT, lipid profile, USG abdomen, TMT, ECG, chest X-ray) and body region. A report can only answer an order placed before it (one day of slack). The order flips to **Result back — review** and appears in the doctor's inbox. | ✅ |
| Read against the question | The clinical model reads the report against why the test was ordered: does it answer the question, key findings, abnormal items, change from the previous, next steps to consider, urgency, and a plain-language explanation for the patient. | 🧪 |
| Reviewed | The doctor adds a note and marks the result reviewed; the note is kept for future visits. | ✅ |

---

## 12. Ask the chart (assistant) and retrieval

A streaming chat that answers **only from the evidence it is given**, with a citation on every statement.

**Conversation scopes:** one patient's chart, the knowledge library only, or both. A patient-scoped chat can only ever see that patient.

**Retrieval pipeline** (every stage timed and stored for the "Why this answer" panel):

1. **Dense search** — query embedding against Qdrant (default top 30).
2. **Lexical search** — SQLite FTS5 BM25 (default top 30) for exact terms.
3. **Fusion** — Reciprocal Rank Fusion (k = 60) with adjustable weights.
4. **Reranking** (optional) — cross-encoder, remote reranker or LLM judge; off by default.
5. **De-duplication** of near-identical chunks.
6. **Token budget** — the context is cut to a budget (default 6,000 tokens).
7. **Structured record** — the chart's problems, allergies, medicines and latest results are added as source `R`.

**Generation:** the prompt labels evidence `P1…` (patient documents), `K1…` (library), `R` (record) and tells the model that evidence is data, not instructions. Tokens stream to the browser over server-sent events. Afterwards the answer is **validated**: citations that do not match a real source are stripped and reported; a citation-coverage figure is stored. If the evidence is insufficient, the assistant **abstains** instead of guessing — without calling the model at all when nothing was retrieved.

| Feature | Status |
|---|---|
| Streaming answers, citation chips, evidence panel with the quoted excerpt and "Open document" | ✅ |
| "Why this answer": stage timings, scores, parameters used, what was dropped | ✅ |
| Abstention, stripping of invalid citations, patient isolation, LLM-outage error event | ✅ (tested) |
| Stop generation (client abort), conversation history, rename, delete, thumbs up/down feedback with notes | ✅ |
| Suggested starter questions per scope | ✅ |
| Answer quality with a real model | 🧪 |

Technology: `rag/` (retrieve, indexing, lexical, vector_store), `services/chat.py`, `clinical/citations.py`, SSE (`text/event-stream`), React `ChatView` + `EvidencePanel`.

---

## 13. Clinical tools

Seven structured tools, each returning validated JSON that the screen renders as a card. Every output is saved as a **draft** AI run that the clinician accepts or rejects (audited).

| Tool | What it produces |
|---|---|
| Case summary | One-liner, active problems, key findings, medications, recent changes, gaps, follow-up considerations — each with citations |
| SOAP note | Subjective / objective / assessment / plan from the encounter, plus missing information |
| Entity extraction | Problems, medications, allergies, labs, procedures, symptoms, follow-up from a document |
| Differential support | Considerations with supporting/against evidence and suggested evaluation, plus red flags |
| Guideline Q&A | Answer from the knowledge library with citations, or an explicit abstention |
| Report comparison | New, resolved, worsened, improved and unchanged findings; **numeric changes are computed by code** and handed to the model |
| Medication reconciliation | Chart medicines vs a document's medicines: only in chart, only in document, dose differences |

Technology: `services/tools.py`, JSON-mode prompts with output validation, `ai_runs` table (model, time, review status). Status 🧪 (works with the test AI; quality with real models unmeasured).

---

## 14. Image and scan handling

| Feature | How it works | Status |
|---|---|---|
| Viewer | Large viewer for PDFs, photos, ECGs and DICOM with thumbnails, paging, zoom, full screen; imaging uses a dark stage. | ✅ |
| **DICOM** | Reads headers (modality, study/series description, patient fields, dates), applies the modality LUT (so CT is in Hounsfield units) and the window/level, renders a PNG preview; single-frame and multi-frame (middle frame). | pydicom, Pillow | 🟡 one frame shown |
| Image analysis | A vision model returns image type, quality, observations, measurements, text found, possible considerations and limitations, with a recommended review. | vision model slot | 🧪 |
| Scanned documents | Transcribed page by page by the vision model before indexing | 🧪 |

---

## 15. Knowledge library

| Feature | How it works | Status |
|---|---|---|
| Domains | Cardiology, nephrology, endocrinology, haematology, ophthalmology, pulmonology (starter packs) plus a suggested taxonomy of more | ✅ |
| Upload and manage | Admins add guidelines/protocols (PDF, DOCX, MD…) with domain, source organisation, version and date; tags and facets; search | ✅ |
| **Versioning** | Several versions of a guideline can exist; one is **active** and only active versions are retrieved. | ✅ |
| Re-index | One click rebuilds the library index (needed after changing the embedding model); the settings page shows when a rebuild is required. | ✅ |
| Content | 10 short starter notes, labelled as demo summaries | 🟡 placeholder content |

---

## 16. AI providers and runtime settings

Everything about the AI is changed **in the app**, takes effect on the next request, and needs no restart.

| Slot | Purpose | Choices |
|---|---|---|
| Language model | Chat, summaries, tools | Ollama or any OpenAI-compatible endpoint; temperature, output tokens, context window, timeout, concurrency, reasoning on/off |
| Vision model | Scanned pages, photos, image analysis | Same endpoints, or reuse the language model |
| Clinical reasoning model | Pre-visit brief, diagnosis second look, dose review, reading results | Default `medgemma:27b`; or reuse the language model |
| Embeddings | Search index | Ollama, OpenAI-compatible or in-process |
| Reranker | Optional ranking step | none · local cross-encoder · remote · LLM judge |
| Retrieval | Profiles (fast / balanced / thorough / custom), top-k per stage, RRF constant, weights, chunk size and overlap, context budget, history turns | |
| Vector store | Embedded folder or a Qdrant server | |
| Medicines | Region, reference photos on/off | |
| Security | Session timeout; whether viewers may use AI | |

Each section has **Test** (runs against the unsaved values: connection, model present, a real call) and **Save**. A warning appears when an endpoint is not local, because patient context would leave the clinic. Retrieval can be tried in a **playground** that shows every stage. Settings changed by another process (for example the command line) are picked up within seconds.

Technology: Pydantic config models stored as one JSON row (API keys encrypted inside it); provider classes in `ai/` (`llm.py`, `embeddings.py`, `reranker.py`, `registry.py`); async `httpx`; automatic one-time retry when an endpoint rejects the JSON-mode or `think` switch.

---

## 17. Administration

| Feature | Detail | Status |
|---|---|---|
| Users and roles | Create, edit, deactivate, reset password | ✅ |
| Audit log | Filter by user, action, patient, date; CSV export | ✅ |
| Service health | A live status dot for database, vector store and each AI slot; a detail page with latency | ✅ |
| Branding | Product name, organisation, logo, tagline, default accent and theme, disclaimer, sign-in message | ✅ |
| Patient export | A plain-text clinical summary of the chart, downloadable (audited) | 🟡 text only; no standard exchange format (FHIR) |
| Feedback review | Thumbs and notes on assistant answers | ✅ |

---

## 18. Appearance and white-labelling

Per-user light / dark / system theme, **nine accent presets or any hex** (the whole palette — soft fills, navy emphasis, readable text — is derived from it), comfortable/compact density, three corner styles, three text sizes, system or Inter font, high-contrast mode, reduced motion, sidebar state and landing page. The full visual language is in [DESIGN.md](DESIGN.md).

---

## 19. Demo data, test AI and tooling

| Item | What it is |
|---|---|
| **Life Care Medico demo clinic** | Four staff accounts and **15 patients** (UHIDs `LCM-10231…10245`), 83 documents: lab reports, X-ray, ultrasound, CT and MRI (some as DICOM), ECGs, discharge summaries, outside prescriptions. The reports and the people are fictional; the images are real, de-identified images from openly licensed datasets (credits in each folder's `IMAGE_SOURCES.md`). Five patients are booked on today's list. One folder contains a report belonging to another patient to exercise the quarantine. |
| Patient-file generator | `scripts/patient_files` builds the folders: letterheads, tables, burned-in image headers, DICOM files, ECG printouts, with embedded open-licence fonts. |
| Seed command | `python -m app.seed demo | today | knowledge | use-mock-ai | reprocess` |
| **Test AI** | `app.devtools.mock_ai`: an OpenAI-compatible server that assembles answers from the evidence it is given. Lets the whole product run without a GPU. **Not a model; never for clinical use.** `MOCK_AI_PLAIN=1` drops its "[mock]" markers for screen recordings. |
| Product film | `video/`: scripts that drive the real app and a HyperFrames project that renders a 3:17 film, plus the timed voiceover script. |

---

## 19b. New in version 3.0 — running a clinic on it

- **Prescription speed**: templates (private or clinic-shared), ★ favourite medicines with their usual dose, most-used medicines, "same as last visit". They fill the form; every line is still safety-checked.
- **Print**: server-made PDFs on the clinic's letterhead (paper size, text size, accent colour, logo, contact details, footer) with a live preview; the doctor's registration number, council, qualifications and signature image; signed **QR verification** page.
- **Letters**: medical and fitness certificates, referral letters (pre-filled from the chart), and a plain-language **visit summary for the patient** — numbered without gaps per year, immutable once issued, voidable with a reason, verifiable.
- **Branches**: several sites in one installation, each with its own letterhead details, day list and staff; patients shared.
- **Patients**: automatic MRN numbers, **duplicate warning** at registration, duplicate review and **audited merge** (records and search vectors move together), Excel/CSV **import** with column mapping and per-row checks.
- **Operations**: daily encrypted **backups** with a verify step and CLI restore; off-site copy script; crash recovery for half-processed reports; a `doctor` and `status` command.
- **Install and update**: `install.sh` (preflight, keys, HTTPS proxy), `update.sh` with automatic rollback, `rollback.sh`, offline bundle builder.
- **Licensing**: signed offline licences bound to the installation; seat and branch limits; never blocks patient care; usage report.
- **Security**: two-step verification (TOTP + recovery codes), lockout, password policy, security headers and CSRF, encrypted uploads, ClamAV, tamper-evident audit chain, production start-up guards, security checklist.
- **Integration**: scoped API keys, partner API (prescriptions, visits, patients, "dispensed"), signed webhooks with retry, spreadsheet exports.
- **Clinical governance**: fingerprint-bound sign-off by a named clinical lead and pharmacist; 27 reviewable clinical test cases; evaluation harness (`python -m app.cli eval`) measuring lab-extraction, retrieval, abstention and grounding.

## 20. Deployment

| Option | Detail |
|---|---|
| Docker (recommended) | One image; `docker compose up -d`; profiles for `qdrant`, `ollama`, `mock` |
| Directly | `scripts/setup.sh`, `scripts/demo.sh [--mock]`, or a systemd unit |
| Production-style settings | `APP_ENV`, `APP_SECRET_KEY`, `COOKIE_SECURE`, `DATABASE_URL`, `UPLOAD_MAX_MB`; non-root container user; health check |
| Guide | [DEPLOY_LOCAL.md](DEPLOY_LOCAL.md) — tested end to end with Docker (build, seed, browser tests) |

---

## 21. Quality: tests and checks

| Suite | Count | Covers |
|---|---|---|
| Backend (pytest) | **96** | auth and roles, patient isolation, ingestion (PDF tables, lab extraction, identity, duplicates), DICOM, scores, formulary rules, orders and matching, consultation APIs, retrieval and chat (citations, abstention, outage), provider adapters, settings |
| Frontend unit (Vitest) | 8 | utilities, badges, markdown |
| Browser end-to-end (Playwright) | 6 | doctor flow, allergy stop in a live prescription, front desk limits, wrong-patient quarantine, admin model test, viewer read-only |
| Static checks | — | Ruff (lint + format), TypeScript strict, ESLint |

All of the above pass at the time of writing, including against the Docker deployment.
