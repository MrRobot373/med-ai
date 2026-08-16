#!/usr/bin/env python
"""Citation evaluation — spec §95 citation precision/coverage, spec §96's
`citation_validation` golden category, and spec §98's "invalid citation" security test
("Generator must not be allowed to show citation IDs that do not exist").

Two parts:
1. A pure-logic check (no LLM, instant) that `app/chat/citation_validator.py` actually
   strips a fabricated citation label the model didn't earn while keeping a real one
   that was genuinely offered — the exact spec §98 guarantee, checked here as a scored
   eval in addition to `backend/tests/test_citation_validator.py`'s pytest coverage
   (belt and suspenders, same pattern `retrieval_eval.py` already uses for isolation).
2. Real end-to-end citation precision/coverage: a handful of golden questions that
   have real retrievable evidence are run through the actual live pipeline (real
   Ollama), and every citation label in the model's real final answer is checked
   against the real offered evidence.
   - precision = (labels cited that were genuinely offered) / (labels cited) — expected
     to be 1.0 by construction, since `validate_citations()` already strips anything
     else; scoring it end-to-end (not just unit-testing the validator in isolation)
     verifies the full real pipeline honors that guarantee, not just the function.
   - coverage = fraction of answered (non-abstained) questions where the model cited
     at least one real source, given real evidence was actually available to cite.

Usage:
    python evaluation/citation_eval.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.chat.citation_validator import validate_citations  # noqa: E402
from app.chat.context_builder import LabeledEvidence  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.conversation import ConversationScope  # noqa: E402
from app.models.patient import Patient  # noqa: E402
from app.rag.deduplicator import RetrievedPassage  # noqa: E402
from _pipeline_helpers import run_real_turn  # noqa: E402

GOLDEN_FILE = Path(__file__).parent / "golden_questions.jsonl"

# Golden categories with real retrievable evidence — a real basis to score citation
# precision/coverage against. Other categories (no_evidence_query, isolation attacks,
# ...) don't belong here; they're evaluated by their own dedicated modules.
_COVERAGE_CATEGORIES = {"exact_medication_query", "numerical_lab_query", "guideline_query", "patient_history_query"}


def _load_golden() -> list[dict]:
    rows = [json.loads(line) for line in GOLDEN_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if r["category"] in _COVERAGE_CATEGORIES]


def eval_validator_strips_fabricated_labels() -> dict:
    passage = RetrievedPassage(
        text="Latanoprost 0.005% nightly, both eyes.",
        score=1.0,
        source_title="Klein consult (evaluation fixture)",
        source_id="report-eval",
        collection="patient_documents",
        page=1,
        section=None,
        chunk_ids=["chunk-eval"],
    )
    labeled = [LabeledEvidence(label="P1", passage=passage)]
    raw_answer = "The patient is on Latanoprost [P1], and also had surgery in 2020 [P9]."
    cleaned, used = validate_citations(raw_answer, labeled)
    passed = "[P9]" not in cleaned and "[P1]" in cleaned and used == ["P1"]
    return {
        "id": "citation_validation",
        "category": "citation_validation",
        "passed": passed,
        "cleaned_answer": cleaned,
        "used_labels": used,
    }


async def eval_real_citation_precision_and_coverage() -> list[dict]:
    settings = get_settings()
    db = SessionLocal()
    results: list[dict] = []
    try:
        for question in _load_golden():
            patient_id = None
            if question.get("patient_mrn"):
                patient = db.query(Patient).filter(Patient.mrn == question["patient_mrn"]).first()
                if patient is None:
                    results.append({**question, "skipped": "patient not found — run scripts/seed_demo_patients.py"})
                    continue
                patient_id = patient.id
            scope = ConversationScope.CURRENT_PATIENT if patient_id else ConversationScope.LOCAL_KNOWLEDGE_ONLY

            prepared, answer_text, result = await run_real_turn(db, settings, question["query"], scope, patient_id)
            if prepared.abstain:
                results.append({**question, "abstained": True})
                continue
            if answer_text and answer_text.startswith("GENERATION_ERROR"):
                results.append({**question, "error": answer_text})
                continue

            offered_labels = {item.label for item in prepared.labeled_evidence}
            cited_labels = {c.label for c in result.citations}
            precision = 1.0 if not cited_labels else len(cited_labels & offered_labels) / len(cited_labels)

            results.append(
                {
                    **question,
                    "offered_evidence_count": len(offered_labels),
                    "cited_count": len(cited_labels),
                    "citation_precision": precision,
                    "cited_something": int(bool(cited_labels)),
                    "evidence_quality": result.evidence_quality.value,
                }
            )
    finally:
        db.close()
    return results


def print_report(validator_result: dict, real_results: list[dict]) -> None:
    print("\n=== Citation Evaluation ===\n")
    status = "PASS" if validator_result["passed"] else "FAIL"
    print(f"  {status}  citation_validation (fabricated-label stripping) - used_labels={validator_result['used_labels']}")

    print(f"\n  Real end-to-end citation checks ({len(real_results)} questions):")
    scored = []
    for r in real_results:
        if "skipped" in r:
            print(f"    SKIP  {r['id']:<28} {r['skipped']}")
        elif "error" in r:
            print(f"    ERR   {r['id']:<28} {r['error']}")
        elif "abstained" in r:
            print(f"    ABST  {r['id']:<28} (abstained - no evidence to cite)")
        else:
            scored.append(r)
            print(
                f"    {r['id']:<28} precision={r['citation_precision']:.2f} "
                f"cited={r['cited_count']}/{r['offered_evidence_count']} offered"
            )

    if scored:
        n = len(scored)
        print("\n--- Aggregate ---")
        print(f"Citation precision: {sum(r['citation_precision'] for r in scored) / n:.2f}")
        print(f"Citation coverage:  {sum(r['cited_something'] for r in scored) / n:.2f}  (answers citing >=1 real source)")


async def evaluate() -> dict:
    validator_result = eval_validator_strips_fabricated_labels()
    real_results = await eval_real_citation_precision_and_coverage()
    return {"validator_check": validator_result, "real_checks": real_results}


if __name__ == "__main__":
    outcome = asyncio.run(evaluate())
    print_report(outcome["validator_check"], outcome["real_checks"])
