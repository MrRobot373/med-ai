# GMS Clinical AI

Local-first, multimodal clinical RAG & decision-support platform. Built against the
Master Build Prompt in this repo's root (`MASTER BUILD PROMPT — GMS Local Multimodal
Clinical RAG & Decision-Support Platform.md`) as a 16-phase program — see
[docs/architecture.md](docs/architecture.md) for the phase roadmap and current status.

> **Current status: Phase 05 — Report Ingestion.** Foundation (01), the dashboard (02),
> authentication (03), patient management (04), and now report ingestion — upload,
> PDF/DOCX/XLSX/image/DICOM parsing, OCR fallback (real, unmocked, CPU-only), report-type
> classification, and conservative patient-identity mismatch checking — all exist and
> work end-to-end. Structured labs, RAG, chat, and vision are not implemented yet — the
> nav and patient-workspace tabs tell you exactly which phase each section lands in, and
> every capability card links to a real (if not-yet-built) destination rather than a dead
> end.

The initial knowledge-base domain for this deployment is **ophthalmology** — see
`data/*.pdf` (anatomy, disease, referral-guideline, and instrument references) and
`data/eye_conditions.json` (structured disease/symptom/management dataset). The 3 seeded
demo patients (cataract, glaucoma, diabetic retinopathy) already draw on this domain;
the PDFs themselves feed the `medical_knowledge` Qdrant collection starting in Phase 07.
Swap `data/`'s contents for a different specialty at any time; nothing in the code
hardcodes ophthalmology.

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
on CPU and download automatically from Hugging Face the first time the RAG pipeline
(Phase 07) uses them. No account/API key is required (public models).

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
```

## Running

```bat
start-demo.bat
```

This checks Docker, starts Qdrant, checks Ollama, runs migrations, seeds demo accounts
and patients, generates sample report files for the upload demo, starts the backend
(`:8000`) and frontend (`:5173`) in separate windows, polls `/api/health` until it
responds, and opens the browser. `stop-demo.bat` shuts services down.
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

## Repository layout

See [docs/architecture.md](docs/architecture.md). Reference UI screenshots that guided
the visual design live in `docs/ui-reference/`.

## Third-party software

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
