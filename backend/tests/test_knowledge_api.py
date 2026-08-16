"""Knowledge Administration API — RBAC (admin-only), CRUD, and the
upload -> activate / reindex / rollback flow (Phase 12, spec's Knowledge Administration
section). Real indexing is mocked (see conftest.py's `_mock_rag_indexing`), matching
every other module's test convention; TestClient runs `BackgroundTasks` synchronously,
so the activation triggered by upload/reindex/activate-version has already completed
by the time each request returns.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from tests.sample_documents import make_pdf_bytes

PASSWORD = "correct-horse-battery-6"


def _login_as(client: TestClient, email: str, role: UserRole) -> User:
    db = SessionLocal()
    try:
        user = User(email=email, display_name=email.split("@")[0], password_hash=hash_password(PASSWORD), role=role, active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
    finally:
        db.close()
    resp = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200
    return user


def _pdf(text: str) -> bytes:
    # Real text, long enough to skip the OCR fallback path (see test_knowledge_service.py).
    return make_pdf_bytes([text])


def _create_document(client: TestClient, title: str = "ICO Glaucoma Guidelines") -> dict:
    resp = client.post("/api/knowledge/documents", json={"title": title, "source": "ICO", "authority_tier": "a"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_all_routes_require_admin_role(client: TestClient):
    _login_as(client, "doctor.knowledge1@example.com", UserRole.DOCTOR)
    assert client.get("/api/knowledge/documents").status_code == 403
    assert client.post("/api/knowledge/documents", json={"title": "X", "authority_tier": "d"}).status_code == 403


def test_create_list_and_get_document(client: TestClient):
    _login_as(client, "admin.knowledge2@example.com", UserRole.ADMIN)
    created = _create_document(client)
    assert created["archived"] is False

    listed = client.get("/api/knowledge/documents").json()
    assert any(d["id"] == created["id"] for d in listed)

    detail = client.get(f"/api/knowledge/documents/{created['id']}").json()
    assert detail["versions"] == []


def test_get_unknown_document_404s(client: TestClient):
    _login_as(client, "admin.knowledge3@example.com", UserRole.ADMIN)
    assert client.get("/api/knowledge/documents/does-not-exist").status_code == 404


def test_patch_updates_only_supplied_fields(client: TestClient):
    _login_as(client, "admin.knowledge4@example.com", UserRole.ADMIN)
    created = _create_document(client)
    patched = client.patch(f"/api/knowledge/documents/{created['id']}", json={"specialty": "Glaucoma"}).json()
    assert patched["specialty"] == "Glaucoma"
    assert patched["title"] == created["title"]


def test_upload_version_auto_activates_it(client: TestClient):
    _login_as(client, "admin.knowledge5@example.com", UserRole.ADMIN)
    created = _create_document(client)
    content = _pdf("Laser trabeculoplasty is an appropriate initial therapy for open-angle glaucoma.")

    resp = client.post(
        f"/api/knowledge/documents/{created['id']}/versions?effective_date=2024-01-15",
        files={"file": ("guideline.pdf", content, "application/pdf")},
    )
    assert resp.status_code == 201, resp.text
    version = resp.json()
    assert version["version_number"] == 1

    # BackgroundTasks already ran synchronously under TestClient — the detail view
    # reflects the completed, now-active version without any polling needed here.
    detail = client.get(f"/api/knowledge/documents/{created['id']}").json()
    assert len(detail["versions"]) == 1
    assert detail["versions"][0]["is_active"] is True
    assert detail["versions"][0]["ingestion_status"] == "completed"
    assert detail["versions"][0]["effective_date"] == "2024-01-15"


def test_upload_version_rejects_non_document_extension(client: TestClient):
    _login_as(client, "admin.knowledge6@example.com", UserRole.ADMIN)
    created = _create_document(client)
    resp = client.post(
        f"/api/knowledge/documents/{created['id']}/versions",
        files={"file": ("scan.png", b"\x89PNG\r\n\x1a\n" + b"0" * 20, "image/png")},
    )
    assert resp.status_code == 422


def test_upload_duplicate_version_content_conflicts(client: TestClient):
    _login_as(client, "admin.knowledge7@example.com", UserRole.ADMIN)
    created = _create_document(client)
    content = _pdf("Identical guideline content used twice on purpose for this test case.")
    first = client.post(f"/api/knowledge/documents/{created['id']}/versions", files={"file": ("a.pdf", content, "application/pdf")})
    assert first.status_code == 201
    second = client.post(f"/api/knowledge/documents/{created['id']}/versions", files={"file": ("a_copy.pdf", content, "application/pdf")})
    assert second.status_code == 409


def test_activate_version_rolls_back_to_an_older_version(client: TestClient):
    _login_as(client, "admin.knowledge8@example.com", UserRole.ADMIN)
    created = _create_document(client)
    v1 = client.post(
        f"/api/knowledge/documents/{created['id']}/versions",
        files={"file": ("v1.pdf", _pdf("This is the first edition of the guideline document body text."), "application/pdf")},
    ).json()
    client.post(
        f"/api/knowledge/documents/{created['id']}/versions",
        files={"file": ("v2.pdf", _pdf("This is the second edition of the guideline document body text."), "application/pdf")},
    )

    resp = client.post(f"/api/knowledge/documents/{created['id']}/activate-version", json={"version_id": v1["id"]})
    assert resp.status_code == 200, resp.text

    detail = client.get(f"/api/knowledge/documents/{created['id']}").json()
    versions_by_number = {v["version_number"]: v for v in detail["versions"]}
    assert versions_by_number[1]["is_active"] is True
    assert versions_by_number[2]["is_active"] is False


def test_activate_version_with_wrong_document_id_404s(client: TestClient):
    _login_as(client, "admin.knowledge9@example.com", UserRole.ADMIN)
    doc_a = _create_document(client, "Document A")
    doc_b = _create_document(client, "Document B")
    version_a = client.post(
        f"/api/knowledge/documents/{doc_a['id']}/versions",
        files={"file": ("a.pdf", _pdf("Document A's own guideline content goes here for the test."), "application/pdf")},
    ).json()

    resp = client.post(f"/api/knowledge/documents/{doc_b['id']}/activate-version", json={"version_id": version_a["id"]})
    assert resp.status_code == 404


def test_reindex_with_no_versions_is_a_client_error(client: TestClient):
    _login_as(client, "admin.knowledge10@example.com", UserRole.ADMIN)
    created = _create_document(client)
    resp = client.post(f"/api/knowledge/documents/{created['id']}/reindex")
    assert resp.status_code == 422


def test_reindex_reruns_ingestion_for_the_active_version(client: TestClient):
    _login_as(client, "admin.knowledge11@example.com", UserRole.ADMIN)
    created = _create_document(client)
    client.post(
        f"/api/knowledge/documents/{created['id']}/versions",
        files={"file": ("v1.pdf", _pdf("Guideline body text long enough to skip the OCR fallback path here."), "application/pdf")},
    )
    resp = client.post(f"/api/knowledge/documents/{created['id']}/reindex")
    assert resp.status_code == 200, resp.text
    # Mirrors reports.py's own convention: the response reflects the immediate
    # queued state, not the (separately-committed) background task's outcome — the
    # caller re-fetches, exactly like `test_upload_version_auto_activates_it` does.
    assert resp.json()["ingestion_status"] == "queued"

    detail = client.get(f"/api/knowledge/documents/{created['id']}").json()
    assert detail["versions"][0]["ingestion_status"] == "completed"


def test_archive_document_deactivates_its_active_version(client: TestClient):
    _login_as(client, "admin.knowledge12@example.com", UserRole.ADMIN)
    created = _create_document(client)
    client.post(
        f"/api/knowledge/documents/{created['id']}/versions",
        files={"file": ("v1.pdf", _pdf("Guideline body text long enough to skip the OCR fallback path here."), "application/pdf")},
    )
    resp = client.post(f"/api/knowledge/documents/{created['id']}/archive")
    assert resp.status_code == 200
    assert resp.json()["archived"] is True

    default_list = client.get("/api/knowledge/documents").json()
    assert not any(d["id"] == created["id"] for d in default_list)
    with_archived = client.get("/api/knowledge/documents?include_archived=true").json()
    assert any(d["id"] == created["id"] for d in with_archived)


def test_download_version_file_rejects_a_version_from_another_document(client: TestClient):
    _login_as(client, "admin.knowledge13@example.com", UserRole.ADMIN)
    doc_a = _create_document(client, "Document A")
    doc_b = _create_document(client, "Document B")
    version_a = client.post(
        f"/api/knowledge/documents/{doc_a['id']}/versions",
        files={"file": ("a.pdf", _pdf("Document A's own guideline content goes here for the test."), "application/pdf")},
    ).json()

    resp = client.get(f"/api/knowledge/documents/{doc_b['id']}/versions/{version_a['id']}/file")
    assert resp.status_code == 404


def test_download_version_file_returns_the_stored_bytes(client: TestClient):
    _login_as(client, "admin.knowledge14@example.com", UserRole.ADMIN)
    created = _create_document(client)
    version = client.post(
        f"/api/knowledge/documents/{created['id']}/versions",
        files={"file": ("v1.pdf", _pdf("Guideline body text long enough to skip the OCR fallback path here."), "application/pdf")},
    ).json()

    resp = client.get(f"/api/knowledge/documents/{created['id']}/versions/{version['id']}/file")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


@pytest.mark.parametrize("role", [UserRole.DOCTOR, UserRole.VIEWER])
def test_non_admin_roles_cannot_read_documents_either(client: TestClient, role: UserRole):
    # Admin creates one first so there's something to (attempt to) read.
    _login_as(client, f"admin.knowledge15.{role.value}@example.com", UserRole.ADMIN)
    _create_document(client)

    _login_as(client, f"nonadmin.knowledge15.{role.value}@example.com", role)
    assert client.get("/api/knowledge/documents").status_code == 403
