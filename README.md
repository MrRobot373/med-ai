# GMS Clinical AI

**Clinical intelligence, grounded in evidence.** A local-first clinical platform that
combines patient records, document ingestion, hybrid retrieval (RAG) and
evidence-cited AI — with every model endpoint swappable from the UI.

> Clinical decision support. AI output is always a draft for the treating clinician to
> verify against the cited sources. The bundled patient files are fictional; their medical
> images come from openly licensed, de-identified datasets (see `patient-files/`).

---

## Highlights

| | |
|---|---|
| **A co-pilot for the consultation** | Today's patients, each with a **pre-visit brief** (what changed since last time, what to ask). During the visit: notes and vitals, a **second look at the diagnosis**, a prescription that is **checked live** against the patient's age, weight, kidney (CKD-EPI 2021) and liver function, allergies, problems and current medicines, an **AI dose review** (MedGemma 27B by default), investigations that are **matched automatically** to reports when they come back, and a printable prescription. Everything is stored and feeds the next visit. |
| **India formulary** | Indian generics, brands and combinations (Dolo 650, Pan-D, Augmentin 625, Glycomet-GP…) with dose limits, renal/hepatic/older-adult (Beers 2023)/pregnancy/paediatric rules, interactions and allergy groups. Critical findings need a recorded reason to proceed. Regions are data files, so the engine scales beyond India. |
| **Bring your own models** | Ollama, LM Studio, vLLM, llama.cpp, OpenAI, OpenRouter, Groq, Together — or any OpenAI-compatible endpoint. LLM, vision, embeddings and reranker are configured independently in **Settings**, tested live before saving, and take effect on the next request (no restart). API keys are encrypted at rest. |
| **Evidence you can verify** | Hybrid retrieval (Qdrant vectors + SQLite FTS5 BM25 → reciprocal-rank fusion → optional reranking → de-dup → token budget). Every statement carries a citation chip (`P1` patient document, `K2` library, `R` structured record). Invalid citations are stripped and reported; a **"Why this answer"** panel shows every stage, score and timing. |
| **Safe by construction** | Patient isolation is enforced in both indexes and re-checked in code. Uploaded documents are identity-checked against the chart; suspected wrong-patient files are **quarantined** (no values extracted, excluded from AI) until a clinician confirms. Reference ranges are never invented. The assistant abstains instead of guessing. Patient data never leaves your server unless you point a model at an external endpoint. |
| **Report & radiology viewer** | Every patient dashboard centres on a large viewer for PDFs, photos, ECGs and **DICOM** (X-ray/CT/MRI — header metadata indexed, pixels windowed and rendered), with thumbnails, paging, zoom and full screen. |
| **Patient-specific scores** | Only the scores that apply to *this* patient, computed deterministically from documented data with sources shown: KDIGO CKD stage & risk, CHA₂DS₂-VASc, glycaemic control vs target, metformin renal dosing, apixaban dose criteria. Missing inputs are listed, never assumed. |
| **Built for clinicians** | Patient workspace (overview, timeline, documents, trended results with provenance, medications, problems & allergies, encounters), clinical inbox, streaming assistant, structured tools (case summary, SOAP, differential, report comparison, medication reconciliation, entity extraction, image analysis, guideline Q&A) — all outputs are reviewable drafts. |
| **Yours to brand and tune** | White-label name, logo, tagline, colours and disclaimer. Per-user light/dark/system theme, accent colour, density, corner style, text size, typeface, high contrast and reduced motion. ⌘K command palette and keyboard shortcuts. |
| **Managed** | Roles (admin / clinician / viewer / **front desk** — registration, the day list and report uploads, never clinical content), user management, full audit log with CSV export, answer feedback, live service health, retrieval playground, one-click re-indexing when the embedding model changes. |

## Quick start

Requirements: **Python 3.11+**, **Node 20+**. Optional: [Ollama](https://ollama.com) with a GPU.

```bash
scripts/setup.sh            # venv + deps, frontend deps, .env with a fresh secret   (Windows: scripts\setup.bat)
scripts/demo.sh --mock      # no models needed: bundled mock AI, demo data, http://localhost:8000
```

Staff accounts created by the seed:

| Person | Role | Email | Password |
|---|---|---|---|
| Dr. Ananya Rao | Clinician | `ananya.rao@lifecaremedico.in` | `Clinic@2026` |
| Meera Pillai | Front desk | `meera.pillai@lifecaremedico.in` | `Desk@2026` |
| Vikram Shah | Administrator | `admin@lifecaremedico.in` | `Admin@2026` |
| Rahul Menon | Read-only (audit) | `rahul.menon@lifecaremedico.in` | `Audit@2026` |

The seed loads the 15 patient folders in [`patient-files/`](patient-files/README.md) — lab reports, X-ray,
ultrasound, CT and MRI (some as DICOM), ECGs, discharge summaries and outside prescriptions — and books
five of them on today's list. Change these passwords before any real use.

### With real local models (Ollama)

```bash
ollama pull qwen3.5:9b               # chat + vision (multimodal)
ollama pull qwen3-embedding:0.6b     # embeddings
scripts/demo.sh                      # uses the defaults in .env
```

Any other provider: sign in as admin → **Settings → AI models / Embeddings & reranking**,
pick a preset, paste a key if needed, **Test**, **Save**. See
[docs/configuration.md](docs/configuration.md) for recipes.

> The mock AI (`--mock`) assembles answers from the evidence it is given so the whole
> product can be exercised without a GPU. It is not a model; never use it clinically.

### Development

```bash
scripts/dev.sh               # API with reload on :8000, Vite on :5173 (proxying /api)
```

### Docker

Step-by-step guide for a demo or test server on your network (Docker or bare metal, test AI or Ollama, firewall, HTTPS, backups and a manual test plan): [docs/DEPLOY_LOCAL.md](docs/DEPLOY_LOCAL.md).

```bash
cp .env.example .env         # set APP_SECRET_KEY
docker compose up -d --build                  # app on :8000, talks to Ollama on the host
docker compose --profile qdrant up -d         # optional Qdrant server
docker compose exec app python -m app.seed demo
```

## Architecture

```
React + Vite + Tailwind + Radix ──►  FastAPI  ──►  SQLite (records, chunks, FTS5 BM25, audit, settings)
   (sidebar app, ⌘K, theming)          │      ──►  Qdrant (embedded folder or server) — dense vectors
                                       │
                         ┌─────────────┼─────────────────────────────┐
                    Ingestion      Hybrid retrieval            Generation
             parse · vision OCR    dense + BM25 → RRF →      prompt with labelled
             identity check        rerank → de-dup →         evidence → stream →
             lab extraction        budget (+ trace)          validate citations
                         └─────────────┴──────────────┬──────────────┘
                                                      ▼
                       Provider layer (runtime config): Ollama | OpenAI-compatible | in-process
```

Details: [docs/architecture.md](docs/architecture.md).
Visual design system (colours, type, components, clinical patterns, Figma setup): [docs/DESIGN.md](docs/DESIGN.md).

## Knowledge library

The library is organised by **specialty domains** (cardiology, nephrology, ophthalmology,
pharmacology, hospital policies, …). Starter packs live in [`knowledge-packs/`](knowledge-packs/)
— one folder per domain. See [docs/knowledge-domains.md](docs/knowledge-domains.md) for the
full suggested taxonomy and guidance on what to add.

## Project layout

```
backend/        FastAPI app (app/api, services, ai providers, rag, ingestion, clinical), Alembic, tests
frontend/       React app (src/features/*, components/ui kit, app/appearance theming), unit + e2e tests
knowledge-packs/  starter reference content by specialty
scripts/        setup / dev / demo scripts (bash + Windows)
docs/           architecture, configuration recipes, knowledge taxonomy
```

## Testing

```bash
cd backend && .venv/bin/pytest            # 60 tests: auth/RBAC, isolation, ingestion, DICOM, quarantine, scores, chat, tools, providers
cd frontend && npm test && npm run lint   # unit tests, ESLint, `npx tsc -b` for types
cd frontend && E2E_BASE_URL=http://localhost:8000 npm run e2e   # against a seeded stack
```

## Security notes

- Set a strong `APP_SECRET_KEY` (sessions and API-key encryption) and change the bootstrap
  admin password. Serve behind HTTPS and set `COOKIE_SECURE=true`.
- External LLM endpoints receive patient context in prompts; Settings warns when a
  non-local endpoint is configured. Use only providers covered by your data agreements.
- See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for dependencies and licences.
