"""Web Research orchestration (spec §64-72). `api/research.py` calls into this;
`app/research/*` has the provider/ranking/de-identification logic and knows nothing
about SQLAlchemy or HTTP. Persists through the same `ClinicalModuleRun` table as
Phase 10's modules (`ClinicalModuleType.RESEARCH`) — a real dedicated workflow with
its own schema, not a chat variant, exactly like Phase 10's precedent.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.chat.citation_validator import validate_citations
from app.chat.context_builder import LabeledEvidence, build_evidence_block, label_evidence
from app.chat.evidence_quality import score_evidence_quality
from app.chat.patient_context import build_patient_facts
from app.config.settings import Settings
from app.llm.generation import GenerationError
from app.logging import get_logger
from app.models.chunk import ChunkCollection
from app.models.clinical_module_run import ClinicalModuleRun, ClinicalModuleType
from app.models.patient import Patient
from app.models.web_cache import WebCacheEntry, WebSource
from app.rag.deduplicator import RetrievedPassage
from app.rag.pipeline import retrieve
from app.research.deidentify import deidentify_query
from app.research.paper_assistant import generate_research_synthesis
from app.research.providers import clinicaltrials, fda, pubmed, searxng
from app.research.providers.base import WebResult
from app.research.ranking import rank_results
from app.services.clinical_modules import record_run

logger = get_logger(__name__)

_NOT_PARSED_ERROR = "Model did not return valid structured output after retry"

_PROVIDERS = {
    WebSource.PUBMED: pubmed.search,
    WebSource.FDA: fda.search,
    WebSource.CLINICALTRIALS: clinicaltrials.search,
    WebSource.SEARXNG: searxng.search,
}


def available_sources(settings: Settings) -> list[WebSource]:
    """PubMed/FDA/ClinicalTrials.gov are always-available public APIs (no key, no
    optional infra); SearXNG only counts as "available" once its optional Docker
    profile is actually reachable — checked live, never assumed (spec §103)."""
    sources = [WebSource.PUBMED, WebSource.FDA, WebSource.CLINICALTRIALS]
    if searxng_reachable(settings):
        sources.append(WebSource.SEARXNG)
    return sources


def searxng_reachable(settings: Settings) -> bool:
    try:
        resp = httpx.get(f"{settings.searxng_url.rstrip('/')}/search", params={"q": "test", "format": "json"}, timeout=3.0)
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


def _get_fresh_cache(db: DbSession, settings: Settings, query: str, source: WebSource) -> list[WebCacheEntry]:
    cutoff = datetime.now(UTC) - timedelta(hours=settings.research_cache_freshness_hours)
    stmt = select(WebCacheEntry).where(
        WebCacheEntry.query == query, WebCacheEntry.source == source, WebCacheEntry.retrieved_at >= cutoff
    )
    return list(db.scalars(stmt))


def _cache_result(db: DbSession, query: str, result: WebResult) -> WebCacheEntry:
    checksum = hashlib.sha256(result.text.encode("utf-8")).hexdigest()
    existing = db.scalar(
        select(WebCacheEntry).where(WebCacheEntry.checksum == checksum, WebCacheEntry.query == query)
    )
    if existing:
        return existing
    entry = WebCacheEntry(
        url=result.url,
        title=result.title,
        source=result.source,
        authority_tier=result.authority_tier,
        text=result.text,
        checksum=checksum,
        query=query,
        study_type=result.study_type,
        published_at=result.published_at,
    )
    db.add(entry)
    db.commit()
    return entry


def _cache_entry_to_result(entry: WebCacheEntry) -> WebResult:
    return WebResult(
        title=entry.title,
        url=entry.url,
        text=entry.text,
        source=entry.source,
        authority_tier=entry.authority_tier,
        published_at=entry.published_at,
        study_type=entry.study_type,
    )


async def _fetch_web_results(
    db: DbSession, settings: Settings, sanitized_query: str, sources: list[WebSource]
) -> list[WebResult]:
    all_results: list[WebResult] = []
    to_fetch: list[WebSource] = []

    for source in sources:
        cached = _get_fresh_cache(db, settings, sanitized_query, source)
        if cached:
            all_results.extend(_cache_entry_to_result(c) for c in cached)
        else:
            to_fetch.append(source)

    if to_fetch:
        tasks = [_PROVIDERS[s](sanitized_query, settings, settings.research_max_results_per_source) for s in to_fetch]
        fetched_lists = await asyncio.gather(*tasks, return_exceptions=True)
        for source, fetched in zip(to_fetch, fetched_lists, strict=True):
            if isinstance(fetched, BaseException):
                # Each provider already catches its own network/parse errors and
                # returns [] — this only guards against something truly unexpected,
                # so one provider's bug still can't sink the rest of the query.
                logger.warning("Provider %s raised unexpectedly", source.value, exc_info=fetched)
                continue
            for result in fetched:
                _cache_result(db, sanitized_query, result)
            all_results.extend(fetched)

    return all_results


def _filter_by_date_range(results: list[WebResult], date_range: str) -> list[WebResult]:
    years = {"5y": 5, "1y": 1}.get(date_range)
    if years is None:  # "any" or unrecognized — never silently drop results over an unknown filter
        return results
    today = datetime.now(UTC).date()
    cutoff = today.replace(year=today.year - years)
    # A result with no known publication date is kept rather than dropped — an
    # unknown date is not evidence the result is stale (spec §2: never assume).
    return [r for r in results if r.published_at is None or r.published_at >= cutoff]


def _to_passage(result: WebResult, score: float) -> RetrievedPassage:
    return RetrievedPassage(
        text=result.text,
        score=score,
        source_title=result.title,
        source_id=result.url,
        collection="web_cache",
        page=None,
        section=result.source.value.upper(),
        chunk_ids=[],
    )


def _citation_dict(item: LabeledEvidence) -> dict:
    passage = item.passage
    return {
        "label": item.label,
        "source_title": passage.source_title,
        "url": passage.source_id if passage.collection == "web_cache" else None,
        "collection": passage.collection,
        "page": passage.page,
        "section": passage.section,
        "excerpt": passage.text[:600],
    }


async def run_research(
    db: DbSession,
    settings: Settings,
    question: str,
    patient: Patient | None,
    sources: list[WebSource],
    date_range: str,
    prefer_reviews: bool,
    created_by: str | None,
) -> ClinicalModuleRun:
    # Mandatory, no bypass (spec §66) — every outbound query is de-identified before
    # anything leaves the machine, regardless of whether Research Mode is even enabled.
    deidentified = deidentify_query(question, patient)

    patient_passages: list[RetrievedPassage] = []
    patient_facts = None
    if patient:
        patient_passages = retrieve(db, question, settings, collection=ChunkCollection.PATIENT_DOCUMENTS, patient_id=patient.id)
        patient_facts = build_patient_facts(db, patient)
    knowledge_passages = retrieve(db, question, settings, collection=ChunkCollection.MEDICAL_KNOWLEDGE)

    web_passages: list[RetrievedPassage] = []
    if settings.enable_research and sources:
        raw_results = await _fetch_web_results(db, settings, deidentified.sanitized_text, sources)
        filtered = _filter_by_date_range(raw_results, date_range)
        ranked = rank_results(deidentified.sanitized_text, filtered, prefer_reviews)
        limit = settings.research_max_results_per_source * max(len(sources), 1)
        web_passages = [_to_passage(r.result, r.rank_score) for r in ranked[:limit]]

    labeled = label_evidence(patient_passages, knowledge_passages, web_passages=web_passages)
    patient_labeled = [item for item in labeled if item.label.startswith("P")]
    local_labeled = [item for item in labeled if item.label.startswith("L")]
    web_labeled = [item for item in labeled if item.label.startswith("W")]

    if patient_facts:
        patient_evidence_block = patient_facts
        if patient_labeled:
            patient_evidence_block += "\n\n" + build_evidence_block(patient_labeled)
    else:
        patient_evidence_block = "(no patient context given)"
    local_evidence_block = build_evidence_block(local_labeled)
    external_evidence_block = (
        build_evidence_block(web_labeled)
        if web_labeled
        else "(Research Mode not enabled, or no external sources selected/returned for this question.)"
    )

    input_params = {
        "question": question,
        "sources": [s.value for s in sources],
        "date_range": date_range,
        "prefer_reviews": prefer_reviews,
    }
    patient_id = patient.id if patient else None

    try:
        result = await generate_research_synthesis(
            question, patient_evidence_block, local_evidence_block, external_evidence_block, settings
        )
    except GenerationError as exc:
        return record_run(db, ClinicalModuleType.RESEARCH, patient_id, None, input_params, None, settings.ollama_model, str(exc), created_by)
    if result is None:
        return record_run(db, ClinicalModuleType.RESEARCH, patient_id, None, input_params, None, settings.ollama_model, _NOT_PARSED_ERROR, created_by)

    cleaned_summary, summary_labels = validate_citations(result.evidence_summary, labeled)
    cleaned_consensus, consensus_labels = validate_citations(result.consensus, labeled)
    used_labels = list(dict.fromkeys([*summary_labels, *consensus_labels]))
    quality = score_evidence_quality(labeled, used_labels)

    used_set = set(used_labels)
    citations = [item for item in labeled if item.label in used_set]

    payload = {
        "evidence_summary": cleaned_summary,
        "consensus": cleaned_consensus,
        "conflicting_evidence": result.conflicting_evidence,
        "patient_applicability": result.patient_applicability,
        "exclusion_criteria": result.exclusion_criteria,
        "limitations": result.limitations,
        "evidence_quality": quality.value,
        "citations": [_citation_dict(c) for c in citations],
        "research_mode_used": bool(web_labeled),
        "deidentification": {
            "removed_count": deidentified.removed_count,
            "removed_categories": deidentified.removed_categories,
        },
    }
    return record_run(db, ClinicalModuleType.RESEARCH, patient_id, None, input_params, payload, settings.ollama_model, None, created_by)
