#!/usr/bin/env python
"""Dedicated patient isolation evaluation — spec §14/§16's mandatory guarantee: a
patient-scoped retrieval must never return another patient's content, regardless of
how relevant the query text is to it. `retrieval_eval.py`'s `patient_isolation_attack`
golden question already checks one deliberately-adversarial pair at the fusion stage;
this module is the dedicated, comprehensive version spec §95 asks for — every seeded
patient pair, through the FULL real `retrieve()` pipeline (dense+sparse+fusion+
rerank+dedup, not just fusion), each attacked with a query built from the *other*
patient's own real clinical content: the worst case for a leak (maximally relevant
text, wrong patient scope), generalized automatically across every seeded patient
rather than one hand-picked pair.

Usage:
    python evaluation/patient_isolation_eval.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.config.settings import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.chunk import Chunk, ChunkCollection  # noqa: E402
from app.models.condition import Condition  # noqa: E402
from app.models.patient import Patient  # noqa: E402
from app.rag.pipeline import retrieve  # noqa: E402


def _signature_query(db, patient_id: str) -> str | None:
    """A query built from a patient's own real, distinctive clinical content — the
    same "attack built from real data" approach `retrieval_eval.py`'s golden question
    uses, generalized here to every seeded patient automatically rather than one
    hand-picked pair."""
    conditions = db.query(Condition).filter(Condition.patient_id == patient_id).all()
    if not conditions:
        return None
    return " ".join(c.display for c in conditions)


def evaluate() -> list[dict]:
    settings = get_settings()
    db = SessionLocal()
    results: list[dict] = []
    try:
        patients = db.query(Patient).filter(Patient.synthetic.is_(True)).order_by(Patient.mrn).all()
        for origin in patients:
            query = _signature_query(db, origin.id)
            if not query:
                continue
            for target in patients:
                if target.id == origin.id:
                    continue
                passages = retrieve(
                    db, query, settings, collection=ChunkCollection.PATIENT_DOCUMENTS, patient_id=target.id
                )
                leaked_chunk_ids: set[str] = set()
                for passage in passages:
                    for chunk_id in passage.chunk_ids:
                        chunk = db.get(Chunk, chunk_id)
                        if chunk is not None and chunk.patient_id == origin.id:
                            leaked_chunk_ids.add(chunk_id)
                results.append(
                    {
                        "origin_patient_mrn": origin.mrn,
                        "target_patient_mrn": target.mrn,
                        "query": query[:80],
                        "leaked_chunks": len(leaked_chunk_ids),
                        "passed": len(leaked_chunk_ids) == 0,
                    }
                )
    finally:
        db.close()
    return results


def print_report(results: list[dict]) -> None:
    print("\n=== Patient Isolation Evaluation (full retrieve() pipeline, all seeded patient pairs) ===\n")
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  {status}  {r['origin_patient_mrn']} content -> {r['target_patient_mrn']} scope   leaked={r['leaked_chunks']}")
    if results:
        n = len(results)
        passed = sum(r["passed"] for r in results)
        print(f"\nIsolation pass rate: {passed}/{n} ({passed / n:.2%})")
        if passed < n:
            print("!!! CRITICAL: patient isolation violation detected - this must be fixed before any release.")


if __name__ == "__main__":
    print_report(evaluate())
