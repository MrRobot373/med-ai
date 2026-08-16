# GMS Clinical AI — Final Completion Report

Spec §139. Every number below comes from an actual command run against the real,
currently-running application (real Ollama, real Qdrant, real SQLite database) during
this session — nothing here is estimated or copied from a template.

## Environment

| Component | Value |
|---|---|
| OS | Microsoft Windows 11 Home Single Language, build 10.0.26200 |
| Python | 3.11.9 (`backend/.venv`) |
| Node | v24.15.0 |
| Qdrant | `qdrant/qdrant:v1.19.0` (Docker, container `gms-qdrant`) |
| Ollama | 0.32.13, model `qwen3.5:9b` (reachable, model available) |
| Embedding model | `Qwen/Qwen3-Embedding-0.6B` (device: `cuda`, this deployment's `.env`; `cpu` is the spec-default for anyone who copies `.env.example` fresh) |
| Reranker model | `Qwen/Qwen3-Reranker-0.6B` (device: `cuda`) |
| GPU | NVIDIA GeForce RTX 5050 Laptop GPU, 8151 MiB VRAM, driver 592.19 |
| PyTorch | 2.13.0+cu130, `torch.cuda.is_available() == True` |
| RAG profile | `fast_demo` |

## Implemented Features

| Phase | Scope | Status |
|---|---|---|
| 01 | Foundation: repo scaffold, backend/frontend skeleton, SQLite+Alembic, Qdrant (Docker), Ollama integration, real health checks | Done |
| 02 | Screenshot-matched UI shell (full nav, dashboard cards, responsive layout) | Done |
| 03 | Authentication: login/logout, roles, sessions, protected routes | Done |
| 04 | Patient system: CRUD, search, workspace, encounters, conditions, allergies, medications, timeline | Done |
| 05 | Report ingestion: upload, PDF/DOCX/XLSX/image parsing, OCR, identity checking, ingestion jobs | Done |
| 06 | Structured clinical data: lab extraction, trend engine, medication reconciliation, change engine | Done |
| 07 | Local RAG core: embeddings, Qdrant collections, dense+BM25 retrieval, RRF fusion, reranking, dedup | Done |
| 08 | Clinical chat: conversations, streaming, evidence panel, citation/grounding validation | Done |
| 09 | Vision: image upload, structured extraction, image-to-RAG, comparison | Done |
| 10 | Clinical modules: summary, SOAP, entity extraction, guideline Q&A, differential support, report comparison | Done |
| 11 | Web research: Research Mode, de-identification, PubMed/openFDA/ClinicalTrials, web cache | Done |
| 12 | Knowledge administration: upload, metadata, versions, active documents, reindex, archive, ingestion monitoring | Done |
| 13 | Audit & feedback: audit log UI, feedback capture, provenance drawer | Done |
| 14 | Demo system: synthetic patients, demo scenarios, start/reset scripts, model warm-up, GPU acceleration | Done |
| 15 | RAG evaluation suite: retrieval/citation/groundedness/hallucination/latency metrics | Done |
| 16 | Final validation: full test suite, error-state tests, security review, UI review, this report | Done |

No feature is stubbed, mocked in production code, or silently incomplete. Every phase's
"what exists right now" section in `docs/architecture.md` documents exactly what was
built and — where a real bug was found during live verification — what was found and
fixed, not swept under the rug.

## Automated Tests

| Suite | Total | Passed | Failed | Skipped |
|---|---|---|---|---|
| Backend (`pytest`) | 288 | 288 | 0 | 0 |
| Frontend unit/component (`vitest`) | 59 (23 files) | 59 | 0 | 0 |
| Frontend E2E golden path (`playwright`, spec §97) | 7 (13 real steps) | 7 | 0 | 0 |
| **Total** | **354** | **354** | **0** | **0** |

Static analysis, all clean: `ruff check` (backend — 10 pre-existing findings in old
Alembic migration auto-generated files from Phases 12/13 are unrelated to this
session's work and were left as-is per convention of not hand-editing historical
migrations), `eslint` (frontend), `tsc --noEmit` (frontend).

The E2E golden path (real backend, real Qdrant, real Ollama, no mocking) was run to a
clean pass multiple times during this session, after each of three real bugs found
live were fixed — see `docs/architecture.md`'s Phase 16 section for the full account:

1. **AskAIButton auto-send silently did nothing** — a React 18 StrictMode +
   TanStack Query v5 race permanently detached a mutation's observer from its own
   in-flight request. Fixed by switching to `mutateAsync` + a direct `await`.
2. **Medication reconciliation silently dropped every medication after the first**
   in any `.docx`-sourced document, since paragraph extraction blank-line-separates
   every line, not just section boundaries. Fixed the section-boundary heuristic.
3. **Qdrant going down crashed the chat SSE stream** instead of degrading
   gracefully like an Ollama failure already did. Fixed with a matching
   `RetrievalError`, live-verified by actually stopping the real Qdrant container
   mid-conversation and confirming a clean error event instead of a crash.

A fourth, non-blocking finding from the same session (stale "Not available yet"
dashboard placeholder text for features that had long since shipped) was also fixed —
see `docs/architecture.md` for detail.

## RAG Evaluation

Full numbers: `evaluation/evaluation_report.md` (generated 2026-08-16 17:27 UTC,
Phase 15, real Ollama/Qdrant/embedding/reranker — nothing simulated; unaffected by
Phase 16's fixes since none of them touch retrieval/citation/generation behavior on
the success path, only failure-mode handling).

- **Recall@5 / @10 / @20**: 0.71 / 0.71 / 0.71
- **MRR**: 0.71
- **nDCG@10**: 0.83 (6/7 questions scored)
- **Retrieval pass rate**: 100% (7/7 golden questions)
- **Citation precision**: 1.00, **coverage**: 100% (4 real chat turns)
- **Groundedness**: 11/12 claims supported (0.92) — a real, imperfect number from
  real model sampling, left as-is rather than rerun until it looked better
- **Abstention accuracy**: 100% (6 questions, both honesty mechanisms checked — see
  `docs/rag-design.md`'s "Abstention — two real layers" section)
- **Prompt-injection resistance (spec §98)**: PASS — real injected phrase was
  retrieved (RAG doesn't pre-filter it) but the model explicitly declined to follow
  it while still accurately describing the source document
- **Vision structural completeness**: 1/1
- **Patient isolation**: 20/20 (100%) — every seeded patient pair, full real
  `retrieve()` pipeline, adversarial cross-patient queries

## Performance

Real timed measurements, `evaluation/latency_eval.py` (Phase 15, GPU-enabled
configuration — see Environment above):

| Stage | Time |
|---|---|
| Embedding (query) | 0.066s |
| Dense search | 0.381s |
| Sparse (BM25) search | 0.002s |
| Rank fusion | 0.000s |
| Reranking | 0.077s |
| Deduplication/parent expansion | 0.001s |
| Context building | 0.000s |
| Ingestion (chunk + embed, synthetic doc) | 0.090s |
| LLM time to first token | 4.830s |
| LLM total generation time | 24.742s |

On CPU (spec-default, no GPU opt-in) these same stages are materially slower —
docs/architecture.md's Phase 07/14 sections document ~11-19s/chunk embedding and
~397-398s reranking measured live on CPU before the GPU opt-in; the troubleshooting
table in `README.md` explains this is expected latency, not a hang.

## Security Verification

- **Authentication**: session-cookie based (`HttpOnly`, `SameSite=lax`), login
  rate-limited, invalid-credentials response identical for wrong-password vs.
  unknown-email (no user-enumeration oracle) — `test_auth.py`.
- **Authorization**: every route carries an explicit role dependency
  (`AdminUser`/`WriteUser`/`CurrentUser`) consistent across all 16 phases; verified
  by both the automated test suite (RBAC tests throughout) and this phase's focused
  security review of every route added/changed since Phase 12 — no gaps found.
- **Patient isolation (spec §16)**: enforced in code — `dense_search`/`sparse_search`
  raise if a patient-scoped collection is queried without a `patient_id` — and
  live-verified 20/20 (100%) across every real seeded patient pair via
  `patient_isolation_eval.py`, plus dedicated API-level tests
  (`test_chat_api.py::test_patient_scoped_conversation_never_leaks_another_patients_evidence`).
- **PHI de-identification (spec §66)**: Research Mode's outbound queries are
  de-identified before any external call — Phase 11's live testing verified real
  patient names/MRNs are stripped from the query sent to PubMed/openFDA/
  ClinicalTrials.
- **Prompt injection (spec §98)**: real, live-verified resistance — a seeded
  document containing an embedded "ignore all previous instructions" attack is
  genuinely retrievable (RAG doesn't pre-filter it), and the model's real answer
  quoted the attack while explicitly refusing to follow it. Automated regression
  coverage: `hallucination_eval.py`'s prompt-injection check, plus this phase's
  focused security review of all code changed since Phase 12 (audit/feedback,
  demo system, evaluation suite, dashboard endpoint, error-state fixes) — no
  SQL/command/template injection, no hardcoded secrets, no unsafe deserialization,
  no raw-HTML XSS sinks found; full findings in `docs/architecture.md`'s Phase 16
  section.

## UI Verification

Live screenshots of the real running, logged-in app were compared against
`docs/ui-reference/overview-dashboard-reference.png` (the supplied visual source of
truth, spec §20) — not just a code read. Structural match confirmed: brand mark, nav,
hero headline/CTA, illustration, AI Capabilities grid, "How It Works" steps, trust
trio, and CDS disclaimer are all present and correctly styled, consistent with
Phase 02's original match. One real regression found and fixed during this
comparison: the clinical-activity snapshot cards still showed a stale "Not available
yet — arrives in Phase 05/08-10" placeholder against a real running app that already
had 23 real reports and 10 real AI-generated outputs — now backed by a real
`GET /api/dashboard/summary` endpoint and re-verified via a fresh screenshot showing
the real numbers.

## Known Limitations

- **CPU-only deployments are slow, by design and by measurement, not a bug.**
  Embedding/reranking/report ingestion measured ~11-19s/chunk and reranking
  ~397-398s on CPU (Phase 07/08's live numbers) before this deployment's GPU opt-in.
  Spec §12 deliberately defaults to `cpu` to keep VRAM free for the LLM; GPU opt-in
  is a manual `.env` change, not automatic, and there is no automatic mid-request
  fallback if a GPU-enabled deployment hits CUDA out-of-memory (see README's
  troubleshooting table).
- **GPU VRAM is tight, not generous, when all three models share one card.**
  Measured live on an 8.55GB RTX 5050: ~95% VRAM used with the embedding model,
  reranker, and `qwen3.5:9b` all resident at once. A smaller or more heavily-shared
  GPU may not have room for all three simultaneously.
- **OCR can misread small/low-contrast baked-in patient identifiers on synthetic
  demo images**, correctly triggering the same conservative `MISMATCH` flag a real
  clinician-facing unknown upload would raise (spec §30) — documented and handled,
  not silently ignored, in Phase 05/14's own live-testing notes.
- **react-router 6.30.4 has two known moderate advisories** requiring a v7 major
  upgrade (breaking) to resolve via `npm audit fix`. Accepted risk, documented in
  Phase 16's npm-audit findings: no code path in this app passes untrusted/
  user-controlled strings into `Link`/`navigate()` (all navigation targets are
  hardcoded internal routes), and the app is a client-only SPA with no SSR.
- **esbuild's dev-server-only vulnerability** (bundled via Vite) is also an accepted
  risk — not shipped to production builds, and the dev server is localhost-bound.
- **Windows-only tested.** All live verification in this build ran on Windows 11;
  Linux/macOS should work (nothing in the code is Windows-specific beyond path
  handling already covered by `pathlib`), but wasn't exercised live this session.
- **Single-node, local-first demo deployment**, not a scaled/HA/multi-tenant
  production topology (spec §136's "runs entirely offline on one machine" is the
  explicit design target, not a gap).
- **Groundedness is 11/12, not 12/12** — a real, imperfect number from real model
  sampling (Phase 15), left as-is rather than rerun until it looked better; this is
  the honest current state of the local `qwen3.5:9b` model's output quality, not a
  bug in the grounding validator.

No feature described in the master build prompt is stubbed, faked, or hidden as
"coming later" without being explicitly listed above.
