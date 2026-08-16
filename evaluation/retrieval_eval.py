#!/usr/bin/env python
"""Golden retrieval evaluation — spec §95/§96, scoped to Phase 07's retrieval-only
slice. The full `evaluation/` suite (citation/groundedness/hallucination/vision
evaluation) lands in Phase 15, once the phases those depend on (08 chat, 09 vision,
11 web research) exist to produce anything to evaluate.

Computes Recall@5/10/20 and MRR at the fusion stage (dense+sparse+RRF, before
reranking — reranking's final top-8 output is too small a candidate pool to compute
Recall@20 meaningfully) against `golden_questions.jsonl`, using keyword containment as
a practical relevance proxy — this is a small demo corpus with real but not
exhaustively hand-labeled documents, not a fixed benchmark dataset.

Two categories get a pass/fail check instead of (or in addition to) recall:
- `no_evidence_query`: correct behavior is finding NOTHING relevant at all.
- `patient_isolation_attack`: correct behavior is that a chunk belonging to the
  `forbidden_patient_mrn` never appears in the results, full stop — this is the
  spec §14 "patient A's chunks can never appear in patient B's context" guarantee,
  checked here as a scored eval in addition to the hard pytest assertion in
  `backend/tests/test_rag_pipeline.py` (belt and suspenders: a unit test that must
  never regress, plus a visible report a human can read).

Usage:
    python evaluation/retrieval_eval.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.config.settings import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.chunk import Chunk, ChunkCollection  # noqa: E402
from app.models.patient import Patient  # noqa: E402
from app.rag import dense_retriever, sparse_retriever  # noqa: E402
from app.rag.fusion import reciprocal_rank_fusion  # noqa: E402

GOLDEN_FILE = Path(__file__).parent / "golden_questions.jsonl"

# This file only handles the golden categories that are actual retrieval/ranking
# questions (a query, a collection, an expected-relevant-chunk check). The other
# spec §96 categories added in Phase 15 (report_comparison, prompt_injection_document,
# citation_validation, vision_report_extraction, web_deidentification) are structurally
# different — no ranked chunk list to score — and are evaluated by their own dedicated
# modules instead (report_generator.py runs all of them together).
_RETRIEVAL_CATEGORIES = {
    "exact_medication_query",
    "semantic_symptom_query",
    "numerical_lab_query",
    "patient_history_query",
    "guideline_query",
    "no_evidence_query",
    "patient_isolation_attack",
}


def _load_golden() -> list[dict]:
    rows = [json.loads(line) for line in GOLDEN_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if r["category"] in _RETRIEVAL_CATEGORIES]


def _resolve_patient_id(db, mrn: str | None) -> str | None:
    if not mrn:
        return None
    patient = db.query(Patient).filter(Patient.mrn == mrn).first()
    return patient.id if patient else None


def _chunk_texts(db, chunk_ids: list[str]) -> dict[str, str]:
    if not chunk_ids:
        return {}
    rows = db.query(Chunk.id, Chunk.text).filter(Chunk.id.in_(chunk_ids)).all()
    return {row.id: row.text for row in rows}


def _is_relevant(text: str, expected_keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in expected_keywords)


def _check_isolation_leak(db, chunk_ids: list[str], forbidden_patient_id: str | None) -> bool:
    if not forbidden_patient_id or not chunk_ids:
        return False
    leaked = db.query(Chunk).filter(Chunk.id.in_(chunk_ids), Chunk.patient_id == forbidden_patient_id).count()
    return leaked > 0


def _ndcg_at_k(chunk_ids: list[str], texts: dict[str, str], expected_keywords: list[str], k: int = 10) -> float | None:
    """Standard nDCG@k with binary relevance (keyword containment, same proxy as the
    rest of this file). IDCG is computed from the relevant items actually present
    among the retrieved candidates (the total count of relevant chunks in the whole
    corpus isn't known) — the conventional approach when only a retrieved-candidate
    judgment is available, not a fully hand-labeled corpus. Returns `None` for a
    question with no notion of "relevant content" at all (no_evidence_query has
    nothing to rank well; patient_isolation_attack's success criterion is absence, not
    ranking) — reported as "n/a" rather than a misleading numeric score."""
    if not expected_keywords:
        return None
    relevances = [int(_is_relevant(texts.get(cid, ""), expected_keywords)) for cid in chunk_ids[:k]]
    if not relevances:
        return 0.0
    dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))
    ideal = sorted(relevances, reverse=True)
    idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal))
    return (dcg / idcg) if idcg > 0 else 0.0


def evaluate() -> list[dict]:
    settings = get_settings()
    db = SessionLocal()
    results: list[dict] = []
    try:
        for question in _load_golden():
            collection = ChunkCollection(question["collection"])
            patient_id = _resolve_patient_id(db, question.get("patient_mrn"))

            if question.get("patient_mrn") and patient_id is None:
                results.append({**question, "skipped": "patient not found — run scripts/seed_demo_patients.py"})
                continue

            try:
                dense_hits = dense_retriever.dense_search(
                    question["query"], collection, settings, patient_id=patient_id, top_k=20
                )
                sparse_hits = sparse_retriever.sparse_search(
                    db, question["query"], collection, patient_id=patient_id, top_k=20
                )
            except ValueError as exc:
                results.append({**question, "error": str(exc)})
                continue

            fused = reciprocal_rank_fusion(dense_hits, sparse_hits, k=settings.rag_rrf_k)
            chunk_ids = [hit.chunk_id for hit in fused]
            texts = _chunk_texts(db, chunk_ids)

            expected = question.get("expected_keywords", [])
            rank_of_first_relevant = next(
                (i for i, cid in enumerate(chunk_ids, start=1) if _is_relevant(texts.get(cid, ""), expected)), None
            )

            if question["category"] == "no_evidence_query":
                passed = rank_of_first_relevant is None
            elif question["category"] == "patient_isolation_attack":
                forbidden_id = _resolve_patient_id(db, question.get("forbidden_patient_mrn"))
                passed = not _check_isolation_leak(db, chunk_ids, forbidden_id)
            else:
                passed = rank_of_first_relevant is not None

            results.append(
                {
                    **question,
                    "rank_of_first_relevant": rank_of_first_relevant,
                    "recall_at_5": int(rank_of_first_relevant is not None and rank_of_first_relevant <= 5),
                    "recall_at_10": int(rank_of_first_relevant is not None and rank_of_first_relevant <= 10),
                    "recall_at_20": int(rank_of_first_relevant is not None and rank_of_first_relevant <= 20),
                    "mrr": (1.0 / rank_of_first_relevant) if rank_of_first_relevant else 0.0,
                    "ndcg_at_10": _ndcg_at_k(chunk_ids, texts, expected),
                    "passed": passed,
                }
            )
    finally:
        db.close()
    return results


def print_report(results: list[dict]) -> None:
    evaluated = [r for r in results if "skipped" not in r and "error" not in r]
    print(f"\n=== Golden Retrieval Evaluation ({len(evaluated)} evaluated / {len(results)} total) ===\n")
    for r in results:
        if "skipped" in r:
            print(f"  SKIP  {r['id']:<32} {r['skipped']}")
        elif "error" in r:
            print(f"  ERR   {r['id']:<32} {r['error']}")
        else:
            status = "PASS" if r["passed"] else "FAIL"
            ndcg = "n/a" if r["ndcg_at_10"] is None else f"{r['ndcg_at_10']:.2f}"
            print(f"  {status}  {r['id']:<32} rank={r['rank_of_first_relevant']} mrr={r['mrr']:.2f} ndcg@10={ndcg}")

    if evaluated:
        n = len(evaluated)
        ndcg_scored = [r["ndcg_at_10"] for r in evaluated if r["ndcg_at_10"] is not None]
        print("\n--- Aggregate (evaluated questions only) ---")
        print(f"Recall@5:  {sum(r['recall_at_5'] for r in evaluated) / n:.2f}")
        print(f"Recall@10: {sum(r['recall_at_10'] for r in evaluated) / n:.2f}")
        print(f"Recall@20: {sum(r['recall_at_20'] for r in evaluated) / n:.2f}")
        print(f"MRR:       {sum(r['mrr'] for r in evaluated) / n:.2f}")
        if ndcg_scored:
            print(f"nDCG@10:   {sum(ndcg_scored) / len(ndcg_scored):.2f}  ({len(ndcg_scored)}/{n} questions scored)")
        print(f"Pass rate: {sum(r['passed'] for r in evaluated) / n:.2f}")


if __name__ == "__main__":
    print_report(evaluate())
