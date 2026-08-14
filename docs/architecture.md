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
| 03 | Authentication: login/logout, roles, sessions, protected routes | Not started |
| 04 | Patient system: CRUD, search, workspace, encounters, conditions, allergies, medications, timeline | Not started |
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
