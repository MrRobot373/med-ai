# GMS Clinical AI

Local-first, multimodal clinical RAG & decision-support platform. Built against the
Master Build Prompt in this repo's root (`MASTER BUILD PROMPT — GMS Local Multimodal
Clinical RAG & Decision-Support Platform.md`) as a 16-phase program — see
[docs/architecture.md](docs/architecture.md) for the phase roadmap and current status.

> **Current status: Phase 14 — Demo System.** Foundation (01), the dashboard (02),
> authentication (03), patient management (04), report ingestion (05), structured
> clinical data (06), the local retrieval pipeline (07), clinical chat (08), vision (09),
> six structured clinical workflows (10), Web Research Mode (11), Knowledge
> Administration (12), Audit & Feedback (13), and now the one-click Demo System (14):
> five synthetic patients, six real Demo Scenarios, `start-demo.bat`/`reset-demo.bat`
> covering the full spec §86/§87 sequence, and model warm-up. Every generated
> clinical-module result remains an explicit, timestamped draft — spec §63's "never
> automatically saved as finalized clinical record." Live-verified against real
> Ollama/Qdrant/PubMed/openFDA — see docs/architecture.md's per-phase sections for the
> full findings, including several real bugs found and fixed during live testing across
> phases (Ollama timeout, an unset `num_ctx` silently truncating large prompts, an
> overly-strict Research schema, PubMed/openFDA rejecting a raw natural-language
> question, and non-deterministic synthetic-document byte output defeating a dedup
> check). Only Phase 15 (evaluation suite) and Phase 16 (final validation) remain — the
> nav tells you exactly which phase each remaining section lands in.
>
> **Known latency issue — fixed for GPU deployments, still present on CPU-only ones:**
> reranking a patient-scoped question against the knowledge base measured ~6-7 minutes
> in CPU-only live testing (Phase 08's Clinical Chat, and again in Phase 10's Guideline
> Q&A / Differential Support / Report Comparison, which share the same retrieval code).
> Moving the embedding/reranker models to GPU (see "GPU acceleration" below) measured
> well under a second for the same real workload — see docs/architecture.md's Phase 14
> "GPU acceleration" notes for the exact numbers. Running CPU-only (spec §12's default)
> still carries the original cost. A separate, already-fixed bug in an earlier session
> made `qwen3.5:9b`'s default "thinking" mode silently swallow the entire response
> budget before emitting any visible content — that part is fixed regardless of device.
> Modules that don't need retrieval (SOAP, summary, entity extraction) are fast — well
> under 90 seconds live even on CPU, since `"think": false` applies to every Ollama call.

The initial knowledge-base domain for this deployment is **ophthalmology** — see
`data/*.pdf` (anatomy, disease, referral-guideline, and instrument references) and
`data/eye_conditions.json` (structured disease/symptom/management dataset). The 5 seeded
demo patients (cataract, glaucoma, diabetic retinopathy, wet AMD, and a multi-morbidity
case) already draw on this domain; `scripts/ingest_knowledge.py` feeds a curated subset
of the PDFs into the `medical_knowledge` Qdrant collection (see that script and
docs/architecture.md's Phase 07 section for why the full multi-hundred-page textbooks
are an opt-in `--all`, not the default). Swap `data/`'s contents for a different
specialty at any time; nothing in the code hardcodes ophthalmology.

## GPU acceleration (optional)

Spec §12 defaults embedding/reranker execution to CPU, to keep GPU VRAM free for the
main LLM. If your GPU has spare headroom, both can run on GPU instead — a real,
measured **~1,500x** throughput improvement for embedding (0.47s vs. ~737s for the same
38-chunk real workload) and reranking a query against the knowledge base dropping from
the ~6-7 minutes noted above to well under a second. See docs/architecture.md's Phase 14
section for the full methodology and numbers.

To enable it:

```bat
:: 1. Install a CUDA-enabled PyTorch build (replaces the default CPU-only wheel pip
::    resolves from requirements.txt/pyproject.toml — check pytorch.org for the wheel
::    tag matching your driver's CUDA version; this project's dev machine used cu130):
backend\.venv\Scripts\python -m pip install --index-url https://download.pytorch.org/whl/cu130 "torch==2.13.0+cu130"

:: 2. In .env (copy from .env.example if you haven't already):
EMBEDDING_DEVICE=cuda
RERANKER_DEVICE=cuda
```

**VRAM budget matters — measured real numbers on an 8.5GB RTX 5050:** embedding model
alone ~3.8GB, +reranker ~4.9GB, +the LLM (`qwen3.5:9b`, loaded by Ollama) ~7.8GB total —
roughly 95% of an 8GB card with all three resident at once, no crash but very little
headroom. A smaller/shared GPU may not have room for all three; revert either or both
`_DEVICE` settings to `cpu` if you see CUDA out-of-memory errors.

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
(CPU by default, GPU optionally — see "GPU acceleration" below) and download
automatically from Hugging Face the first time the RAG pipeline uses them (a report
upload, or `scripts/ingest_knowledge.py`). No account/API key is required (public
models), but the first download is a few hundred MB per model and — on CPU — embedding
is genuinely slow; see docs/architecture.md's Phase 07 section ("CPU embedding
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

:: Demo patients (5 synthetic ophthalmology cases — cataract, glaucoma, diabetic
:: retinopathy, wet AMD, and a multi-morbidity patient — each with several months of
:: encounter history). Idempotent.
backend\.venv\Scripts\python scripts\seed_demo_patients.py

:: Sample report files for the upload demo (normal + scanned/OCR + a deliberate
:: identity-mismatch example). Gitignored — regenerate anytime.
backend\.venv\Scripts\python scripts\generate_sample_reports.py

:: Ingest those sample reports into their matching demo patients through the real
:: upload/OCR/vision/RAG-indexing pipeline — so labs, vision analyses, and report
:: comparisons are real out of the box, not something you upload live first.
:: Idempotent by (patient, filename).
backend\.venv\Scripts\python scripts\seed_demo_reports.py

:: Ingest reference clinical guidelines into the RAG knowledge base. Runs the real
:: embedding model on CPU — expect several minutes the first time (longer still while
:: the model itself downloads). Idempotent: unchanged files are skipped on re-run
:: (pass --force to re-index anyway).
backend\.venv\Scripts\python scripts\ingest_knowledge.py

:: Warm the generation/embedding/reranker models so the first real demo query isn't
:: also the slow cold-start one. Best-effort/non-fatal.
backend\.venv\Scripts\python scripts\warm_models.py
```

## Running

```bat
start-demo.bat
```

This checks Docker, starts Qdrant (and SearXNG if `ENABLE_RESEARCH=true` in `.env`),
checks Ollama, runs migrations, seeds demo accounts/patients/reports (ingested through
the real pipeline) and the reference knowledge base, warms the models, runs the full
health check, starts the backend (`:8000`) and frontend (`:5173`) in separate windows,
polls `/api/health` until it responds, and opens the browser only once it's healthy.
`stop-demo.bat` shuts services down (including SearXNG if it was started).
`health-check.bat` runs the same checks as `/api/health` from the command line.
`reset-demo.bat` wipes the database/uploaded files/Qdrant collections and re-seeds a
fresh known-clean demo state — it asks for an explicit `YES` confirmation first and
never touches anything outside this machine's configured demo environment.

Once running, click **Demo Scenarios** on the Overview page (or go to `/demo`) for six
one-click scenarios — Patient Report Comparison, Longitudinal Lab Analysis, Vision +
Guideline RAG, Medication Reconciliation, Current Evidence Research, and Clinical Note
Generation — each opening the right synthetic patient and invoking the real pipeline,
never a replayed response.

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
| Guideline Q&A / Differential Support / Report Comparison take several minutes | Same reranker latency as patient-scoped Clinical AI questions above — these three modules retrieve from `medical_knowledge` too. SOAP, summary, and entity extraction don't retrieve anything and are fast (well under 90 seconds live). |
| A Research Mode query with external sources takes 9+ minutes | Expected — it combines the reranker latency above with a materially larger combined patient+local+external evidence prompt than any other module. Not a new problem; `research_num_ctx=16384` and `ollama_request_timeout_seconds=300` are already sized for this. |
| `POST /api/research/query` returns `generation_error: "Model did not return valid structured output after retry"` | Should not reproduce after this session's fixes — see docs/architecture.md's Phase 11 section for the two real causes found live (an unset `num_ctx` silently truncating the prompt, and the model occasionally returning a plain string instead of a JSON array for a list field, now tolerated by a Pydantic validator). If it does reproduce, `app/llm/structured.py` now logs a raw-output preview on parse failure — check the backend log for what the model actually returned before assuming it's the same bug. |
| `sources: [pubmed, fda]` was requested but the response shows `research_mode_used: false` | Check the backend log for the actual PubMed/openFDA HTTP calls — as of this session, both are sent a punctuation/stopword-cleaned query (`app/research/providers/base.py`'s `clean_search_terms()`), not the raw question, specifically because a raw natural-language question returned zero PubMed hits and a 400 from openFDA in live testing. If cleaned queries still return nothing, the topic genuinely may not have indexed literature/drug labels — that's an honest zero, not a bug. |
| A knowledge document upload stays `queued`/`processing` for a while | Normal — extraction/chunking/embedding runs in a `BackgroundTask` after the upload response returns, same pattern as report ingestion. Poll `GET /api/knowledge/documents/{id}` (the frontend does this every 2s automatically) rather than assuming it's stuck; check `ingestion_error` on the version once it settles to `failed`. |
| Embedding/reranking crashes with a CUDA out-of-memory error | Only possible if `EMBEDDING_DEVICE`/`RERANKER_DEVICE` are set to `cuda` in `.env` — there's no automatic CPU fallback mid-request (see docs/architecture.md's "GPU acceleration" section: a real 8.55GB card had ~95% VRAM used with the embedding model, reranker, and `qwen3.5:9b` all resident at once, with little headroom left). Fix: set the offending var back to `cpu` in `.env` and restart the backend, or free VRAM elsewhere (close other GPU processes, or run Ollama's model at a smaller quantization). |
| `GET /api/health/models` shows `"embedding": {"status": "package_missing"}` | `sentence-transformers` (or its `torch` dependency) isn't installed in the backend's venv — run `pip install -r backend/requirements.txt` from `backend/.venv`'s Python and restart. `"not_loaded"` instead of `"package_missing"` is normal and not an error — both models load lazily on first real use (embedding a chunk or reranking), not at backend startup. |
| `GET /api/health/models` shows `"ocr": {"status": "package_missing"}`, or a scanned PDF/image never gets OCR-recovered text | `easyocr` isn't installed, or `ENABLE_OCR=false` in `.env` (status would be `"disabled"` in that case, not `"package_missing"`) — `pip install -r backend/requirements.txt` and/or check `.env`, then restart. Ingestion still completes either way (spec §99: OCR failing on one page never fails the whole job), just without OCR-recovered text for that report — check `extraction_status`/`ocr_used` on `GET /api/reports/{id}`. |
| Research Mode returns `research_mode_used: false` even with `sources` requested and `ENABLE_RESEARCH=true` | No internet reachable from the backend host, or PubMed/openFDA/ClinicalTrials genuinely returned zero results for the (cleaned) query — both look identical from the response alone. Diagnostic: `curl -s https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi` from the backend's machine; a failure there confirms no internet, not a bug. Local-only scopes (`local_knowledge_only`, no `sources`) work fully offline regardless — Research Mode is the only feature with an internet dependency (spec §11/§136). |

## Repository layout

See [docs/architecture.md](docs/architecture.md). Reference UI screenshots that guided
the visual design live in `docs/ui-reference/`.

The plan for the next module — **MED AI Cardiac** (ECG analysis & monitoring) — and its
UI concept live in [docs/ecg/ECG_PRODUCT_PLAN.md](docs/ecg/ECG_PRODUCT_PLAN.md).

## Third-party software

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
