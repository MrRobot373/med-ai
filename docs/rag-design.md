# RAG Design

How this deployment's retrieval-augmented generation pipeline actually works —
chunking, embedding, sparse retrieval, fusion, reranking, citations, and grounding —
written against the real implementation in `backend/app/rag/`, `backend/app/chat/`,
and `backend/app/ingestion/chunking.py`, not an idealized description. See
`docs/architecture.md`'s Phase 07/08 sections for the live-measured numbers and real
bugs found while building this; this document explains the *mechanism*, that one
tracks the *build history*.

## Pipeline overview

```text
Document ingested (report upload, or scripts/ingest_knowledge.py)
        │
        ▼
  Chunking (ingestion/chunking.py)
        │
        ▼
  Embedding (rag/embeddings.py) ──────────► Qdrant (vector) + SQLite `chunks` (text)
                                                              │
                                                              │  (indexed once, read many times)
                                                              ▼
Clinical AI question
        │
        ├──────────────► Dense search (rag/dense_retriever.py)  ─┐
        │                                                         │
        └──────────────► Sparse/BM25 search (rag/sparse_retriever.py) ─┤
                                                                   │
                                                                   ▼
                                            Reciprocal Rank Fusion (rag/fusion.py)
                                                                   │
                                                                   ▼
                                            Reranking (rag/reranker.py, cross-encoder)
                                                                   │
                                                                   ▼
                                  Deduplication + parent expansion (rag/deduplicator.py)
                                                                   │
                                                                   ▼
                                  Context construction (chat/context_builder.py) — [P#]/[L#]/[V#]/[W#] labels
                                                                   │
                                                                   ▼
                                          Ollama generation (real streaming, "think": false)
                                                                   │
                                                                   ▼
                            Citation validation (chat/citation_validator.py) — strip fabricated labels
                                                                   │
                                                                   ▼
                            Grounding validation (chat/grounding_validator.py) — per-claim support check
                                                                   │
                                                                   ▼
                                        Evidence quality label (chat/evidence_quality.py)
```

Every stage above is a real, separate, independently-testable module — not one large
function — matching spec §134's "small focused modules" requirement. `rag/pipeline.py`
composes dense → sparse → fusion → rerank → dedup into one `retrieve()` call;
everything above that (query classification, structured-fact assembly, citation/
grounding validation) is `chat/orchestrator.py`'s job, which has no knowledge of the
LLM's internals and calls into `rag/pipeline.py` the same way for every collection.

## Chunking

`ingestion/chunking.py`'s `chunk_pages()` is section-aware, not a naive fixed-size
sliding window:

- A blank-line-separated block (paragraphs, or a `[Table]` block our own PDF/DOCX/XLSX
  extractors already emit) is the atomic unit — never split mid-block.
- A short, punctuation-free line is tracked as the current section heading, attached
  to every chunk that follows it, so a citation can say *which part* of a document it
  came from (e.g. "Assessment" vs. "Plan"), not just the page number.
- Target size ~550 tokens with ~80-token overlap (`RAG_CHUNK_TARGET_TOKENS` /
  `RAG_CHUNK_OVERLAP_TOKENS`), both configurable — spec §134 "configuration for
  thresholds," not a magic constant buried in code.
- A `[Table]` block is never split across chunks even if that pushes one chunk over
  the target size — a partial table row is worse than one oversized chunk.
- Token counts are an approximation (~1.3× word count), not a real tokenizer call —
  adequate for *sizing* chunks; it doesn't need to be exact.

## Embedding

`rag/embeddings.py` wraps `Qwen/Qwen3-Embedding-0.6B` via `sentence-transformers`, a
lazy-loaded process-wide singleton (loads once, on first real use — see
`/api/health` reporting `not_loaded` vs. `ready`, never a hardcoded "Ready").
Qwen3-Embedding is asymmetric: `embed_query()` and `embed_documents()` use different
prompt templates internally (the model was trained that way), so a query is never
embedded through the document path or vice versa.

Two real, measured CPU-performance fixes live here (`docs/architecture.md`'s Phase 07
section has the full story): `max_seq_length` capped to a sane value instead of the
model's 32K default (attention cost scales with the *configured* max, not the actual
input length — an uncapped default made a single ~400-word chunk take 141–179 seconds),
and `attn_implementation="sdpa"` forced instead of PyTorch's default eager attention
(~2.2× faster on CPU for this decoder-based architecture). `EMBEDDING_DEVICE=cuda` (see
README.md's "GPU acceleration" section) skips both CPU-specific costs entirely — real
measured throughput went from ~11–19s/chunk (CPU) to ~0.01s/chunk (GPU) in this
deployment's testing.

## Sparse (BM25) retrieval

`rag/sparse_retriever.py` — spec §43 Stage 6's point that dense embeddings can blur
past exact drug names, ICD-style codes, and precise phrases a lexical match catches
directly. Computed **in-process** over the SQLite chunk corpus at query time via
`rank-bm25`, not stored as a persistent Qdrant sparse index — simpler infrastructure
for this deployment's scale (spec §135 "avoid unnecessary infrastructure"), and it
never goes stale against the corpus the way a separately-maintained sparse index could.

## Patient isolation (mandatory, not optional)

Both `dense_retriever.dense_search()` and `sparse_retriever.sparse_search()` **raise**
if a patient-scoped collection (`patient_documents`, `patient_vision`) is queried
without a `patient_id` — spec §16's guarantee enforced at the one place every retrieval
call passes through, in code, not by convention. `evaluation/patient_isolation_eval.py`
verifies this live against every seeded patient pair through the *full* pipeline
(dense+sparse+fusion+rerank+dedup), attacked with each patient's own real clinical
content scoped to every other patient — the worst case for a leak.

## Fusion

`rag/fusion.py` implements Reciprocal Rank Fusion (spec §44's named default):
`score(chunk) = Σ 1/(k + rank)` summed across every ranked list the chunk appears in
(`k=60`, the constant from the original RRF paper — configurable via
`RAG_RRF_K`). A chunk ranked #1 by dense search but entirely absent from the sparse
list still surfaces (rewarded for the list it *did* rank well in) rather than being
zeroed out for the list it didn't appear in at all. Kept as a standalone, swappable
module — spec §44 explicitly asks for fusion strategy to stay configurable, not hard-wired
into the retrieval pipeline.

## Reranking

`rag/reranker.py` wraps `Qwen/Qwen3-Reranker-0.6B` as a `sentence-transformers`
`CrossEncoder` — same lazy-singleton, same CPU-perf fixes (capped sequence length,
`sdpa` attention) as the embedding model, same GPU opt-in. Takes the fused candidate
set (capped by `RAG_FUSION_TOP_K`, spec §46's "~15-20 candidates before reranking" —
never hundreds of chunks, spec §6) and re-scores each with a real cross-encoder pass
(joint query+passage attention, more accurate than the bi-encoder dot-product dense
search uses, at real extra compute cost). Raw logits, not a calibrated probability —
positive means relevant, negative means not (confirmed empirically during Phase 07 live
testing: ~0.06 for a genuinely relevant pair, ~-5.8 for an irrelevant one) — which is
exactly the signal `chat/evidence_quality.py` uses for its deterministic quality label,
never a fabricated confidence percentage.

## Deduplication and parent expansion

`rag/deduplicator.py` — spec §47. Adjacent same-section chunks from one source get
merged into a single passage (full chunk-level provenance preserved via `chunk_ids`,
so a merge never loses which exact chunks a citation traces back to), and
`max_per_source` caps how many merged passages from one document can dominate a
result just because several overlapping chunks all matched.

## Citations

`chat/context_builder.py` labels every offered passage once — `P#` for patient
documents, `L#` for local knowledge, `V#` for vision-derived evidence, `W#` for
external web evidence (Research Mode only) — from the same ordered list the model is
shown, before generation. The model never invents its own numbering; it can only ever
cite a label it was actually offered. `chat/citation_validator.py` then strips any
`[P9]`-style marker in the model's real output that doesn't match a real offered
label — spec §52's "never trust the LLM's own citation numbering," verified live (spec
§98's explicit security test) in `evaluation/citation_eval.py`.

## Grounding validation

`chat/grounding_validator.py` — a second, structured LLM pass (spec §52/§53) that
classifies each major claim in the model's own generated answer as
`supported`/`partially_supported`/`unsupported` against its cited passages. One
controlled retry; returns `None` (never a fabricated "pass") if both attempts fail to
parse. `evaluation/groundedness_eval.py` scores this live against real golden
questions — see `evaluation/evaluation_report.md` (generated by
`evaluation/report_generator.py`) for the current real numbers.

## Abstention — two real layers, not one

A question can go unanswered two different ways, both real and both spec
§2-compliant, discovered explicitly while building `evaluation/hallucination_eval.py`
(see its docstring for the full live finding):

1. **Hard pre-generation gate** (`chat/orchestrator.py`'s `prepare_turn()`): no LLM
   call happens at all when there is truly nothing to answer from — no retrieval hit
   **and** no structured patient/encounter/report facts.
2. **In-generation honesty** (the system prompt's own instruction): for a
   patient-scoped question, structured facts (demographics, conditions, medications)
   almost always exist for a real patient, so the hard gate rarely fires — but those
   facts might have nothing to do with the specific question asked (e.g. "what was the
   brain MRI result?" against an ophthalmology chart with no MRI in it at all). The
   system prompt instructs the model to use `ABSTENTION_TEXT` verbatim in this case,
   confirmed live: the model correctly declined and cited that nothing in the record
   supported an answer, rather than guessing.

Both mechanisms are checked by `evaluation/hallucination_eval.py`'s abstention-accuracy
metric — checking only the hard gate would have misreported a correctly-honest answer
as a failure.
