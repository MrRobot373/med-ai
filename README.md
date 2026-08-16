# GMS Clinical AI

Local-first, multimodal clinical RAG & decision-support platform. Built against the
Master Build Prompt in this repo's root (`MASTER BUILD PROMPT — GMS Local Multimodal
Clinical RAG & Decision-Support Platform.md`) as a 16-phase program — see
[docs/architecture.md](docs/architecture.md) for the phase roadmap and current status.

> **Current status: Phase 09 — Vision.** Foundation (01), the dashboard (02),
> authentication (03), patient management (04), report ingestion (05), structured
> clinical data (06), the local retrieval pipeline (07), clinical chat (08), and now
> vision — image/DICOM reports are analyzed automatically on upload (structured,
> spec §60-shaped JSON: image type, observations, measurements, clinical entities,
> quality limitations, uncertainties — describing observable findings, never
> presenting a diagnosis as fact), indexed into a real `patient_vision` collection so
> findings become genuine, citable ([V#]) chat evidence, and a previous/current image
> comparison tool runs a real joint vision-model call plus a real guideline-evidence
> lookup on the extracted differences. All verified end-to-end against real
> Ollama/Qdrant, not mocked. Clinical modules (SOAP, differential support, etc.) aren't
> implemented yet — the nav and patient-workspace tabs tell you exactly which phase
> each section lands in, and every capability card links to a real (if not-yet-built)
> destination rather than a dead end.
>
> **Known latency issue, not yet fixed:** reranking a patient-scoped chat question
> against the knowledge base measured ~6-7 minutes in live testing — see
> docs/architecture.md's Phase 08 section ("Hybrid-reasoning model latency") for the
> full finding (a separate, already-fixed bug in that same session made `qwen3.5:9b`'s
> default "thinking" mode silently swallow the entire response budget before emitting
> any visible content — that part is fixed; the reranker latency is a pre-existing
> Phase 07 characteristic flagged here as a follow-up, not newly introduced). Vision
> analysis itself is fast (`"think": false` applies to every Ollama call, vision
> included) — a single-image analysis completed in well under a minute in live testing.

The initial knowledge-base domain for this deployment is **ophthalmology** — see
`data/*.pdf` (anatomy, disease, referral-guideline, and instrument references) and
`data/eye_conditions.json` (structured disease/symptom/management dataset). The 3 seeded
demo patients (cataract, glaucoma, diabetic retinopathy) already draw on this domain;
`scripts/ingest_knowledge.py` feeds a curated subset of the PDFs into the
`medical_knowledge` Qdrant collection (see that script and docs/architecture.md's Phase
07 section for why the full multi-hundred-page textbooks are an opt-in `--all`, not the
default). Swap `data/`'s contents for a different specialty at any time; nothing in the
code hardcodes ophthalmology.

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | On Windows, use the `python` launcher (not `python3`). |
| Node.js 20+ | Tested with Node 24 / npm 11. |
| Docker Desktop | Runs Qdrant (and, later, SearXNG for Research Mode). |
| Ollama | Must be running locally with the configured model pulled: `ollama pull qwen3.5:9b`. |
| NVIDIA GPU, 8 GB VRAM | Target machine profile — see `.env.example` `RAG_PROFILE`. |

Embedding (`Qwen/Qwen3-Embedding-0.6B`) and reranker (`Qwen/Qwen3-Reranker-0.6B`) models
are **not** Ollama models — they run locally via `sentence-transformers`/`transformers`
on CPU and download automatically from Hugging Face the first time the RAG pipeline uses
them (a report upload, or `scripts/ingest_knowledge.py`). No account/API key is required
(public models), but the first download is a few hundred MB per model and — on CPU —
embedding is genuinely slow; see docs/architecture.md's Phase 07 section ("CPU embedding
performance") for real measured numbers and the fixes already applied.

## Setup

```bat
:: Backend
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m alembic upgrade head

:: Frontend
cd ..\frontend
npm install

:: Config
cd ..
copy .env.example .env
:: edit .env if your ports/URLs differ from the defaults

:: Demo accounts (admin/doctor/viewer) — passwords are generated, never hardcoded;
:: printed once and saved to data/sqlite/.demo_credentials.txt (gitignored)
backend\.venv\Scripts\python scripts\seed_demo.py

:: Demo patients (3 synthetic ophthalmology cases — cataract, glaucoma, diabetic
:: retinopathy — with several months of encounter history). Idempotent.
backend\.venv\Scripts\python scripts\seed_demo_patients.py

:: Sample report files for the upload demo (normal + scanned/OCR + a deliberate
:: identity-mismatch example). Gitignored — regenerate anytime.
backend\.venv\Scripts\python scripts\generate_sample_reports.py

:: Ingest reference clinical guidelines into the RAG knowledge base. Runs the real
:: embedding model on CPU — expect several minutes (longer the first time, while the
:: model itself downloads). Idempotent; safe to re-run.
backend\.venv\Scripts\python scripts\ingest_knowledge.py
```

## Running

```bat
start-demo.bat
```

This checks Docker, starts Qdrant, checks Ollama, runs migrations, seeds demo accounts
and patients, generates sample report files for the upload demo, ingests reference
clinical guidelines into the RAG knowledge base (several minutes — not a hang), starts
the backend (`:8000`) and frontend (`:5173`) in separate windows, polls `/api/health`
until it responds, and opens the browser. `stop-demo.bat` shuts services down.
`health-check.bat` runs the same checks as `/api/health` from the command line.
`reset-demo.bat` is a stub until Phase 14 (synthetic demo dataset) — it says so and
exits non-zero rather than pretending to do something.

Manual run (equivalent, useful during development):

```bat
docker compose up -d qdrant
cd backend && .venv\Scripts\python -m uvicorn app.main:app --reload
cd frontend && npm run dev
```

## Testing

```bat
:: Backend
cd backend
.venv\Scripts\pytest

:: Frontend
cd frontend
npm run test
npm run build
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `docker info` fails / Qdrant won't start | Start Docker Desktop, wait for it to fully initialize, retry. |
| `/api/health/ollama` shows `reachable: false` | Start Ollama (`ollama serve` or the desktop app). |
| `/api/health/ollama` shows `model_available: false` | `ollama pull qwen3.5:9b` (or whatever `OLLAMA_MODEL` is set to). |
| `/api/health/qdrant` shows `reachable: false` | `docker compose up -d qdrant`, check port 6333 isn't in use by another process. |
| Frontend can't reach the backend | Confirm backend is on `:8000` and `frontend/vite.config.ts`'s dev proxy target matches; check `FRONTEND_ORIGIN` in `.env` for CORS. |
| `alembic upgrade head` fails | Confirm `DATABASE_URL` in `.env` points at a writable path under `data/sqlite/`. |
| `scripts/ingest_knowledge.py` (or a report upload) seems to hang | It's very likely still running, not hung — CPU embedding is genuinely slow (see docs/architecture.md's Phase 07 section). A single ~500-token chunk can take tens of seconds on CPU; give it several minutes, and check Task Manager for active CPU usage on the python process before assuming it's stuck. |
| A patient-scoped Clinical AI question takes several minutes before the first token appears | Likely still running, not hung — see docs/architecture.md's Phase 08 section ("Hybrid-reasoning model latency"). Reranking against `medical_knowledge` measured ~6-7 minutes live; `general`/`local_knowledge_only` scope questions and questions answerable from structured facts alone are much faster since they skip reranking or retrieval entirely. |
| Clinical AI streams zero tokens and abstains even though the patient clearly has relevant data | Should not reproduce after this session's fix (`"think": false` is now sent on every Ollama chat request) — if it does, confirm the running backend was restarted after pulling this change, since `qwen3.5:9b`'s default "thinking" mode can silently consume the entire response budget before any visible content is emitted. |
| An image/DICOM report's ingestion status stays `processing` at `stage: "analyzing_image"` for a while | Normal — vision analysis makes a real Ollama call as part of ingestion (automatic for image/DICOM reports, same pattern as OCR). It's fast once thinking is disabled (well under a minute in live testing), but a cold/loaded Ollama can still take longer; check `GET /api/reports/{id}/status` for `error`, not just elapsed time, before assuming it's stuck. |
| A DICOM report's vision analysis shows `status: "not_applicable"` | Expected when the file's pixel data can't be decoded into a preview (e.g. an unsupported compressed transfer syntax — see docs/architecture.md's Phase 05 DICOM notes). Not a bug; `analysis_error` on the response explains why. |

## Repository layout

See [docs/architecture.md](docs/architecture.md). Reference UI screenshots that guided
the visual design live in `docs/ui-reference/`.

## Third-party software

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
