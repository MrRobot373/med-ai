"""Research orchestration service (spec §64-72). Providers and the LLM call are
mocked (real network/generation verified live); caching, de-identification wiring,
and date filtering are exercised against a real DB and real logic.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.config.settings import get_settings
from app.db.session import SessionLocal
from app.models.clinical_module_run import ClinicalModuleRun, ClinicalModuleType
from app.models.patient import Patient, Sex
from app.models.web_cache import AuthorityTier, WebCacheEntry, WebSource
from app.research.paper_assistant import ResearchSynthesis
from app.research.providers.base import WebResult
from app.services import research as research_service


def _make_patient(db) -> Patient:
    patient = Patient(
        id=str(uuid.uuid4()),
        mrn=f"TEST-{uuid.uuid4().hex[:8]}",
        first_name="Priya",
        last_name="Ramanathan",
        date_of_birth=date(1970, 5, 4),
        sex=Sex.FEMALE,
        synthetic=True,
    )
    db.add(patient)
    db.commit()
    return patient


def _cleanup(db, patient: Patient | None = None) -> None:
    db.query(WebCacheEntry).delete()
    db.query(ClinicalModuleRun).filter(ClinicalModuleRun.module_type == ClinicalModuleType.RESEARCH).delete()
    if patient:
        db.query(Patient).filter(Patient.id == patient.id).delete()
    db.commit()


def _result(title="Result", text="glaucoma treatment content", source=WebSource.PUBMED, tier=AuthorityTier.C) -> WebResult:
    return WebResult(title=title, url="https://pubmed.ncbi.nlm.nih.gov/1/", text=text, source=source, authority_tier=tier)


# --- available_sources ---------------------------------------------------------------------


def test_available_sources_always_includes_the_no_key_apis(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(research_service, "searxng_reachable", lambda settings: False)
    sources = research_service.available_sources(get_settings())
    assert set(sources) == {WebSource.PUBMED, WebSource.FDA, WebSource.CLINICALTRIALS}


def test_available_sources_includes_searxng_when_reachable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(research_service, "searxng_reachable", lambda settings: True)
    sources = research_service.available_sources(get_settings())
    assert WebSource.SEARXNG in sources


# --- caching ---------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_web_results_reuses_a_fresh_cache_entry_without_refetching(monkeypatch: pytest.MonkeyPatch):
    async def fail_if_called(query, settings, max_results):
        raise AssertionError("provider should not be called when a fresh cache entry exists")

    monkeypatch.setattr(research_service, "_PROVIDERS", {WebSource.PUBMED: fail_if_called})
    db = SessionLocal()
    try:
        db.add(
            WebCacheEntry(
                url="https://pubmed.ncbi.nlm.nih.gov/1/", title="Cached result", source=WebSource.PUBMED,
                authority_tier=AuthorityTier.C, text="cached text", checksum="abc123", query="glaucoma treatment",
            )
        )
        db.commit()

        results = await research_service._fetch_web_results(db, get_settings(), "glaucoma treatment", [WebSource.PUBMED])
        assert len(results) == 1
        assert results[0].title == "Cached result"
    finally:
        _cleanup(db)
        db.close()


@pytest.mark.asyncio
async def test_fetch_web_results_refetches_when_cache_entry_is_stale(monkeypatch: pytest.MonkeyPatch):
    called = False

    async def fake_provider(query, settings, max_results):
        nonlocal called
        called = True
        return [_result(title="Fresh result")]

    monkeypatch.setattr(research_service, "_PROVIDERS", {WebSource.PUBMED: fake_provider})
    db = SessionLocal()
    try:
        stale_time = datetime.now(UTC) - timedelta(hours=999)
        entry = WebCacheEntry(
            url="https://pubmed.ncbi.nlm.nih.gov/1/", title="Stale result", source=WebSource.PUBMED,
            authority_tier=AuthorityTier.C, text="stale text", checksum="def456", query="glaucoma treatment",
        )
        db.add(entry)
        db.commit()
        db.query(WebCacheEntry).filter(WebCacheEntry.id == entry.id).update({"retrieved_at": stale_time})
        db.commit()

        results = await research_service._fetch_web_results(db, get_settings(), "glaucoma treatment", [WebSource.PUBMED])
        assert called is True
        assert any(r.title == "Fresh result" for r in results)
    finally:
        _cleanup(db)
        db.close()


def test_cache_result_is_idempotent_by_checksum():
    db = SessionLocal()
    try:
        result = _result(text="identical content")
        first = research_service._cache_result(db, "some query", result)
        second = research_service._cache_result(db, "some query", result)
        assert first.id == second.id
        assert db.query(WebCacheEntry).count() == 1
    finally:
        _cleanup(db)
        db.close()


# --- date filtering ------------------------------------------------------------------------


def test_filter_by_date_range_any_keeps_everything():
    old = _result(); old.published_at = date(2001, 1, 1)
    results = research_service._filter_by_date_range([old], "any")
    assert results == [old]


def test_filter_by_date_range_excludes_results_older_than_the_window():
    old = _result(); old.published_at = date(2001, 1, 1)
    recent = _result(); recent.published_at = datetime.now(UTC).date()
    results = research_service._filter_by_date_range([old, recent], "1y")
    assert old not in results
    assert recent in results


def test_filter_by_date_range_keeps_undated_results():
    undated = _result()
    undated.published_at = None
    results = research_service._filter_by_date_range([undated], "1y")
    assert undated in results


# --- run_research orchestration ------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_research_deidentifies_before_any_provider_sees_the_query(monkeypatch: pytest.MonkeyPatch):
    captured_queries = []

    async def spy_provider(query, settings, max_results):
        captured_queries.append(query)
        return []

    monkeypatch.setattr(research_service, "_PROVIDERS", {WebSource.PUBMED: spy_provider})
    monkeypatch.setattr("app.services.research.retrieve", lambda *a, **k: [])

    async def fake_synthesis(*args, **kwargs):
        return ResearchSynthesis(evidence_summary="No evidence found.")

    monkeypatch.setattr("app.services.research.generate_research_synthesis", fake_synthesis)

    settings = get_settings()
    monkeypatch.setattr(settings, "enable_research", True)

    db = SessionLocal()
    try:
        patient = _make_patient(db)
        await research_service.run_research(
            db, settings, f"{patient.first_name} {patient.last_name} MRN {patient.mrn} needs glaucoma treatment advice",
            patient, [WebSource.PUBMED], "any", True, None,
        )
        assert len(captured_queries) == 1
        assert patient.first_name not in captured_queries[0]
        assert patient.last_name not in captured_queries[0]
        assert patient.mrn not in captured_queries[0]
    finally:
        _cleanup(db, patient)
        db.close()


@pytest.mark.asyncio
async def test_run_research_skips_web_fetch_when_research_mode_is_disabled(monkeypatch: pytest.MonkeyPatch):
    called = False

    async def fail_if_called(query, settings, max_results):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(research_service, "_PROVIDERS", {WebSource.PUBMED: fail_if_called})
    monkeypatch.setattr("app.services.research.retrieve", lambda *a, **k: [])

    async def fake_synthesis(*args, **kwargs):
        return ResearchSynthesis(evidence_summary="Local-only answer.")

    monkeypatch.setattr("app.services.research.generate_research_synthesis", fake_synthesis)

    settings = get_settings()
    monkeypatch.setattr(settings, "enable_research", False)

    db = SessionLocal()
    try:
        run = await research_service.run_research(db, settings, "glaucoma treatment options", None, [WebSource.PUBMED], "any", True, None)
        assert called is False
        import json

        payload = json.loads(run.payload)
        assert payload["research_mode_used"] is False
    finally:
        _cleanup(db)
        db.close()


@pytest.mark.asyncio
async def test_run_research_strips_invalid_citation_labels(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.services.research.retrieve", lambda *a, **k: [])

    async def fake_synthesis(*args, **kwargs):
        return ResearchSynthesis(evidence_summary="No real evidence supports this [L9].", consensus="")

    monkeypatch.setattr("app.services.research.generate_research_synthesis", fake_synthesis)
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_research", False)

    db = SessionLocal()
    try:
        run = await research_service.run_research(db, settings, "some question", None, [], "any", True, None)
        import json

        payload = json.loads(run.payload)
        assert "[L9]" not in payload["evidence_summary"]
        assert payload["evidence_quality"] == "insufficient"
    finally:
        _cleanup(db)
        db.close()
