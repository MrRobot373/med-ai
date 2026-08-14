from __future__ import annotations

import os
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


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as c:
        yield c
