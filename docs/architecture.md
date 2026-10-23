# Architecture

## Backend (`backend/app`)

| Package | Responsibility |
|---|---|
| `core/` | Environment config, logging, security (Argon2id, session tokens, Fernet secret encryption), error types |
| `models/` | SQLAlchemy 2 models: users/sessions, patients + encounters/conditions/allergies/medications/observations, documents/chunks, conversations/messages, AI runs, settings, audit, web cache |
| `services/runtime_config.py` | The DB-stored, admin-editable configuration (LLM, vision, embeddings, reranker, retrieval, vector store, clinical model, formulary, branding, security). Secrets encrypted at rest, masked in the API |
| `ai/` | Provider layer: `llm.py` (Ollama native + OpenAI-compatible streaming, multimodal, JSON mode fallback, think-tag filter, per-endpoint concurrency), `embeddings.py`, `reranker.py`, `registry.py` (builds clients from the current config on every request) |
| `ingestion/` | Parsers (PDF incl. tables, DOCX, XLSX, CSV, TXT/MD, JSON packs, images), structure-aware chunking, lab extraction (document-stated ranges only), identity checking |
| `rag/` | `vector_store.py` (Qdrant embedded/server), `lexical.py` (SQLite FTS5 BM25), `retrieve.py` (fusion, rerank, de-dup, budget, trace), `indexing.py` (dual-index writes, full re-index) |
| `clinical/` | Patient-record context builder, prompts, citation validation and coverage |
| `formulary/` | India medicine catalogue (`data/in.json`), dose/frequency parsing, patient facts (CKD-EPI 2021 eGFR) and the prescription rule engine |
| `services/` | Documents lifecycle, chat orchestration (SSE events), structured tools, vision, audit |
| `api/` | Thin FastAPI routers with role dependencies (`AdminUser`, `WriteUser`, `AIUser`, `CurrentUser`) |
| `devtools/mock_ai.py` | OpenAI-compatible mock server for GPU-free development and E2E tests |

### Chat turn

1. Persist the question; emit `user_message`.
2. Retrieve: dense (Qdrant, filtered by patient) + BM25 (FTS5, filtered by patient) for the
   patient scope and the knowledge library → weighted RRF → rerank → de-dup → token budget.
   Emit `sources` with the full trace.
3. No evidence and no patient record → abstain without calling the model.
4. Prompt = rules + structured record `[R]` + labelled evidence `[P#]/[K#]` + history.
   Stream `token` events.
5. Validate citations (remove labels not provided), compute coverage, persist answer with
   trace, emit `done`.

### Document ingestion

Validate type/magic bytes/size → SHA-256 duplicate check → store → background processing:
parse (vision transcription for images and text-less PDF pages) → identity check against the
chart (mismatch ⇒ quarantine) → lab extraction with provenance → chunk → index (dense + BM25;
the indexed text is prefixed with title/section for recall, stored text stays clean).

## Frontend (`frontend/src`)

| Path | Responsibility |
|---|---|
| `app/appearance.tsx` | Theme engine: CSS-variable tokens for light/dark/high-contrast, runtime accent colour (contrast-safe), density, radius, type scale, motion; synced to user preferences |
| `components/ui/` | Accessible component kit on Radix primitives |
| `components/layout/` | Sidebar, top bar, ⌘K command palette, status indicator, user menu |
| `components/clinical/` | Citation-aware Markdown, badges, document drawer, tool output renderers, record dialogs |
| `features/*` | One folder per area: home, inbox, patients, workspace tabs, assistant, tools, library, audit, settings, consult, frontdesk, today, print |
| `api/` | Typed API client, SSE reader, TanStack Query hooks |
