#!/usr/bin/env python
"""Runs every `evaluation/*.py` module and renders one human-readable Markdown report
(spec §95: "Create a human-readable HTML or Markdown evaluation report"). Markdown was
chosen over HTML — this repo's own architecture/build documentation is already
Markdown (`docs/architecture.md`), and this report is meant to be read the same way
and linked from there, not to be a standalone styled page.

This is the single command a reviewer (or Phase 16's Final Validation) runs to get the
full picture: retrieval quality, citation precision/coverage, groundedness, abstention
accuracy, prompt-injection resistance, vision extraction, patient isolation, and
latency — all real, measured numbers from the real seeded demo data and real
Ollama/embedding/reranker models, never fabricated or simulated.

This is a genuinely slow command (several real Ollama generations, several real
grounding-validation passes) — expect several minutes, not seconds. Run it before a
release, not on every commit.

Usage:
    python evaluation/report_generator.py [--output PATH]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import citation_eval  # noqa: E402
import groundedness_eval  # noqa: E402
import hallucination_eval  # noqa: E402
import latency_eval  # noqa: E402
import patient_isolation_eval  # noqa: E402
import retrieval_eval  # noqa: E402
import vision_eval  # noqa: E402

DEFAULT_OUTPUT = Path(__file__).parent / "evaluation_report.md"


def _pct(n: float) -> str:
    return f"{n:.0%}"


def _retrieval_section(results: list[dict]) -> str:
    evaluated = [r for r in results if "skipped" not in r and "error" not in r]
    lines = ["## Retrieval Evaluation", ""]
    lines.append("| Question | Category | Rank | MRR | nDCG@10 | Result |")
    lines.append("|---|---|---|---|---|---|")
    for r in results:
        if "skipped" in r:
            lines.append(f"| {r['id']} | {r['category']} | - | - | - | SKIPPED: {r['skipped']} |")
            continue
        ndcg = "n/a" if r["ndcg_at_10"] is None else f"{r['ndcg_at_10']:.2f}"
        status = "PASS" if r["passed"] else "FAIL"
        lines.append(f"| {r['id']} | {r['category']} | {r['rank_of_first_relevant']} | {r['mrr']:.2f} | {ndcg} | {status} |")
    if evaluated:
        n = len(evaluated)
        ndcg_scored = [r["ndcg_at_10"] for r in evaluated if r["ndcg_at_10"] is not None]
        lines += [
            "",
            f"- **Recall@5**: {sum(r['recall_at_5'] for r in evaluated) / n:.2f}",
            f"- **Recall@10**: {sum(r['recall_at_10'] for r in evaluated) / n:.2f}",
            f"- **Recall@20**: {sum(r['recall_at_20'] for r in evaluated) / n:.2f}",
            f"- **MRR**: {sum(r['mrr'] for r in evaluated) / n:.2f}",
        ]
        if ndcg_scored:
            lines.append(f"- **nDCG@10**: {sum(ndcg_scored) / len(ndcg_scored):.2f} ({len(ndcg_scored)}/{n} questions scored)")
        lines.append(f"- **Pass rate**: {_pct(sum(r['passed'] for r in evaluated) / n)}")
    lines.append("")
    return "\n".join(lines)


def _citation_section(outcome: dict) -> str:
    validator = outcome["validator_check"]
    real = outcome["real_checks"]
    scored = [r for r in real if "citation_precision" in r]
    lines = ["## Citation Evaluation", ""]
    status = "PASS" if validator["passed"] else "FAIL"
    lines.append(f"- **Fabricated-label stripping (spec §98)**: {status}")
    lines.append("")
    lines.append("| Question | Precision | Cited / Offered |")
    lines.append("|---|---|---|")
    for r in real:
        if "skipped" in r or "error" in r:
            lines.append(f"| {r['id']} | - | {r.get('skipped') or r.get('error')} |")
        elif "abstained" in r:
            lines.append(f"| {r['id']} | - | abstained |")
        else:
            lines.append(f"| {r['id']} | {r['citation_precision']:.2f} | {r['cited_count']}/{r['offered_evidence_count']} |")
    if scored:
        n = len(scored)
        lines += [
            "",
            f"- **Citation precision**: {sum(r['citation_precision'] for r in scored) / n:.2f}",
            f"- **Citation coverage**: {_pct(sum(r['cited_something'] for r in scored) / n)}",
        ]
    lines.append("")
    return "\n".join(lines)


def _groundedness_section(results: list[dict]) -> str:
    scored = [r for r in results if "claim_count" in r]
    lines = ["## Groundedness Evaluation", ""]
    lines.append("| Question | Supported / Total Claims |")
    lines.append("|---|---|")
    for r in results:
        if "skipped" in r or "error" in r:
            lines.append(f"| {r['id']} | {r.get('skipped') or r.get('error')} |")
        elif "abstained" in r:
            lines.append(f"| {r['id']} | abstained |")
        elif "not_scored" in r:
            lines.append(f"| {r['id']} | {r['not_scored']} |")
        else:
            lines.append(f"| {r['id']} | {r['supported']}/{r['claim_count']} |")
    if scored:
        total_claims = sum(r["claim_count"] for r in scored)
        total_supported = sum(r["supported"] for r in scored)
        if total_claims:
            lines.append("")
            lines.append(f"- **Groundedness** (supported / total claims): {total_supported}/{total_claims} = {total_supported / total_claims:.2f}")
    lines.append("")
    return "\n".join(lines)


def _hallucination_section(outcome: dict) -> str:
    abstention = outcome["abstention"]
    injection = outcome["injection"]
    scored = [r for r in abstention if "correct" in r]
    lines = ["## Hallucination / Abstention Evaluation", ""]
    lines.append(
        "_Two real honesty mechanisms are checked: the orchestrator's hard pre-generation "
        "abstain gate, and the system prompt's in-generation instruction to honestly decline "
        "when retrieved/available context doesn't answer the question. Either counts as correct — "
        "see `hallucination_eval.py`'s docstring for the live finding that made checking both necessary._"
    )
    lines.append("")
    lines.append("| Question | Should Decline | Hard Gate | In-Generation | Result |")
    lines.append("|---|---|---|---|---|")
    for r in abstention:
        if "skipped" in r:
            lines.append(f"| {r['id']} | - | - | - | SKIPPED: {r['skipped']} |")
        else:
            status = "PASS" if r["correct"] else "FAIL"
            lines.append(
                f"| {r['id']} | {r['should_decline']} | {r['hard_gate_abstained']} | "
                f"{r['honestly_declined_in_generation']} | {status} |"
            )
    if scored:
        n = len(scored)
        lines.append("")
        lines.append(f"- **Abstention accuracy**: {_pct(sum(r['correct'] for r in scored) / n)} ({n} questions)")

    lines.append("")
    lines.append("### Prompt Injection Resistance (spec §98)")
    lines.append("")
    if "skipped" in injection or "error" in injection:
        lines.append(f"SKIPPED/ERROR: {injection.get('skipped') or injection.get('error')}")
    else:
        status = "PASS" if injection["passed"] else "FAIL"
        lines.append(f"- **Result**: {status}")
        lines.append(f"- Injected phrase retrieved (RAG doesn't pre-filter it): {injection['injected_phrase_was_retrieved']}")
        lines.append(f"- Model complied with the injected instruction: {injection['model_complied_with_injection']}")
        lines.append(f"- Real model answer: \"{injection['answer_text'][:300]}\"")
    lines.append("")
    return "\n".join(lines)


def _vision_section(results: list[dict]) -> str:
    scored = [r for r in results if "passed" in r]
    lines = ["## Vision Extraction Evaluation", ""]
    lines.append("_Structural completeness only — no hand-labeled ground truth exists for synthetic images (see `vision_eval.py`'s docstring)._")
    lines.append("")
    lines.append("| Question | Image Type | Observations | Result |")
    lines.append("|---|---|---|---|")
    for r in results:
        if "skipped" in r:
            lines.append(f"| {r['id']} | - | - | SKIPPED: {r['skipped']} |")
        else:
            status = "PASS" if r["passed"] else "FAIL"
            obs = len(r["payload"].get("observations", []))
            lines.append(f"| {r['id']} | {r['payload'].get('image_type')!r} | {obs} | {status} |")
    if scored:
        n = len(scored)
        lines.append("")
        lines.append(f"- **Structural completeness**: {sum(r['passed'] for r in scored)}/{n}")
    lines.append("")
    return "\n".join(lines)


def _isolation_section(results: list[dict]) -> str:
    lines = ["## Patient Isolation Evaluation", ""]
    lines.append(f"Every seeded patient pair ({len(results)} combinations), full real `retrieve()` pipeline, real cross-patient adversarial queries.")
    lines.append("")
    if results:
        n = len(results)
        passed = sum(r["passed"] for r in results)
        lines.append(f"- **Isolation pass rate**: {passed}/{n} ({_pct(passed / n)})")
        failures = [r for r in results if not r["passed"]]
        if failures:
            lines.append("")
            lines.append("**CRITICAL — leaks detected:**")
            for r in failures:
                lines.append(f"- {r['origin_patient_mrn']} -> {r['target_patient_mrn']}: {r['leaked_chunks']} leaked chunk(s)")
    lines.append("")
    return "\n".join(lines)


def _performance_section(timings: dict) -> str:
    lines = ["## Performance", ""]
    lines.append("| Stage | Time |")
    lines.append("|---|---|")
    label_map = {
        "embedding_query_s": "Embedding (query)",
        "dense_search_s": "Dense search",
        "sparse_search_s": "Sparse (BM25) search",
        "fusion_s": "Rank fusion",
        "reranking_s": "Reranking",
        "deduplication_s": "Deduplication/parent expansion",
        "context_building_s": "Context building",
        "synthetic_ingestion_s": "Ingestion (chunk + embed, synthetic doc)",
        "llm_time_to_first_token_s": "LLM time to first token",
        "llm_total_generation_s": "LLM total generation time",
    }
    for key, label in label_map.items():
        value = timings.get(key)
        lines.append(f"| {label} | {'n/a' if value is None else f'{value:.3f}s'} |")
    if "llm_tokens_streamed" in timings:
        lines.append(f"| LLM tokens streamed | {timings['llm_tokens_streamed']} |")
    if "llm_error" in timings:
        lines.append(f"| LLM error | {timings['llm_error']} |")
    lines.append("")
    return "\n".join(lines)


async def generate(output_path: Path) -> None:
    print("Running retrieval_eval...", flush=True)
    retrieval_results = retrieval_eval.evaluate()

    print("Running citation_eval (real Ollama calls)...", flush=True)
    citation_outcome = await citation_eval.evaluate()

    print("Running groundedness_eval (real Ollama calls)...", flush=True)
    groundedness_results = await groundedness_eval.evaluate()

    print("Running hallucination_eval (real Ollama calls)...", flush=True)
    hallucination_outcome = await hallucination_eval.evaluate()

    print("Running vision_eval...", flush=True)
    vision_results = vision_eval.evaluate()

    print("Running patient_isolation_eval...", flush=True)
    isolation_results = patient_isolation_eval.evaluate()

    print("Running latency_eval (real Ollama call)...", flush=True)
    timings = await latency_eval.evaluate()

    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    report = "\n".join(
        [
            "# RAG Evaluation Report",
            "",
            f"Generated {generated_at} — spec §95 RAG Evaluation Suite. Every number below is a real,",
            "measured result against the real seeded demo dataset and real Ollama/embedding/reranker",
            "models (see `.env` for which device each ran on) — nothing here is simulated or fabricated.",
            "",
            _retrieval_section(retrieval_results),
            _citation_section(citation_outcome),
            _groundedness_section(groundedness_results),
            _hallucination_section(hallucination_outcome),
            _vision_section(vision_results),
            _isolation_section(isolation_results),
            _performance_section(timings),
        ]
    )
    output_path.write_text(report, encoding="utf-8")
    print(f"\nReport written to {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output Markdown file path")
    args = parser.parse_args()
    asyncio.run(generate(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
