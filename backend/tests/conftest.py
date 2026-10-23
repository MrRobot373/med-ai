"""Test harness: isolated temp data dir + SQLite file, fake AI providers (no network)."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="gms-test-"))
os.environ["DATA_DIR"] = str(_TMP)
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "admin@test.local"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "Admin@12345"
os.environ["APP_SECRET_KEY"] = "test-secret"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import db as app_db  # noqa: E402
from app.ai import registry  # noqa: E402
from app.core.errors import ServiceUnavailable  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.devtools.mock_ai import hash_embed  # noqa: E402
from app.models import User  # noqa: E402
from app.rag import vector_store  # noqa: E402
from app.services import rate_limit, runtime_config  # noqa: E402


class FakeLLM:
    model = "fake-llm"

    def __init__(self, behaviour: dict):
        self.behaviour = behaviour

    async def stream(self, messages, **kwargs):
        self.behaviour.setdefault("calls", []).append(messages)
        if self.behaviour.get("fail"):
            raise ServiceUnavailable("Cannot reach the language model (fake outage).")
        text = self.behaviour.get("reply") or self._default(messages, kwargs.get("json_mode"))
        for piece in re.findall(r"\S+\s*", text):
            yield piece

    async def complete(self, messages, **kwargs):
        return "".join([p async for p in self.stream(messages, **kwargs)]).strip()

    def _default(self, messages, json_mode):
        content = messages[-1].content
        if json_mode:
            return json.dumps(
                self.behaviour.get("json")
                or {
                    "one_liner": "Summary",
                    "answer": "Answer [K1]",
                    "key_points": [],
                    "abstained": False,
                    "medications": [],
                }
            )
        labels = re.findall(r"^\[([PKW]\d+)\]", content, re.M)
        cited = " ".join(f"[{x}]" for x in labels[:2])
        return f"Based on the evidence, the finding is documented {cited} [R]. Unsupported claim [P99]."


class FakeEmbedder:
    async def embed_documents(self, texts):
        return [hash_embed(t, 64) for t in texts]

    async def embed_query(self, text):
        return hash_embed(text, 64)

    async def dimension(self):
        return 64


class FakeReranker:
    enabled = False
    label = "disabled"

    async def score(self, query, docs):
        return [0.0] * len(docs)


@pytest.fixture
def ai():
    """Mutable behaviour for the fake LLM: set ai['reply'], ai['json'], ai['fail']."""
    return {}


@pytest.fixture(autouse=True)
def _env(monkeypatch, ai):
    os.environ["DATA_DIR"] = str(_TMP)
    from app.core.config import get_settings

    get_settings.cache_clear()
    vector_store.reset_clients()
    import shutil

    shutil.rmtree(_TMP / "vectors", ignore_errors=True)
    app_db.Base.metadata.drop_all(app_db.engine)
    with app_db.engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS chunks_fts"))
    app_db.init_db()
    runtime_config.invalidate_cache()
    rate_limit.login_limiter._hits.clear()
    monkeypatch.setattr(registry, "llm", lambda cfg: FakeLLM(ai))
    monkeypatch.setattr(registry, "vision_llm", lambda cfg: FakeLLM(ai))
    monkeypatch.setattr(registry, "embedder", lambda cfg: FakeEmbedder())
    monkeypatch.setattr(registry, "reranker", lambda cfg: FakeReranker())
    yield
    vector_store.reset_clients()


@pytest.fixture
def client():
    from app.main import create_app

    with TestClient(create_app(skip_migrations=True)) as c:
        yield c


def make_user(email: str, role: str, password: str = "Password@123") -> None:
    db = app_db.SessionLocal()
    db.add(User(email=email, full_name=email.split("@")[0].title(), role=role, password_hash=hash_password(password)))
    db.commit()
    db.close()


def login(client, email="admin@test.local", password="Admin@12345"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def admin(client):
    login(client)
    return client


@pytest.fixture
def clinician(client):
    make_user("doc@test.local", "clinician")
    login(client, "doc@test.local", "Password@123")
    return client


def lab_pdf(name: str, mrn: str, rows: list[tuple], date: str = "2026-09-01") -> bytes:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    y = 60
    for line in [
        f"Patient name: {name}",
        f"MRN: {mrn}",
        f"Report date: {date}",
        "Test | Result | Unit | Reference range",
    ] + [" | ".join(r) for r in rows]:
        page.insert_text((50, y), line, fontsize=10)
        y += 15
    data = doc.tobytes()
    doc.close()
    return data


def create_patient(client, mrn="T-100", first="Alice", last="Tester", **extra) -> dict:
    r = client.post(
        "/api/patients", json={"mrn": mrn, "first_name": first, "last_name": last, "sex": "female", **extra}
    )
    assert r.status_code == 201, r.text
    return r.json()


def upload(client, patient_id, data: bytes, filename="report.pdf", **form):
    r = client.post(
        f"/api/patients/{patient_id}/documents", files={"file": (filename, data, "application/pdf")}, data=form
    )
    return r
