# Architecture & Build Roadmap

Full requirements live in `MASTER BUILD PROMPT — GMS Local Multimodal Clinical RAG &
Decision-Support Platform.md` at the repo root. This document tracks what's actually
built, phase by phase, against that spec's §132 sequence — updated as each phase lands.

## System shape (target — see spec §13/§143)

```text
GMS CLINICAL AI
        |
        +-- Authentication / Authorization        (Phase 03)
        +-- Patient Management                     (Phase 04)
        +-- Document Ingestion                      (Phase 05)
        +-- Structured Clinical Data / Trends        (Phase 06)
        +-- Local Hybrid RAG (dense+BM25+RRF+rerank) (Phase 07)
        +-- Clinical Chat / Streaming / Citations    (Phase 08)
        +-- Vision                                   (Phase 09)
        +-- Clinical Modules (SOAP/differential/etc.) (Phase 10)
        +-- Web Research (de-identified)              (Phase 11)
        +-- Knowledge Administration                  (Phase 12)
        +-- Audit & Feedback                          (Phase 13)
        +-- Demo System (seed data, one-click start)  (Phase 14)
        +-- Evaluation Suite                          (Phase 15)
        +-- Final Validation + Completion Report      (Phase 16)
```

## Phase status

| Phase | Scope | Status |
|---|---|---|
| 01 | Foundation: repo scaffold, backend/frontend skeleton, SQLite+Alembic, Qdrant (Docker), Ollama integration, real health checks | **Done** |
| 02 | Screenshot-matched UI shell (full nav, dashboard cards, responsive layout) | **Done** |
| 03 | Authentication: login/logout, roles, sessions, protected routes | **Done** |
| 04 | Patient system: CRUD, search, workspace, encounters, conditions, allergies, medications, timeline | **Done** |
| 05 | Report ingestion: upload, PDF/DOCX/XLSX/image parsing, OCR, identity checking, ingestion jobs | **Done** |
| 06 | Structured clinical data: lab extraction, trend engine, medication reconciliation, change engine | **Done** |
| 07 | Local RAG core: embeddings, Qdrant collections, dense+BM25 retrieval, RRF fusion, reranking, dedup | **Done** |
| 08 | Clinical chat: conversations, streaming, evidence panel, citation/grounding validation | **Done** |
| 09 | Vision: image upload, structured extraction, image-to-RAG, comparison | **Done** |
| 10 | Clinical modules: summary, SOAP, entity extraction, guideline Q&A, differential support, report comparison | **Done** |
| 11 | Web research: Research Mode, de-identification, PubMed/FDA, optional SearXNG, web cache | **Done** |
| 12 | Knowledge administration: upload, metadata, versions, active documents, reindex, archive, ingestion monitoring | **Done** |
| 13 | Audit & feedback: audit log UI, feedback capture, provenance drawer | Not started |
| 14 | Demo system: synthetic patients (ophthalmology domain — see `data/`), demo scenarios, start/reset scripts, model warm-up | Not started |
| 15 | RAG evaluation suite: retrieval/citation/groundedness/hallucination/latency metrics | Not started |
| 16 | Final validation: full test suite, security review, UI review vs. screenshots, `FINAL_COMPLETION_REPORT.md` | Not started |

## Phase 01 — what exists right now

```text
backend/app/
  main.py                     FastAPI app + CORS + router registration
  config/settings.py          All tunables (model names, RAG K-values, profiles) via env
  db/base.py, db/session.py   SQLAlchemy 2.x engine/session, FK enforcement, health check
  models/user.py, session.py  users + sessions tables (auth storage lands Phase 03)
  integrations/               Real Ollama/Qdrant/embedding/reranker health checks
  api/health.py                GET /api/health, /health/ollama, /health/qdrant, /health/models
  schemas/health.py            Response models for the above

backend/migrations/           Alembic env wired to app.config.settings.DATABASE_URL
backend/tests/                pytest: DB reachability, health endpoint shape, model-name matching

docker-compose.yml            Qdrant (pinned v1.19.0, persistent volume) + optional SearXNG
scripts/health_check.py       Same checks as /api/health, runnable standalone
start-demo.bat / stop-demo.bat / health-check.bat   Phase 01 versions (full §86 sequence lands with later phases)
```

## Phase 02 — what exists right now

```text
frontend/src/
  layouts/AppShell.tsx         Nav per spec §19, brand mark, Local Mode badge, live status chip
  pages/Overview/               Full dashboard: hero + illustration, AI Capabilities grid,
                                 How It Works steps, clinical-activity snapshot (honest
                                 "not wired up yet" state — no fabricated numbers per §22),
                                 System Status (real), trust trio, CDS disclaimer
  pages/NotYetBuilt.tsx          Explicit "not built yet, Phase N" placeholder used by every
                                 nav route without a real feature behind it yet
  components/                   Card, IconBadge, CapabilityCard, HowItWorksStep,
                                 HeroIllustration (original inline SVG), SystemStatusPanel,
                                 DashboardSnapshot, StatusChip — reusable primitives, not
                                 one-off markup per page
  api/client.ts, api/health.ts  Typed fetch wrapper + TanStack Query health hook

Login page (spec §21) is intentionally NOT built in Phase 02, unlike the spec's literal
grouping — a form with a submit button that can't actually authenticate yet (no backend
auth endpoint until Phase 03) would be exactly the "dummy button" the spec prohibits. It
ships in Phase 03 as one functional unit: UI + real POST /api/auth/login together.

Every capability card and nav item routes somewhere real — either the live Overview page
or a NotYetBuilt screen naming the phase that will complete it. Verified via Playwright
screenshots at 1366×768 / 1440×900 / 1920×1080 (no layout breakage, no console errors) and
a scripted click-through (capability card → correct NotYetBuilt page, correct nav
highlighting).
```

## Phase 03 — what exists right now

```text
backend/app/
  auth/security.py       Argon2id password hashing; session tokens are a separate
                          256-bit random value, only its SHA-256 lives in the DB
  auth/service.py         authenticate_user / create_session / get_user_by_session_token /
                           revoke_session — framework-agnostic, no FastAPI imports
  auth/dependencies.py    get_current_user (cookie → session → user), require_role(*roles)
  auth/rate_limit.py      In-process sliding-window login limiter (documented single-
                           process limitation — no Redis, per spec §135)
  api/deps.py              Shared Annotated[X, Depends(y)] aliases (DbDep, SettingsDep)
  api/auth.py               POST /api/auth/login, /logout, GET /me
  schemas/auth.py           LoginRequest (deliberately NOT EmailStr — see regression
                             note below), UserOut

scripts/seed_demo.py     Creates admin/doctor/viewer accounts. Passwords are never
                          hardcoded: read from env or randomly generated, printed once,
                          saved to data/sqlite/.demo_credentials.txt (gitignored).
                          Idempotent — safe to re-run.

frontend/src/
  api/auth.ts              useMe / useLogin / useLogout (TanStack Query)
  pages/Login/               Matches spec §21; identical error message for wrong-
                              password/unknown-email/inactive-account (anti-enumeration)
  components/RequireAuth.tsx  Route guard — 401 from /me is the "logged out" signal,
                               not an exceptional error
  components/UserMenu.tsx     Real name/email/role + Logout; no Profile/Preferences/
                               System Information items since those pages don't exist
  router.tsx                  /login public; everything else behind RequireAuth

Two real bugs were caught during live verification (not just unit tests) and fixed:
1. Backend: pydantic's `EmailStr` rejects `.local`/other reserved TLDs, which broke
   login for the very accounts scripts/seed_demo.py creates, and some configurations
   perform live DNS/MX lookups — wrong for an app required to work offline (§136).
   Replaced with a light shape check that doesn't touch the network.
2. Frontend: `apiFetch` assumed FastAPI's `detail` field is always a string; its
   automatic 422 validation errors return an array, which rendered as the literal
   text "[object Object]". Fixed to flatten either shape into a readable message.
Both have regression tests (backend pytest + frontend vitest) so they can't reappear
silently.

Verified end-to-end with Playwright against the real running app: unauthenticated
redirect → invalid-credentials error → successful login → user menu → logout → session
genuinely revoked server-side (reloading a protected route redirects again, not just a
client-side flag).
```

## Phase 04 — what exists right now

```text
backend/app/
  models/patient.py, encounter.py, condition.py, allergy.py, medication.py
                            `source_report_id` on Condition deliberately omitted until
                            Phase 05 adds `reports` (avoids a dangling/unconstrained FK)
  models/enums.py            Shared VerificationStatus (confirmed/provisional/unconfirmed)
  schemas/patient.py, encounter.py, condition.py, allergy.py, medication.py, timeline.py
  services/patients.py       search/create/update/archive; every query scoped by
                              patient_id — the same discipline Phase 07 RAG isolation needs
  services/encounters.py     Sequential per-patient encounter numbering (MRN-ENCnnn)
  services/clinical.py       Conditions/allergies/medications. Medications are append-
                              only (spec §36): stopping sets active=False + stop_date,
                              never mutates/deletes the original prescribing details
  services/timeline.py       Derives chronological events from encounters/conditions/
                              medications/allergies — report/lab events join the same
                              shape once Phase 05/06 exist, no reshaping needed later
  api/patients.py             Nested resource routes (spec §104); GET open to any
                               authenticated role, every write behind
                               require_role(ADMIN, DOCTOR) via a dedicated WriteUser
                               Annotated type (not a reused CurrentUser + default value,
                               which would silently skip the role check)

scripts/seed_demo_patients.py  3 synthetic ophthalmology patients (cataract, glaucoma,
                                 diabetic retinopathy) with 5-10 months of encounter/
                                 condition/medication/allergy history, drawn from
                                 data/eye_conditions.json terminology. Idempotent by MRN.
                                 Wired into start-demo.bat as step 6/8.

frontend/src/
  api/patients.ts, encounters.ts, clinical.ts, timeline.ts   TanStack Query hooks
  api/auth.ts (useCanWrite)   Derives write-permission from the logged-in role so
                               viewers see read-only UI (no button rendered at all)
                               instead of a control that always 403s — presentation
                               only, the backend role check remains authoritative
  components/Modal.tsx         Shared dialog primitive — every Add-X form composes it
  components/PatientCard.tsx, AddPatientModal.tsx, NewEncounterModal.tsx,
             AddConditionModal.tsx, AddAllergyModal.tsx, AddMedicationModal.tsx
  layouts/PatientWorkspace.tsx  Patient identity always visible (spec §24); tabs are
                                 real nested routes (/patients/:id/overview etc.), not
                                 client-only state, so each tab is directly linkable
  pages/Patients/               Search, filter, add
  pages/PatientWorkspace/        Overview, Timeline, Conditions (+ allergies),
                                  Medications tabs; Reports/Labs/Clinical AI still
                                  NotYetBuilt (Phases 05/06/08-10) but now nested inside
                                  the real patient context instead of standalone
  components/DashboardSnapshot.tsx  Now shows a REAL active-patient count (previously
                                      an honest "not available yet" placeholder) — the
                                      exact "gets replaced once Phase 04 lands" its own
                                      Phase 02 docstring promised. Report/AI-analysis
                                      counts remain honest placeholders until Phase 05/
                                      08-10 exist to generate them for real.

Deliberate simplification vs. the spec's literal wording: spec §18 says doctors access
"assigned/permitted patients." This build uses role-based access (any doctor/admin sees
all patients; viewer is read-only) rather than a per-patient grant/ACL system, since no
later phase in the spec's own plan calls for building patient-assignment management —
matches §135 "avoid unnecessary infrastructure" better than speculative ACL scaffolding.

Verified end-to-end with Playwright against the real running app: search → open a
seeded patient → real conditions/allergies/medications/encounters render → add a
condition → stop a medication (history preserved, not deleted) → new encounter →
unknown-patient-id shows a clean not-found state, not a broken page → logged in as
viewer, every write control is absent (not shown-then-403).
```

## Phase 05 — what exists right now

```text
backend/app/
  models/report.py            Report: ReportType/IngestionStatus/ExtractionStatus/
                                PatientMatchStatus enums, source_filename (display) vs.
                                stored_filename (random on disk) kept separate, file_hash
                                (sha256, indexed, dedup key), extracted_content (JSON,
                                page-tagged text so every extracted value traces back to
                                an exact source page per spec §133)
  models/ingestion_job.py     IngestionJob + PIPELINE_STAGES for UI progress display

  ingestion/validators.py     Magic-byte sniffing (extension alone is never trusted),
                                sanitize_display_filename
  ingestion/storage.py         reports_dir(), random stored filename, sha256, write/delete
  ingestion/pdf.py              PyMuPDF: per-page text + table extraction, page->PNG
                                 render (OCR fallback input)
  ingestion/docx.py, xlsx.py    python-docx / openpyxl: paragraphs+tables / per-sheet pages
  ingestion/image.py, dicom.py  Pillow / pydicom: image normalization, DICOM summary +
                                 de-identified preview PNG (broad try/except - a malformed
                                 DICOM degrades to "no preview," never a 500)
  ingestion/ocr.py               Lazy-loaded easyocr singleton (CPU), used only when a
                                 page's native text falls under ocr_min_chars_per_page -
                                 open-source substitute for the spec's suggested
                                 PaddleOCR (more reliable to install on Windows)
  ingestion/classification.py    Keyword-heuristic report-type classifier tuned for the
                                 ophthalmology domain; never fabricates a confidence score
  ingestion/identity.py           Extracts patient name/MRN from document text and
                                 compares against the current chart. Conservative by
                                 design (spec §30): only ever claims MATCHED or MISMATCH
                                 when reasonably confident, else UNCONFIRMED - a document
                                 is never silently auto-attached on uncertainty
  ingestion/pipeline.py          run_ingestion() orchestrator: stage-by-stage IngestionJob
                                 updates, dispatches by mime type, never raises past its
                                 own boundary (a parser crash fails that one report, not
                                 the request or the background worker)

  services/reports.py           create_report() (dedup by file_hash+patient unless
                                 explicitly overridden), run_ingestion_task() (FastAPI
                                 BackgroundTasks - not Celery/Redis, per spec §135's
                                 "avoid unnecessary infrastructure" - opens its own fresh
                                 DB session since the request's session is closed by the
                                 time it runs), confirm_patient_match(), archive_report()
  api/reports.py                 Upload/list/detail/status/file-download/preview/
                                 confirm-match/archive; files are only ever served through
                                 an authenticated endpoint, never a static/public path

scripts/generate_sample_reports.py  Synthetic ophthalmology report files for the upload
                                      demo (normal PDF/DOCX/XLSX, a scanned no-text-layer
                                      PDF and PNG to exercise real OCR, and one deliberate
                                      identity-mismatch PDF) - gitignored, regenerated by
                                      start-demo.bat step 7

frontend/src/
  api/reports.ts                  Upload/list/detail/confirm-match/archive hooks; list
                                    polling dynamically enables only while a report is
                                    still queued/processing, stops once settled
  components/UploadReportModal.tsx  File picker; a 409 duplicate conflict offers an
                                      explicit "Upload Anyway" retry rather than failing
                                      silently or auto-overwriting
  components/ReportCard.tsx          Status badge, OCR/page-count detail; a mismatch
                                      renders the exact spec §30 banner ("Patient
                                      mismatch detected" / current vs. detected identity)
                                      with confirm/cancel actions gated by useCanWrite()
  pages/PatientWorkspace/Reports.tsx  Replaces the Phase 04 NotYetBuilt placeholder
  pages/PatientWorkspace/Overview.tsx  "Recent Reports" card (spec §25)

Two real bugs were caught during live verification (not just unit tests) and fixed, both
with regression tests so they can't reappear silently:
1. Spreadsheet extraction renders "Label | Value" (pipe-separated cells), not
   "Label: Value" — the identity regexes only recognized `:`/whitespace separators and
   silently missed every XLSX-sourced identity field until fixed.
2. When a document (or OCR-flattened image/table text) puts more than one labeled field
   on a single line with nothing but whitespace between them — e.g.
   "Patient: Elena Novak MRN: DEMO-1003" — the name pattern swallowed the next field's
   label into its own capture ("Elena Novak MRN"), and the MRN pattern separately
   truncated its own value at the first internal space. Both regexes now stop at an
   explicit label/line boundary instead of matching greedily past it. This surfaces
   independently of OCR quality (a perfectly-read single-line document hits it too),
   though it was found via a live scanned-image upload where OCR also legitimately
   misread the MRN's hyphen as a space — which correctly still produces a MISMATCH
   (spec §30's "never silently guess"), just with a clean extracted name in the banner
   instead of a garbled one.

A third finding was investigated and determined to be correct, *intended* behavior, not
a bug: real (unmocked) OCR occasionally misreads a surname (e.g. "Wallace" -> "Wallce"),
which correctly triggers a MISMATCH rather than a false MATCH — exactly what spec §30
requires ("never silently attach" beats "usually right"). Left unchanged.

Verified end-to-end with Playwright against the real running app, one fresh browser
session per scenario: normal PDF upload (text extraction, classification, matched
identity), DOCX, XLSX (pipe-separated identity, post-fix), a scanned image/PDF with no
text layer through the real (unmocked) easyocr pipeline end-to-end, and a deliberate
identity mismatch (banner text, confirm/cancel actions, archive). Also checked: viewer
role sees no write controls on the Reports tab (covered by frontend unit tests).
```

## Phase 06 — what exists right now

```text
backend/app/
  models/observation.py       Observation: reference_low/high and abnormal_flag are
                                populated ONLY from what the source document itself
                                states (a Reference Range/Target table column, or an
                                explicit "(elevated)"-style annotation) — never a
                                hardcoded "normal" threshold. Real reference intervals
                                vary by lab/sex/age/method; baking one in would be
                                exactly the invented clinical fact spec §2 prohibits.

  ingestion/_tabular.py         Shared pipe-delimited table parser (reused by labs.py
                                 and medications.py). Finds genuine header rows within
                                 a contiguous pipe-run rather than always trusting the
                                 first line — needed because e.g. XLSX drops fully-
                                 empty rows instead of preserving them as a blank-line
                                 separator, so an identity preamble and the real data
                                 table can land in the same contiguous block
  ingestion/labs.py              Lab/observation extraction (spec §33): long-format
                                 tables ("Test | Result | Unit | Reference Range"),
                                 wide-format tables (a column header names a known
                                 test, e.g. "IOP (mmHg)", one series per row/qualifier
                                 like OD/OS), and inline free-text mentions. A small
                                 registry provides canonical names/aliases/typical
                                 units for grouping ONLY, never reference ranges
  ingestion/medications.py       Medication-list extraction scoped to a clearly
                                 delimited "Current Medications:"-style section
                                 (table or line list) rather than free-text NLP over
                                 an entire document — higher precision, every hit
                                 traceable to its exact source line

  services/observations.py       Persists extracted observations per report
                                 (idempotent — replaces, never accumulates,
                                 on re-processing); build_trends() groups by
                                 normalized test, with a small trusted-conversion
                                 table (spec §33: "convert only when a trusted
                                 conversion is defined... otherwise flag the
                                 incompatible units" — non-convertible readings are
                                 excluded from the trend series, never compared
                                 unsafely, and still visible in the full list)
  services/reconciliation.py     Medication reconciliation (spec §36): compares a
                                 specific report's detected medications against the
                                 patient's current active list. Fuzzy name matching
                                 (a drug's strength is sometimes folded into its name
                                 in one place, split out in another); dose text
                                 differences are surfaced as "needs review," never a
                                 confident "increased"/"decreased" claim, since the
                                 two sides often encode "dose" as different concepts
                                 entirely (administration volume vs. strength).
                                 Absence from one document is worded as "not
                                 mentioned in this document," never "discontinued" —
                                 spec §37's "potential inconsistency" framing, not an
                                 overclaimed fact. Read-only; never writes to
                                 `medications` — a clinician acts on what it surfaces
  services/change_engine.py      Deterministic "What Changed?" engine (spec §35 —
                                 "an actual backend change engine," no LLM). Diffs
                                 conditions/medications/allergies/observations
                                 between a `since` date and now. A medication "dose
                                 changed" isn't its own concept in the append-only
                                 medication model — it's a stop+start pair for the
                                 same drug, paired up here rather than shown as a
                                 misleading separate stop and start. Observation
                                 changes report "increased"/"decreased"/"unchanged" —
                                 deliberately NOT "worsened"/"improved", since
                                 whether a rising value is good or bad is test-
                                 specific clinical judgment this deterministic code
                                 has no basis to assert. `since` is a required query
                                 param, never a silently-guessed default window
  services/timeline.py            Extended with completed report uploads and
                                 abnormal-only lab results (normal results stay on
                                 the Labs tab — the timeline isn't drowned in noise)

  api/patients.py                 GET .../observations, .../observations/trends,
                                    .../changes?since=<date>
  api/reports.py                  GET .../medication-reconciliation

frontend/src/
  components/TrendChart.tsx        Plain inline SVG line chart (no charting library —
                                     matches the original-artwork approach from Phase
                                     02): 2px line, ≥8px markers with a surface ring,
                                     abnormal points colored distinctly, direct end-
                                     label. Single reading -> a dot and an honest "need
                                     at least two to show a trend line" note, not a
                                     fabricated line
  pages/PatientWorkspace/Labs.tsx    Replaces the Phase 04 placeholder: one card per
                                       test with its trend chart + full reading table
                                       (reference range shown exactly as the source
                                       document stated it, or "Not stated in source")
  components/ReconciliationModal.tsx  Current (system) vs. Detected (this document)
                                        table, triggered from a report's "Reconcile
                                        Medications" action; read-only, non-committal
                                        wording per the backend design above
  components/ChangesCard.tsx          "What's Changed" card on Overview, since the
                                        patient's previous encounter — needs at least
                                        two encounters to have a "previous visit" to
                                        compare against; says so honestly otherwise
                                        rather than falling back to an arbitrary
                                        window like "last 30 days"

Timeline (Phase 04) also gained report/abnormal-result icons; the "Recent Reports"
card pattern from Phase 05 is now joined by the Changes card on Overview.

A real, non-obvious bug was found and fixed during unit testing (not live testing this
time): a data row like `"HbA1c | 8.1 | % | 4.0-5.6"` also matches the wide-format
"looks like a header" heuristic (its own name cell, "HbA1c", matches the test
registry just as readily as a genuine column header like "IOP (mmHg)" would) — without
a fix, every data row was treated as the start of a new (headerless) table, and the
real header never got the chance to accumulate any rows under it. Fixed with a numeric
guard: a row holding an actual measured value is data, not a header, regardless of
whether its own name cell happens to match a known test.

Deliberate simplifications vs. the spec's literal wording, documented rather than
silently narrowed:
- The change engine covers conditions/medications/allergies/observations — spec §35's
  full list also names vitals/symptoms/procedures/reports, none of which any earlier
  phase modeled as structured data. Nothing here would need to change shape to add
  them later.
- Medication reconciliation compares "current system list" vs. "this one document,"
  not spec §36's literal two-arbitrary-points-in-time UI — the natural source of a
  "previous" medication list in this system is a document, not a second manually
  chosen system snapshot.

Verified end-to-end with Playwright against the real running app: Labs tab renders
real extracted values (correct abnormal flags, correct reference ranges, correct
single-vs-multi-point chart states) after a fresh XLSX upload; medication
reconciliation against a real consultation note correctly classifies newly-detected,
matched-with-a-dose-difference, and not-mentioned medications (confirmed the
"not-in-document" case never claims "discontinued"); the Changes card on Overview
renders a real diff (new condition, stopped medication, new allergy, new lab results)
computed from actual accumulated demo-patient data; Timeline correctly shows report-
upload and abnormal-result events interleaved chronologically with existing event
types, with normal results correctly absent.
```

## Phase 07 — what exists right now

```text
backend/app/
  models/chunk.py               Chunk: the SQLite-side twin of every Qdrant point.
                                  A chunk's `id` IS its Qdrant point ID (one row, one
                                  point, no separate mapping table). patient_id is
                                  nullable (NULL = medical_knowledge, not patient-
                                  scoped) but mandatory in every patient_documents
                                  query — enforced in code, not just by convention

  ingestion/chunking.py          Section-aware chunking (spec §55): blank-line-
                                  separated blocks (our own extractors already emit
                                  these for paragraphs/[Table] blocks), a short
                                  punctuation-free line tracked as the current
                                  section, ~550-token target / ~80-token overlap
                                  (configurable). A `[Table]` block is never split
                                  across chunks (spec §56) even if that makes one
                                  chunk larger than target. Token counts are an
                                  approximation (~1.3x word count) — no real Qwen
                                  tokenizer is wired in, and an approximation is
                                  sufficient for sizing chunks

  rag/embeddings.py               Qwen3-Embedding-0.6B via sentence-transformers,
                                   lazy-loaded singleton (same pattern as Phase 05's
                                   OCR reader), dimension read from the loaded model
                                   (never hardcoded). embed_query() vs.
                                   embed_documents() — Qwen3-Embedding's asymmetric
                                   query/document convention
  rag/reranker.py                 Qwen3-Reranker-0.6B via sentence-transformers'
                                   CrossEncoder, same lazy-singleton pattern. A
                                   generic interface (query, [(chunk_id, text), ...])
                                   -> reranked hits — nothing outside this module
                                   knows the reranker is specifically a Qwen model
  rag/qdrant_setup.py              Creates medical_knowledge/patient_documents on
                                   first real use (vector size from the embedding
                                   model, spec §5); a payload index on patient_id
                                   for fast mandatory filtering (spec §16).
                                   patient_vision (Phase 09)/web_cache (Phase 11)
                                   join later the same way
  rag/dense_retriever.py           Embedding-similarity search. Raises if
                                   patient_documents is queried without a
                                   patient_id — patient isolation enforced in code,
                                   at the one place every query passes through
  rag/sparse_retriever.py          BM25 (spec §43 Stage 6 — critical for drug
                                   names/ICD codes/exact phrases dense embedding can
                                   blur past) via rank-bm25, computed in-process over
                                   the SQLite chunk corpus at query time rather than
                                   stored as a Qdrant sparse vector — simpler than
                                   the IDF-fitting infrastructure a persistent sparse
                                   index needs at this deployment's scale, and never
                                   goes stale against the corpus. Same mandatory
                                   patient_id rule as dense_retriever
  rag/fusion.py                    Reciprocal Rank Fusion (spec §44's named default),
                                   standalone and swappable per spec's "keep fusion
                                   strategy configurable"
  rag/deduplicator.py              Deduplication + parent expansion (spec §47):
                                   adjacent same-section chunks from one source merge
                                   into one passage with full chunk-level provenance;
                                   max_per_source caps one document from dominating
                                   the result just because several overlapping
                                   chunks matched
  rag/indexing.py                  index_document(): chunk -> embed -> upsert to
                                   Qdrant + persist Chunk rows, idempotent per source
                                   (re-indexing replaces, never accumulates). Shared
                                   by report ingestion (patient_documents) and
                                   scripts/ingest_knowledge.py (medical_knowledge) —
                                   matches spec §29's own pipeline diagram ("RAG
                                   chunking -> Embedding -> Qdrant indexing")
  rag/pipeline.py                  retrieve(): composes dense + sparse + fusion +
                                   rerank + dedup into one call. No knowledge of the
                                   LLM or conversation state — query classification/
                                   rewriting/context construction is Phase 08's job,
                                   which calls into this package

  ingestion/pipeline.py (extended) New "indexing" stage after lab extraction. Never
                                   indexes a report flagged MISMATCH — its content is
                                   suspected to belong to a *different* patient, so
                                   indexing it under this one's patient_id would
                                   defeat the isolation guarantee it's meant to
                                   protect. Indexing runs instead once
                                   confirm_patient_match() clears the mismatch.
                                   archive_report()/delete_report_and_file() now
                                   deindex too — an archived report stops being
                                   retrievable immediately, not left searchable

  api/health.py (extended)         /api/health/qdrant now reports real per-
                                   collection point counts, not just reachability.
                                   Embedding/reranker health flips from "not_loaded"
                                   to "ready" (with real detected dimension for
                                   embedding) once something has actually used them —
                                   still never a hardcoded "Ready" (spec §103)

scripts/ingest_knowledge.py        Ingests data/*.pdf into medical_knowledge. Default
                                    scope is a curated set of small, genuinely
                                    clinical ophthalmology guideline documents
                                    (ICO Clinical Guidelines, Ophthalmology Referral
                                    Guidelines, Instruments book — 136 pages total);
                                    --all opts into the remaining multi-hundred-page
                                    textbooks (up to ~1,900 pages). See "CPU
                                    embedding performance" below for why that's a
                                    deliberate scope decision, not laziness

evaluation/
  golden_questions.jsonl           spec §96's golden set, scoped to what Phase 07
                                    can actually test: exact_medication_query,
                                    semantic_symptom_query, numerical_lab_query,
                                    patient_history_query, guideline_query,
                                    no_evidence_query, patient_isolation_attack.
                                    report_comparison/prompt_injection_document/
                                    citation_validation/vision_report_extraction/
                                    web_deidentification need Phase 08/09/11
                                    features that don't exist yet — added when those
                                    phases land, per spec §96's own list
  retrieval_eval.py                Recall@5/10/20 + MRR at the fusion stage (dense+
                                   sparse+RRF, before reranking — reranking's final
                                   top-8 is too small a pool to compute Recall@20
                                   meaningfully), using keyword containment as a
                                   relevance proxy. The full evaluation/ suite
                                   (citation/groundedness/hallucination/vision) lands
                                   in Phase 15 once 08/09/11 exist to produce
                                   anything to evaluate

## CPU embedding performance — a real, measured finding

Live testing surfaced a genuine, non-obvious performance bug, not just a slow model:
`Qwen3-Embedding-0.6B` defaults to a 32,768-token max sequence length (it supports
very long context), and `sentence-transformers` sizes its attention computation off
that configured max — not the actual input length. Left uncapped, embedding a single
~400-word chunk took **141-179 seconds** on this 16-core CPU machine. Two fixes,
applied in `rag/embeddings.py`/`rag/reranker.py`:

1. **Cap `model.max_seq_length`** to `settings.embedding_max_seq_length` (default
   2048 — comfortable headroom over the ~550-token chunk target). This is the
   single most impactful line for CPU throughput on this model.
2. **Force `attn_implementation="sdpa"`** (PyTorch's fused scaled-dot-product-
   attention kernel) instead of the default "eager" implementation — both Qwen3-
   Embedding and Qwen3-Reranker are decoder-based, and eager attention is
   measurably slower on CPU for this architecture (~2.2x, measured on a clean,
   uncontended run). Falls back to the default if `sdpa` isn't available rather
   than failing the whole pipeline over a throughput optimization.

With both fixes, a clean (no CPU contention from other processes) measurement showed
**~11 seconds/chunk** once the model is warm — a ~46-page clinical guideline PDF
(38 chunks) indexes in roughly 7 minutes. This is still genuinely CPU-slow (spec §12
"prefer CPU execution" for embedding/reranker, keeping the GPU free for the main LLM,
has a real throughput cost) — which is exactly why `scripts/ingest_knowledge.py`'s
default scope is small, curated, and clinically real rather than attempting the full
multi-thousand-page reference library inline. A production deployment populating a
large knowledge base would either run ingestion as a long background/overnight job or
use a GPU-capable `EMBEDDING_DEVICE`.

Deliberate simplifications vs. the spec's literal wording, documented rather than
silently narrowed:
- Sparse retrieval is computed in-process (rank-bm25 over the SQLite chunk corpus at
  query time), not stored as a Qdrant sparse vector — see `rag/sparse_retriever.py`'s
  docstring. Spec §44 requires hybrid dense+lexical retrieval with RRF fusion; it
  doesn't mandate lexical retrieval specifically live *inside* Qdrant.
- `evaluation/golden_questions.jsonl` covers 7 of spec §96's 12 categories — the
  other 5 need chat (08), vision (09), or web research (11) features to exist first.

Verified end-to-end with real (unmocked) models against the real running Qdrant
instance: `scripts/ingest_knowledge.py`'s default 3 files indexed 111 real chunks into
`medical_knowledge`; 4 real demo-patient reports (Wallace/Klein/Novak) indexed into
`patient_documents`. The golden retrieval set (`evaluation/retrieval_eval.py`) scores
**7/7 passing** against this real content — Recall@5/10/20 and MRR all 0.71 (5 of 7
categories have a findable answer to rank; the other 2, `no_evidence_query` and
`patient_isolation_attack`, correctly find *nothing*, which is the right answer for
both). Notably, `semantic_symptom_query` ("trouble seeing at night or with bright
lights") correctly ranked Wallace's actual chief complaint ("glare while driving at
night") first — genuine semantic match, not keyword overlap, real evidence the
embedding model is doing its job. The critical patient-isolation test
(`backend/tests/test_rag_pipeline.py`) proves a chunk built from patient A's own real
clinical content, queried with maximal semantic/lexical relevance while scoped to
patient B, never appears in patient B's results — the spec §14 guarantee, checked as
an automated test that runs on every CI pass (part of the full 100-test backend
suite), not just verified once by hand.

A second real bug was found live, not in unit testing: `services/reports.py`'s
`confirm_patient_match()` calls `index_document()` through a separate import than
`ingestion/pipeline.py`'s — the test suite's mock only covered the first call site,
so every mismatch-confirmation test left one real, un-cleaned-up point in the shared
dev Qdrant instance. Caught by noticing `patient_documents`' real point count didn't
match its own SQLite chunk-row count after a full test run; fixed by mocking both
call sites, verified by asserting the point count is bit-for-bit identical before and
after a full backend test run (100 passed, 0 net new Qdrant points).
```

## Phase 08 — what exists right now

```text
backend/app/
  models/conversation.py           Conversation: user_id, optional patient_id/
                                    encounter_id/selected_report_id, ConversationScope
                                    (general, current_patient, current_encounter,
                                    selected_report, selected_reports_comparison
                                    [Phase 10], local_knowledge_only, research_mode
                                    [Phase 11]), title (set from the first user
                                    message, spec §39's conversation list)
  models/message.py                Message: role, content, structured_payload (JSON —
                                    task_classification/evidence_quality/grounding
                                    ONLY; never chain-of-thought, spec §125),
                                    generation_error (distinct from an honest
                                    abstention, which is a normal successful message)
  models/citation.py               Citation: label ("P1"/"L1"), source_type, chunk_id
                                    (nullable, SET NULL — citation survives reindexing/
                                    deletion), report_id, source_title/page/section,
                                    source_excerpt copied at generation time, relevance_score

  chat/prompts.py                  Centralized, versioned system prompts (spec §137
                                    "one place, versioned") — clinical_chat-v1,
                                    grounding_validation-v1. Evidence-as-data/prompt-
                                    injection boundary, exact-wording abstention
                                    instruction, never invent patient values, never
                                    state numeric confidence
  chat/generation.py                Ollama /api/chat streaming client. `"think": false`
                                    on every request — see "Hybrid-reasoning model
                                    latency" below for why this is not optional.
                                    Process-wide asyncio.Semaphore (spec §121, sized
                                    from CHAT_MAX_CONCURRENT_GENERATIONS)
  chat/patient_context.py          Structured facts (name/MRN/age/sex, active
                                    conditions, allergies, active medications) — spec
                                    §43 Stage 4's "don't embed every row unnecessarily"
  chat/query_classifier.py         Deterministic regex greeting detector
                                    (general_conversation vs. clinical_question) — the
                                    full spec §43 task-category list (SOAP, coding,
                                    vision...) routes to modules that don't exist until
                                    Phase 09-10
  chat/context_builder.py          Labels retrieved passages P1/P2.../L1/L2... in
                                    order, formats the evidence block the LLM sees
  chat/citation_validator.py       Strips any `[P9]`-style marker the model emits that
                                    doesn't match real offered evidence (spec §52 —
                                    never trust the LLM's own citation numbering)
  chat/grounding_validator.py      One structured LLM pass classifies each major
                                    claim as supported/partially_supported/unsupported
                                    against its cited passages (spec §52/§53 combined —
                                    same underlying judgment). One controlled retry;
                                    returns None (never a fabricated "pass") if both
                                    attempts fail to parse
  chat/evidence_quality.py         Deterministic STRONG/MODERATE/LIMITED/INSUFFICIENT
                                    label from the reranker's own logit sign + citation
                                    coverage + distinct-source count — never a
                                    fabricated confidence percentage (spec §54)
  chat/orchestrator.py             prepare_turn() (classify -> retrieve -> assemble
                                    context, sync, no LLM call) / finalize_turn()
                                    (citation + grounding validation, async, runs once
                                    the full streamed answer is in hand — spec §119
                                    "preserve citations when the final answer
                                    completes"). Abstains only when there is truly
                                    nothing to answer from (no retrieval hits AND no
                                    structured facts) — structured facts alone answer
                                    many questions with zero retrieval needed.
                                    SELECTED_REPORT scope deliberately does not widen
                                    to medical_knowledge; every other patient scope does

  services/chat.py                 DB persistence + the run_turn() SSE-event generator
                                    glueing chat/orchestrator.py to the API layer
  api/chat.py                      /api/conversations CRUD + /api/conversations/{id}/
                                    messages — real StreamingResponse over text/event-
                                    stream (spec §119, not client-chunked), checking
                                    request.is_disconnected() before every yield (spec
                                    §120 cancellation)

frontend/src/
  api/chat.ts                       Types mirroring schemas/chat.py, TanStack Query
                                     hooks for conversation CRUD, and streamMessage() —
                                     fetch + a hand-parsed `data: {...}\n\n` SSE body
                                     (not EventSource, which can't POST a body or take
                                     an AbortSignal). useChatStream() owns the per-
                                     conversation streaming lifecycle + Stop
  pages/ClinicalAI/                 The shared three-column surface (Conversations |
                                     Clinical Assistant | Evidence, spec §39), used by
                                     both the global /clinical-ai route (general /
                                     local_knowledge_only scopes only) and the
                                     per-patient tab (current_patient/current_encounter/
                                     selected_report). The patient-tab route wrapper
                                     keys the workspace on patient.id so switching
                                     patients fully remounts it — spec §40, never
                                     silently continue a patient-specific conversation
                                     under a different patient
  components/AskAIButton.tsx        "Ask AI About This" (spec §41) on Report/Lab/
                                     Medication cards — auto-passes real object context
                                     as an already-composed question via router state,
                                     lands on the patient's Clinical AI tab and actually
                                     sends it, never decorative. Hidden for viewers
                                     (starting a conversation is a write action)
```

### Hybrid-reasoning model latency — a real, measured finding

Live end-to-end testing (real Ollama, real Qdrant, real reranker — not mocked) surfaced
a correctness bug, not just a slow model: `qwen3.5:9b` is a hybrid-reasoning model that,
left at its default, spends its *entire* generation budget on an invisible "thinking"
phase before emitting any visible content. A trivial 3-word prompt against this Ollama
instance produced 2,200 thinking tokens and took **293 seconds** before Ollama's response
even contained a `content` field — and under the chat endpoint's configured
`num_predict` (1,024, spec §50's response-length budget), thinking alone consumed the
whole budget, so `content` stayed empty for the entire stream. The result: an apparently
successful generation with **zero visible tokens**, silently falling through to look like
an evidence-quality-insufficient answer with nothing wrong logged.

Fixed in `chat/generation.py`: every request now sends `"think": false`. This is not
just a latency fix — it is also the more correct behavior for spec §125's "no hidden
chain-of-thought" requirement, since a model that only *appears* to skip thinking but
still reasons internally is a weaker guarantee than one that has it disabled outright.
Verified live after the fix: a real `current_patient`-scope question ("summarize active
conditions and medications, mention relevant guideline evidence") streamed 455 real
tokens, cited `[P1]` (the patient's own consultation note) and `[L2]`/`[L3]` (ICO
glaucoma guideline passages), scored `evidence_quality: limited` (correctly — the
reranker's own logits were negative for all three passages), and the grounding validator
correctly flagged the model's opening demographic claim as `unsupported` (the cited
passage doesn't literally state age) while confirming the medication and guideline
claims as `supported`. This is the whole Phase 08 pipeline working end-to-end against
real content, not a mocked approximation of it.

A second, separate, **not yet fixed** latency source was also observed live: reranking a
`current_patient`-scope query against `medical_knowledge` took **~397-398 seconds**,
consistently, across two separate cold backend processes (so it is not a one-time
JIT/model-load cost — see Phase 07's CPU embedding section above for the fixes that
already went into `rag/reranker.py`). This dominates total turn latency far more than
generation itself once thinking is disabled. Root cause is not yet isolated (candidate
count vs. per-candidate sequence length vs. thread configuration) — flagged here as a
known follow-up rather than guessed at and "fixed" blind, since `rag/reranker.py` is
Phase 07's already-tested, already-committed code and this session's scope is Phase 08.

## Phase 09 — what exists right now

```text
backend/app/
  llm/generation.py                 REFACTORED from app/chat/generation.py (Phase 08)
                                     into a shared package: chat and vision are both
                                     just callers of one Ollama client, one process-
                                     wide concurrency semaphore (spec §58 "use Qwen3.5
                                     vision capability rather than loading a second
                                     large VLM" — one model, one budget, whether the
                                     call carries images or not). `ChatMessage` gained
                                     an `images: list[str] | None` field (base64,
                                     Ollama's per-message `images` key)

  models/vision_analysis.py         VisionAnalysis: one row per report (re-running
                                     analysis updates it, never accumulates history —
                                     same idempotent-per-source convention as
                                     `index_document`). `payload` is spec §60's exact
                                     JSON schema (image_type/visible_text/observations/
                                     measurements_visible/clinical_entities/
                                     quality_limitations/uncertainties) — the only
                                     "acceptable provenance," same rule as Phase 08's
                                     Message.structured_payload. status:
                                     success/failed/not_applicable (a DICOM whose pixel
                                     data can't decode into a preview is NOT_APPLICABLE,
                                     distinct from an attempted-and-failed analysis)
  models/chunk.py (extended)        ChunkCollection.PATIENT_VISION joins
                                     patient_documents/medical_knowledge;
                                     PATIENT_SCOPED_COLLECTIONS (both patient_documents
                                     and patient_vision) is the single set every
                                     patient-isolation check (mandatory patient_id
                                     filter, spec §16) now tests membership against,
                                     rather than one hardcoded collection name
  models/citation.py (extended)     CitationSourceType.PATIENT_VISION — image-derived
                                     evidence gets its own citation source type, "V#"
                                     label space (spec §51-style, alongside P#/L#)

  vision/prompts.py                 Centralized, versioned (spec §124): vision_analysis
                                     ("describe OBSERVABLE findings, never a diagnosis
                                     as fact" — spec §58/§59's central rule, repeated
                                     not just stated once) and vision_comparison
                                     (previous image sent first, current second — the
                                     prompt states that ordering explicitly)
  vision/analyzer.py                analyze_image()/compare_images(): Pydantic-
                                     validated structured JSON output over
                                     llm/generation.py, same validate/repair-retry/
                                     never-fabricate discipline as Phase 08's
                                     grounding_validator (one retry, `None` — never a
                                     fabricated result — if both attempts fail to parse)

  services/vision.py                Persistence + orchestration. run_analysis():
                                     reads real image bytes (a DICOM report's is a
                                     rendered preview PNG, via ingestion/dicom.py's
                                     existing Phase 05 renderer) -> analyze_image() ->
                                     stores the result -> indexes into patient_vision
                                     (skipped for a MISMATCH report, same spec §16 rule
                                     as text reports — resumes once
                                     services/reports.py's confirm_patient_match()
                                     calls reindex_if_present(), which re-indexes from
                                     the already-stored payload rather than re-calling
                                     the model). compare_reports(): stateless — spec
                                     §61 only asks to "support selecting two images"
                                     and "show" the comparison, nothing requires
                                     versioning/persisting it, so it's computed fresh
                                     every call rather than adding a table+migration
                                     for an inherently ad-hoc feature. Its
                                     `clinical_evidence` is a REAL deterministic
                                     `rag.pipeline.retrieve()` call against
                                     `medical_knowledge`, querying on the model's own
                                     `differences` list (spec §61 "where useful,
                                     retrieve relevant local knowledge based on
                                     extracted differences") — never text the model
                                     invented itself
  ingestion/pipeline.py (extended)  run_ingestion() is now async (a real awaited
                                     Ollama call lives inside it) and, for image/DICOM
                                     mime types only, runs vision analysis
                                     automatically after lab extraction — same
                                     automatic, best-effort-never-blocks pattern as OCR
                                     (spec §122). A PDF/DOCX/XLSX report never gets a
                                     VisionAnalysis row at all, vs. an explicit
                                     `POST .../vision/analyze` call against one, which
                                     honestly records NOT_APPLICABLE
  chat/orchestrator.py (extended)   Image-to-RAG, for real (spec §59's own pipeline
                                     diagram ends in "RAG query generation -> local
                                     knowledge retrieval"): current_patient/
                                     current_encounter scopes now also retrieve from
                                     patient_vision, labeled V1/V2/... alongside P#/L#.
                                     SELECTED_REPORT scope deliberately does not widen
                                     to the whole patient_vision corpus (same rationale
                                     as its medical_knowledge exclusion) — but if the
                                     selected report itself has a vision analysis, it's
                                     surfaced in that report's own "SELECTED REPORT
                                     FACTS" section, since it's directly on-topic there
  chat/citation_validator.py/       Citation regex extended [PLW] -> [PLVW]; V-labels
  context_builder.py (extended)     validated/stripped exactly like P#/L#

  api/vision.py                     GET .../vision (read), POST .../vision/analyze and
                                     POST .../vision/compare (write-gated — both invoke
                                     real generation, same rationale as sending a chat
                                     message in Phase 08)

frontend/src/
  api/vision.ts                     Types mirroring schemas/vision.py; useVisionAnalysis
                                     treats a 404 ("never run yet") as a normal empty
                                     state, not an error to alert on
  components/VisionAnalysisPanel.tsx Structured findings shown inline on ReportCard for
                                     any image/DICOM report — usually already populated
                                     by the time a clinician looks (ingestion ran it
                                     automatically), with a Re-analyze action for a
                                     retry after failure
  components/ImageCompareModal.tsx  Spec §61's exact layout: previous/current image
                                     thumbnails, previous findings, current findings,
                                     observable changes, differences, clinical
                                     evidence, limitations. Reachable from the Reports
                                     tab once a patient has ≥2 analyzable images
```

### A real bug found live: a second unmocked indexing call site (again)

Live end-to-end testing (real upload, real Ollama vision analysis, real Qdrant
indexing, real comparison — not mocked) worked correctly end to end: a synthetic
fundus-style test image was correctly described as "a schematic diagram of an eye"
with honest `quality_limitations` ("stylized schematic, not a clinical photograph, no
anatomical detail... beyond simplified shapes") rather than the model pretending it
was a real clinical photo — exactly the "describe observable findings, never
diagnosis-as-fact" behavior spec §58 requires. A two-image comparison then correctly
ran as one real joint vision-model call and, on genuinely subtle synthetic circle-size
differences, honestly reported "no visible differences" rather than fabricating a fake
progression — the right call given spec's "never fabricate" priority, even though it
means this particular synthetic test case wasn't a good discriminating example.

Live testing also caught a real bug before it reached this doc as a clean success
story: the very first post-refactor `pytest` run took 128s instead of the usual ~30s
(some DICOM-upload tests carry real, decodable synthetic pixel data), because
`services/vision.py` imports `index_document` as its own direct reference — a second
call site the existing `_mock_rag_indexing` fixture didn't cover, exactly the same
class of bug Phase 07's architecture notes already documented once
(`services/reports.py`'s confirm_patient_match import). Fixed by adding
`app.services.vision.index_document` to that fixture (and a matching
`_mock_vision_generation` fixture, since `analyze_image`/`compare_images` were also
unmocked and made real ~30-100s+ Ollama calls per image-upload test). By the time this
was caught, two real points had already leaked into the dev Qdrant's `patient_vision`
collection from that one slow pre-fix run — found via the exact same "real point count
doesn't match SQLite chunk rows" check Phase 07's notes describe, and deleted by hand.
The fix itself is verified structurally, not just by inference: `points_by_collection`
for `patient_vision` was confirmed at 0 both before and after the full live upload ->
analyze -> index -> archive/deindex cycle performed for this section.

## Phase 10 — what exists right now

```text
backend/app/
  llm/structured.py                 EXTRACTED from three near-identical copies of
                                     spec §123's validate/repair-retry/never-fabricate
                                     loop (grounding_validator, vision/analyzer, and
                                     now six clinical modules) into one shared,
                                     generic `generate_structured(messages, schema,
                                     settings) -> SchemaT | None` helper. Refactor
                                     verified safe by the full test suite before any
                                     Phase 10 code was written on top of it

  models/clinical_module_run.py     ClinicalModuleRun: ONE table for all six modules
                                     (module_type discriminates payload shape) rather
                                     than six near-identical tables — each module still
                                     has its own real Pydantic schema/prompt/workflow
                                     (spec §63's actual requirement is "don't send the
                                     same prompt to the chat endpoint," not "use a
                                     separate table"). Every row is an explicit,
                                     timestamped DRAFT — spec §63's SOAP instruction
                                     ("never automatically saved as finalized clinical
                                     record") applies to all six; nothing here ever
                                     writes to Condition/Medication/Encounter. Visible
                                     to any authenticated clinician viewing that
                                     patient's chart, unlike Phase 08's private chat
                                     conversations — a generated draft is chart-adjacent
                                     work product, not personal history

  modules/prompts.py                Six centralized, versioned prompts (spec §124) —
                                     summary (parameterized by type: concise/discharge/
                                     encounter/progress_note), SOAP, entity extraction,
                                     differential support, guideline Q&A, report-
                                     comparison narrative. Every prompt restates spec
                                     §2/§58's core rules itself (never invent a value,
                                     never state a diagnosis as fact, never a numeric
                                     confidence) since each is an independent call with
                                     no shared system prompt to inherit from
  modules/summarizer.py             SummaryType enum + generate_summary() — the four
                                     summary variants share one prompt template and
                                     schema, parameterized rather than duplicated
  modules/soap.py                   Spec §63's exact SOAP schema
                                     (subjective/objective/assessment/plan/
                                     missing_information/source_trace)
  modules/entity_extraction.py      Structured entity extraction — text/category/
                                     context per entity, only what's literally present
                                     in the source, never inferred
  modules/differential.py           Spec §63's exact Differential Support schema.
                                     Reuses chat's LabeledEvidence/build_evidence_block
                                     directly — same evidence formatting as clinical
                                     chat, not a reimplementation
  modules/guideline_qa.py           A dedicated single-turn workflow (spec §63: "do not
                                     implement every capability as send-prompt-to-chat-
                                     endpoint") — reuses chat's citation_validator and
                                     evidence_quality scoring rather than reimplementing
                                     that judgment a second time. Abstains with spec's
                                     exact wording when nothing relevant is retrieved,
                                     WITHOUT ever calling the model (verified by test —
                                     the model call itself is asserted never-invoked)
  modules/report_comparison.py      LLM narrates only NON-numeric textual differences
                                     between two reports; the prompt explicitly tells it
                                     not to recompute or restate numbers as its own
                                     calculation — see the deterministic engine below

  services/clinical_modules.py      Persistence + orchestration for all six. The
                                     report-comparison numeric diff
                                     (`_compute_numeric_changes`) is 100% deterministic
                                     Python — spec's own acceptance criterion "numeric
                                     values are calculated deterministically" — reusing
                                     `services/observations.py`'s trusted-unit-
                                     conversion table (the same one the lab trend engine
                                     and change engine already use) and the same
                                     increased/decreased/unchanged wording convention
                                     as change_engine.py, plus new/resolved for values
                                     present on only one report. An untrusted unit pair
                                     is never compared, matching the trend engine's own
                                     rule. Differential support strips any evidence_id
                                     the model invents that wasn't actually offered —
                                     spec §52's citation-validation rule, applied here
                                     too, not just in chat
  api/clinical_modules.py           Per-patient endpoints (summary/SOAP/entities/
                                     differential/report-comparison) plus one patient-
                                     independent endpoint (guideline-qa). Every
                                     generation-triggering endpoint requires WriteUser
                                     (real Ollama calls — same rationale as chat/
                                     vision); reading already-generated drafts only
                                     needs CurrentUser

frontend/src/
  api/clinicalModules.ts            Types mirroring the six payload schemas exactly;
                                     each generation call is a mutation (a real,
                                     billable-latency action), history lists are
                                     queries
  pages/PatientWorkspace/ClinicalModules/  Five sub-views (Summary/SOAP/Entities/
                                     Differential/Compare Reports) behind a local tab
                                     selector on a new "Clinical Modules" patient-
                                     workspace tab — deterministic numeric-change table
                                     rendered directly (never re-derived client-side),
                                     narrative/citations layered on top
  pages/Workflow/                   The global "Workflow" nav slot (previously a
                                     placeholder) now hosts Guideline Q&A — patient-
                                     independent, so it doesn't belong on a patient tab
```

### Deliberate scope note: "EHR/Patient Reasoning"

Spec §63 lists six sub-capabilities under "Structured Clinical Modules," including
"EHR/Patient Reasoning: combine structured patient facts, relevant narrative records,
and relevant clinical evidence." Phase 10's own explicit implement-list (spec's phase
table) names only five: "summary, SOAP, entity extraction, guideline Q&A, differential
support" (report comparison added from the master prompt's separate Phase 10 bullet).
"EHR/Patient Reasoning" isn't a new deliverable here — it's a description of
exactly what Phase 08's `current_patient`-scope Clinical Chat already does
(`chat/orchestrator.py`'s `prepare_turn()`: structured patient facts + retrieved
patient documents + retrieved knowledge evidence, combined). Treated as already
satisfied rather than built a second time under a different name.

### Live verification — real Ollama, real patient data, not mocked

Four of the six modules were run live against a real demo patient (Robert Klein,
glaucoma) with real encounter notes: SOAP note generation (~63s) produced a correct,
well-structured draft distinguishing subjective/objective/assessment/plan exactly from
the encounter's own documented findings; entity extraction (~24s) correctly pulled
"glaucoma" (condition) and the two IOP readings (lab_finding) with accurate context;
a concise summary (~82s) correctly synthesized three encounters' notes into one
coherent narrative, honestly flagging that the most recent encounter's source material
had no IOP data recorded rather than inventing a plausible-sounding value; and a real
Guideline Q&A question against the local ICO glaucoma guidelines (~6m53s — the
already-documented Phase 07/08 reranker latency, not a new finding) produced a
correctly-cited, accurate follow-up-interval answer with real page/section references.
Differential support and report comparison share the exact same `retrieve()` code path
already proven live here, in Phase 08, and in Phase 09, plus their own
non-LLM logic (numeric diffing, citation stripping) is covered by 13 passing direct
unit tests — live-testing them too would re-confirm the same reranker latency finding
without exercising new code, at a real time cost (given each RAG-grounded call took
6-7 minutes live), so they were verified through the test suite rather than a second
live round trip.

## Phase 11 — what exists right now

```text
backend/app/
  models/web_cache.py                WebCacheEntry (spec §72): checksum-deduped,
                                      freshness-window cache reuse for external results.
                                      AuthorityTier (spec §67 A-F) and WebSource live
                                      here too — reused by Phase 12's KnowledgeDocument
                                      rather than a second authority-tier concept.
                                      Deliberately NOT also indexed into a Qdrant
                                      `web_cache` collection — see "Deliberate scope"
                                      below
  models/clinical_module_run.py      +RESEARCH module type — Research Mode queries are
                                      persisted as the seventh ClinicalModuleRun kind,
                                      same draft-never-auto-finalized discipline as
                                      Phase 10's six

  research/deidentify.py             Mandatory de-identification (spec §66) — strips the
                                      patient's own known identifiers (name/MRN/phone/
                                      email) plus generic identifier-shaped patterns
                                      (email/phone/MRN/street-address regexes).
                                      Deliberately NOT general NER name detection — see
                                      "Deliberate scope" below. Runs unconditionally
                                      before any provider sees the query, no bypass
  research/providers/                pubmed.py (NCBI E-utilities: esearch+esummary+
                                      efetch, real XML abstract parsing), fda.py
                                      (openFDA drug labels), clinicaltrials.py (API v2),
                                      searxng.py (optional, self-hosted). Every
                                      `search()` is independently best-effort — a
                                      network failure/timeout/malformed response returns
                                      `[]`, never raises, so one unreachable source never
                                      sinks the rest of a query
  research/providers/base.py         WebResult dataclass + `clean_search_terms()` —
                                      punctuation/stopword stripping for PubMed/FDA's
                                      keyword-search syntax (see "Bugs found live"
                                      below); deliberately NOT applied to ClinicalTrials.
                                      gov/SearXNG, whose free-text search engines handle
                                      natural language directly
  research/ranking.py                Deterministic lexical relevance (word-overlap) +
                                      modest authority-tier boost (spec §67: "must not
                                      override obvious relevance") — a fast, non-LLM
                                      ranking pass instead of routing web results through
                                      the CPU reranker
  research/paper_assistant.py        ResearchSynthesis schema + generate_research_
                                      synthesis() — spec §70's Research Paper Assistant.
                                      Tolerant field_validators coerce an occasional
                                      string-instead-of-list model response into the
                                      expected shape (see "Bugs found live" below)
  services/research.py               Orchestration: de-identify -> retrieve patient/
                                      local evidence -> fetch external (cache-first,
                                      asyncio.gather for uncached) -> filter by date
                                      range -> rank -> label evidence (P#/L#/W#) ->
                                      synthesize -> validate citations -> record run
  api/research.py                    GET /status (honest capability check — enabled
                                      flag AND live SearXNG reachability, never
                                      assumed), POST /query, GET /runs

frontend/src/
  contexts/ResearchMode.tsx          ResearchModeProvider/useResearchMode — active only
                                      while the Research page has >=1 external source
                                      checked, reverts on unmount (spec §128/§129: the
                                      header badge must never show a stale "Research"
                                      state after navigating away)
  api/research.ts                    WebSource/DateRange/ResearchPayload types +
                                      useResearchStatus/useResearchRuns/
                                      useRunResearchQuery
  pages/Research/index.tsx           Source checkboxes (PubMed/FDA/ClinicalTrials/
                                      General Web + always-on disabled "Local
                                      Knowledge"), date range, evidence preference,
                                      consent banner on first source toggle, citation
                                      badges distinguishing PATIENT/LOCAL/PubMed/FDA/
                                      ClinicalTrials/SearXNG sources
```

### Live verification — real Ollama, real PubMed/openFDA, not mocked

Research Mode's own end-to-end round trip (patient + local + external evidence combined
into one synthesis) turned out to be the single most demanding call in the app so far,
and live testing surfaced four real, previously-invisible bugs — each found, fixed, and
re-verified against the real running stack before moving on:

1. **Ollama request timeout too low.** The first live query (`sources: [pubmed, fda]`)
   failed with `httpx.ReadTimeout` after the ~7-minute reranker step completed — the
   combined evidence prompt is bigger than any prior module's and exceeded the
   `ollama_request_timeout_seconds` default of 120s inherited from Phase 08. Raised to
   300s (`app/config/settings.py`) — a ceiling raise costs nothing for faster calls, it
   just lets the slower ones finish instead of erroring out.
2. **`num_ctx` never set anywhere in the app.** With the timeout fixed, the model
   responded within the window but returned unparseable JSON on both `generate_
   structured` attempts. Investigation found `num_ctx` (Ollama's context window) was
   never explicitly sent on *any* call in the whole codebase — every request silently
   ran at Ollama's own server default, completely disconnected from the app's own
   `rag_default_context_tokens=8192` retrieval budget. Research's prompt was the first
   one big enough to actually exceed that default, silently truncating the *input* (most
   likely dropping the system prompt's JSON-shape instructions). Fixed in `app/llm/
   generation.py` by explicitly sending `num_ctx` on every call — `ollama_num_ctx=8192`
   as the new shared default (matching the existing RAG budget) and `research_num_ctx=
   16384` as a Research-specific override, since its combined-evidence prompt runs
   larger than any other module's. `app/llm/structured.py` also now logs a raw-output
   preview on any parse failure — previously only the bare exception was logged, with no
   way to tell truncation from malformed JSON from empty output.
3. **`ResearchSynthesis`'s list fields too strict.** With `num_ctx` fixed, the model
   produced complete, well-formed JSON — but intermittently collapsed a `list[str]`
   field (`conflicting_evidence`/`exclusion_criteria`/`limitations`) into a bare string
   instead of a single-item list, failing Pydantic validation on both attempts even
   though the JSON itself parsed fine. Fixed with a `field_validator(mode="before")` on
   each of the three fields in `app/research/paper_assistant.py` that normalizes a
   string into `[string]` (or `[]` if blank) rather than gambling the whole call on
   prompt wording alone fixing a probabilistic model habit.
4. **PubMed/openFDA sent the raw clinician question verbatim.** Once generation itself
   was reliable, the response came back with `research_mode_used: false` even though
   `sources: [pubmed, fda]` was requested — external retrieval was silently finding
   nothing. The backend log showed why: PubMed's esearch implicitly ANDs every
   space-separated word, so a filler word like "what" or "for" that never co-occurs with
   the clinical terms in any article's metadata zeroed out the whole result set; openFDA
   400'd outright on a literal quoted full-sentence phrase containing `"(SLT)"` and
   `"?"`. Fixed with `clean_search_terms()` in `app/research/providers/base.py`
   (punctuation + stopword stripping), applied to PubMed and FDA only — confirmed live
   against the real APIs both in isolation (0 PubMed hits -> 2; openFDA 400 -> 200) and
   through the full pipeline afterward.

With all four fixed, the exact same query
(`"What is the recent evidence for selective laser trabeculoplasty (SLT) as first-line
treatment for open-angle glaucoma?"`, `sources: [pubmed, fda]`) completed successfully
end-to-end in 9m34s: `research_mode_used: true`, two real PubMed citations with real
`pubmed.ncbi.nlm.nih.gov` URLs, a correctly-hedged synthesis noting SLT's role as a
first-line alternative alongside topical therapy, and `evidence_quality: moderate` —
honest, not overclaiming, for two abstracts' worth of evidence. `GET /api/research/status`
was also confirmed to report real, non-assumed state: `enabled: true` (from
`ENABLE_RESEARCH=true`) with `searxng_reachable: false` and `sources_available:
[pubmed, fda, clinicaltrials]` while no SearXNG container was running — exactly the
honest degraded-capability behavior spec §103 requires. All test-run rows and cached web
results created during live testing were deleted from the dev database afterward (same
cleanup discipline as every prior phase's live verification).

### Deliberate scope notes

- **De-identification is narrow, not general NER.** `deidentify.py` strips the current
  patient's own known identifiers plus generic identifier-shaped patterns (email/phone/
  MRN/street address) — it does not attempt general name detection. A broader NER pass
  risks false positives on ordinary clinical terminology (verified via a dedicated test:
  "Marcus Gunn pupil" must survive de-identification untouched), which spec §2's
  "never invent/never distort" ethos argues against more than a narrower net argues for.
- **WHO/CDC/NICE were not integrated.** None expose a simple public search API without
  registration or scraping (unlike PubMed/openFDA/ClinicalTrials.gov's open APIs) — a
  deliberate scope decision, not an oversight, consistent with this project's "skip
  honestly rather than fake it" pattern.
- **`web_cache` is SQLite-only, not also a Qdrant collection.** Spec §14 lists
  `web_cache` as a named collection, but embedding + reranking every live web result
  through the already-documented ~6-7 minute CPU reranker path would make Research Mode
  impractically slow on top of everything else it already does. Ranking uses a fast
  deterministic lexical+authority-tier score computed at query time instead (`research/
  ranking.py`); the SQLite cache alone already satisfies spec §72's stated goals
  (reproducibility, speed, demo reliability, auditability).

## Phase 12 — what exists right now

```text
backend/app/
  models/knowledge_document.py      KnowledgeDocument (title/source/specialty/
                                     authority_tier/tags/archived) + KnowledgeDocument
                                     Version (one row per upload: file_hash/effective_
                                     date/review_date/is_active/ingestion_status/
                                     chunk_count). Reuses AuthorityTier (Phase 11) and
                                     IngestionStatus (Phase 05's Report) rather than
                                     duplicating either enum. "Active" is a per-version
                                     flag, not a document-level FK to its active version
                                     — activating/rolling-back is a single-row flip, and
                                     it sidesteps a circular FK between the two tables
  services/knowledge.py             `activate_version()` is the one place that changes
                                     what's retrievable: (re)indexes the target version
                                     — idempotent, since `index_document` deletes any
                                     existing chunks for that file_hash first — then
                                     deindexes+deactivates whichever version was
                                     previously active. Upload, explicit rollback
                                     (activate-version), and FAILED-version recovery
                                     (reindex) all share this one code path. Indexing
                                     itself is keyed off file_hash, reusing exactly
                                     `rag/indexing.py`'s existing mechanism (the same one
                                     `scripts/ingest_knowledge.py` already relied on) —
                                     no change to `Chunk` or the indexing pipeline needed
                                     for versioning to work
  api/knowledge.py                  Every route is AdminUser-gated (spec §18: "Manage
                                     knowledge base" is listed only under Admin's
                                     permissions, unlike patient-facing routes where
                                     Doctor also has write access). Upload/reindex/
                                     activate-version all return immediately (ingestion_
                                     status: queued) and run extraction/chunking/
                                     embedding/indexing in a BackgroundTask — same
                                     poll-for-real-status pattern as report ingestion
                                     (spec §122)

frontend/src/
  api/auth.ts                       +useIsAdmin() — same presentation-only rationale as
                                     useCanWrite; the backend's AdminUser dependency is
                                     what actually enforces the gate
  api/knowledge.ts                  Document/version CRUD hooks; useKnowledgeDocument
                                     polls every 2s while any version is queued/
                                     processing, matching the report-status-polling
                                     convention
  pages/Knowledge/index.tsx         List + create form + a selected document's detail
                                     panel (versions with status badges, Upload New
                                     Version, per-version Activate for rollback,
                                     document-level Reindex/Archive)
```

### Live verification — real uploads, real embeddings, real Qdrant, not mocked

The full document lifecycle was exercised against the real running backend with a real
admin account and real synthetic PDFs (not mocked, matching every other phase): create
document -> upload version 1 (effective_date set) -> BackgroundTask completed with
`is_active: true`, `ingestion_status: completed`, `chunk_count: 1` -> upload version 2 ->
confirmed version 1 auto-deactivated with `chunk_count` reset to 0 (its chunks actually
deindexed from Qdrant, not just flagged) -> `activate-version` rollback to version 1 ->
confirmed version 1 re-indexed (`chunk_count: 1` again) and version 2 correctly
deindexed -> `reindex` confirmed the `queued` -> `processing` -> `completed` transition
against the currently-active version -> `archive` confirmed the document disappears from
the default `GET /documents` list (still visible with `include_archived=true`) and its
active version's chunks are deindexed. All test rows, uploaded files, and the live-test
admin account were deleted from the dev database afterward.

### Deliberate scope notes

- **No hard delete.** Mirrors `Report.archived`'s soft-delete-only convention — spec's
  own data model bullet list says "archive," never "delete," as the terminal admin
  action; version history stays in SQLite for audit purposes even after archiving.
- **No separate `ingestion_jobs` row per version.** Phase 05's `IngestionJob` table is
  strictly `report_id`-scoped (`NOT NULL` FK). Rather than relaxing that constraint or
  adding a second per-stage job-log table for a simpler pipeline (no OCR-stage/identity-
  check/lab-extraction branching a knowledge document needs), `ingestion_status`/
  `ingestion_error`/`chunk_count` live directly on `KnowledgeDocumentVersion` — the same
  place `Report.ingestion_status`/`extraction_error` already live on `Report` itself.
  Satisfies spec's "ingestion status"/"ingestion monitoring" bullets without a second,
  thinner job-tracking mechanism alongside the first.

## Domain note

The bundled knowledge-base source material (`data/*.pdf`, `data/eye_conditions.json`) is
**ophthalmology**-focused, supplied by the project owner. Phase 05/07 ingestion and
Phase 14 demo-patient seeding will target this domain specifically (e.g. cataract,
glaucoma, diabetic retinopathy cases) rather than the illustrative
cardiology/diabetes/renal examples used as generic examples in the Master Build Prompt.
Nothing in the architecture is ophthalmology-specific — swapping `data/` for another
specialty's reference material does not require code changes.

## UI design reference

`docs/ui-reference/` holds the two screenshots supplied as the visual source of truth
(spec §20): the GMS case-study slide and the reference dashboard screenshot. Phase 02
matches this look closely; Phase 01's Overview page is intentionally minimal (status
only) rather than a preview of that visual design.
