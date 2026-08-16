#!/usr/bin/env python
"""Groundedness evaluation — spec §95 "groundedness". Runs real chat turns (real
Ollama, real retrieval) for a handful of golden questions and reports the real
`app/chat/grounding_validator.py` classification of each generated claim
(supported/partially_supported/unsupported) — the same post-generation safety pass
live chat runs (spec §52/§53), scored here rather than just applied silently.

Groundedness score = fraction of claims across all evaluated answers classified
`supported`. This is a real, measured number from real model output on real evidence —
never a fabricated confidence percentage (spec §2/§54's own rule about the app itself
applies equally to how this suite reports on it).

Usage:
    python evaluation/groundedness_eval.py
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

from app.config.settings import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.conversation import ConversationScope  # noqa: E402
from app.models.patient import Patient  # noqa: E402
from _pipeline_helpers import run_real_turn  # noqa: E402

GOLDEN_FILE = Path(__file__).parent / "golden_questions.jsonl"
_GROUNDABLE_CATEGORIES = {"exact_medication_query", "numerical_lab_query", "guideline_query", "patient_history_query"}


def _load_golden() -> list[dict]:
    rows = [json.loads(line) for line in GOLDEN_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if r["category"] in _GROUNDABLE_CATEGORIES]


async def evaluate() -> list[dict]:
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
            if result.grounding is None:
                # Either nothing was cited (nothing to ground-check) or the validator
                # couldn't parse a structured response after its one retry — both are
                # honestly reported as "not scored", never assumed passing.
                results.append({**question, "not_scored": "no grounding result (nothing cited, or validator parse failure)"})
                continue

            claims = result.grounding.claims
            statuses = [c.status for c in claims]
            results.append(
                {
                    **question,
                    "claim_count": len(claims),
                    "supported": sum(1 for s in statuses if s == "supported"),
                    "partially_supported": sum(1 for s in statuses if s == "partially_supported"),
                    "unsupported": sum(1 for s in statuses if s == "unsupported"),
                    "claims": [{"claim": c.claim, "status": c.status} for c in claims],
                }
            )
    finally:
        db.close()
    return results


def print_report(results: list[dict]) -> None:
    print("\n=== Groundedness Evaluation ===\n")
    scored = [r for r in results if "claim_count" in r]
    for r in results:
        if "skipped" in r:
            print(f"  SKIP  {r['id']:<28} {r['skipped']}")
        elif "error" in r:
            print(f"  ERR   {r['id']:<28} {r['error']}")
        elif "abstained" in r:
            print(f"  ABST  {r['id']:<28} (abstained)")
        elif "not_scored" in r:
            print(f"  N/A   {r['id']:<28} {r['not_scored']}")
        else:
            print(f"  {r['id']:<28} {r['supported']}/{r['claim_count']} claims supported")
            for c in r["claims"]:
                print(f"      [{c['status']:<20}] {c['claim'][:90]}")

    if scored:
        total_claims = sum(r["claim_count"] for r in scored)
        total_supported = sum(r["supported"] for r in scored)
        print("\n--- Aggregate ---")
        if total_claims:
            print(f"Groundedness (supported / total claims): {total_supported}/{total_claims} = {total_supported / total_claims:.2f}")
        print(f"Questions scored: {len(scored)}/{len(results)}")


if __name__ == "__main__":
    print_report(asyncio.run(evaluate()))
