from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

# Point Settings at an isolated on-disk SQLite file for the whole test session. This
# MUST happen before any `app.*` module is imported (conftest.py is collected first),
# since `get_settings()` is process-lifetime cached.
_TEST_DB_PATH = BACKEND_ROOT / "tests" / ".tmp_test.db"
if _TEST_DB_PATH.exists():
    _TEST_DB_PATH.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH.as_posix()}"
os.environ["APP_ENV"] = "test"
os.environ["APP_SECRET_KEY"] = "test-only-secret-key"

# Same isolation for uploaded-report storage — without this, running the test suite
# would write real files into the demo's actual data/uploads/ directory.
_TEST_UPLOAD_DIR = BACKEND_ROOT / "tests" / ".tmp_uploads"
if _TEST_UPLOAD_DIR.exists():
    shutil.rmtree(_TEST_UPLOAD_DIR)
os.environ["UPLOAD_DIR"] = str(_TEST_UPLOAD_DIR)

import pytest
from fastapi.testclient import TestClient

from app import models  # noqa: F401 - populates Base.metadata for create_all
from app.db.base import Base
from app.db.session import engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _create_test_schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if _TEST_DB_PATH.exists():
        _TEST_DB_PATH.unlink()
    if _TEST_UPLOAD_DIR.exists():
        shutil.rmtree(_TEST_UPLOAD_DIR)


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _mock_rag_indexing(monkeypatch: pytest.MonkeyPatch) -> None:
    """RAG indexing (embedding + Qdrant upsert) is mocked out by default for every
    test — it needs a real, slow-to-first-load embedding model and a reachable Qdrant
    instance, neither of which a fast, deterministic, offline unit test suite should
    depend on (same rationale as OCR being mocked per-test in test_reports.py, just
    applied globally here since nearly every report-upload test would otherwise need
    the identical mock). Tests that specifically exercise indexing/retrieval
    (test_rag_*.py) call `index_document()`/`retrieve()` directly rather than through
    the upload API, so this default doesn't affect them.

    Two call sites, two patches — `services/reports.py` imports `index_document`
    directly (for `confirm_patient_match`'s "index now that the mismatch is
    resolved" path) rather than going through `ingestion/pipeline.py`, so patching
    only one left a real Qdrant point behind every time a mismatch-confirmation test
    ran (found via live inspection of the dev Qdrant instance's point count not
    matching its own SQLite chunk rows — see docs/architecture.md's Phase 07
    section)."""
    monkeypatch.setattr("app.ingestion.pipeline.index_document", lambda *args, **kwargs: [])
    monkeypatch.setattr("app.services.reports.index_document", lambda *args, **kwargs: [])
    monkeypatch.setattr("app.services.vision.index_document", lambda *args, **kwargs: [])


@pytest.fixture(autouse=True)
def _mock_vision_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same rationale as `_mock_rag_indexing` above, for Phase 09: any report upload
    whose mime type is image/DICOM automatically triggers vision analysis during
    ingestion (`ingestion/pipeline.py`), which — left unmocked — makes a real,
    slow (~30-100s+ observed live) Ollama vision call per upload. Tests that
    specifically exercise vision analysis (test_vision.py) patch
    `app.vision.analyzer.analyze_image`/`compare_images` themselves with a specific
    return value rather than relying on this default empty-result stub."""

    async def _no_analysis(*args, **kwargs):
        return None

    monkeypatch.setattr("app.services.vision.analyze_image", _no_analysis)
    monkeypatch.setattr("app.services.vision.compare_images", _no_analysis)
