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
| 05 | Report ingestion: upload, PDF/DOCX/XLSX/image parsing, OCR, identity checking, ingestion jobs | Not started |
| 06 | Structured clinical data: lab extraction, trend engine, medication reconciliation, change engine | Not started |
| 07 | Local RAG core: embeddings, Qdrant collections, dense+BM25 retrieval, RRF fusion, reranking, dedup | Not started |
| 08 | Clinical chat: conversations, streaming, evidence panel, citation/grounding validation | Not started |
| 09 | Vision: image upload, structured extraction, image-to-RAG, comparison | Not started |
| 10 | Clinical modules: summary, SOAP, entity extraction, guideline Q&A, differential support | Not started |
| 11 | Web research: Research Mode, de-identification, PubMed/FDA, optional SearXNG, web cache | Not started |
| 12 | Knowledge administration: upload, versioning, reindex, admin settings | Not started |
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
