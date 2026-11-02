"""Backups: encrypted, verifiable, pruned, scheduled — and restorable through the real command line."""

import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app import db as app_db
from app.core.config import get_settings
from app.services import backup
from tests.conftest import create_patient, lab_pdf, upload

KEY = "correct horse battery staple"


@pytest.fixture
def keyed(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", KEY)
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))
    get_settings.cache_clear()
    yield tmp_path / "backups"
    get_settings.cache_clear()


def test_backup_run_verify_and_download(admin, keyed):
    pid = create_patient(admin, mrn="BK-1")["id"]
    assert upload(admin, pid, lab_pdf("Alice Tester", "BK-1", [("HbA1c", "7.1", "%", "4.0-5.6")])).status_code == 201
    r = admin.post("/api/system/backup/run")
    assert r.status_code == 200
    st = r.json()
    assert st["encrypted"] and len(st["backups"]) == 1 and st["last_error"] is None
    name = st["backups"][0]["file"]
    assert name.endswith(".gmsbak")

    raw = (keyed / name).read_bytes()
    assert raw.startswith(b"GMSENC1") and b"BK-1" not in raw and b"SQLite format" not in raw  # nothing readable inside

    v = admin.post("/api/system/backup/verify", json={"file": name}).json()
    assert v["ok"] and v["patients"] == 1 and v["documents"] == 1 and v["files"] >= 2
    assert admin.get("/api/system/backup").json()["last_verify_ok"] is True
    dl = admin.get(f"/api/system/backup/download/{name}")
    assert dl.status_code == 200 and dl.content == raw


def test_a_modified_or_wrongly_keyed_backup_is_refused(admin, keyed, monkeypatch):
    create_patient(admin, mrn="BK-2")
    name = admin.post("/api/system/backup/run").json()["backups"][0]["file"]
    path = keyed / name
    good = path.read_bytes()
    bad = bytearray(good)
    bad[len(bad) // 2] ^= 1
    path.write_bytes(bytes(bad))
    r = admin.post("/api/system/backup/verify", json={"file": name})
    assert r.status_code == 422 and "modified" in r.json()["detail"]
    assert admin.get("/api/system/backup").json()["last_verify_ok"] is False
    path.write_bytes(good[: len(good) // 2])  # truncated
    assert admin.post("/api/system/backup/verify", json={"file": name}).status_code == 422
    path.write_bytes(good)
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", "some other key")
    get_settings.cache_clear()
    assert admin.post("/api/system/backup/verify", json={"file": name}).status_code == 422


def test_backups_are_admin_only_and_names_cannot_escape_the_folder(admin, keyed, clinician):
    for method, url in (
        ("get", "/api/system/backup"),
        ("post", "/api/system/backup/run"),
        ("get", "/api/system/backup/download/x"),
    ):
        assert getattr(clinician, method)(url).status_code == 403


def test_path_traversal_is_rejected(admin, keyed):
    admin.post("/api/system/backup/run")
    for evil in ("../../etc/passwd", "..%2F..%2Fetc%2Fpasswd", "gms-backup-../x", "notabackup"):
        assert admin.get(f"/api/system/backup/download/{evil}").status_code in (404, 422)
    assert admin.post("/api/system/backup/verify", json={"file": "../../etc/passwd"}).status_code == 404
    assert admin.delete("/api/system/backup/..%2Fsecret").status_code in (404, 405)


def test_old_backups_are_pruned_to_the_configured_number(admin, keyed):
    for i in range(4):
        (keyed.mkdir(parents=True, exist_ok=True))
        f = keyed / f"gms-backup-2026010{i + 1}-000000.gmsbak"
        f.write_bytes(b"x")
        os.utime(f, (1_700_000_000 + i, 1_700_000_000 + i))
    admin.put("/api/settings/backup", json={"keep": 2})
    admin.post("/api/system/backup/run")
    names = [b["file"] for b in admin.get("/api/system/backup").json()["backups"]]
    assert len(names) == 2 and not any("20260101" in n for n in names)


def test_schedule_runs_once_a_day_after_its_time(admin, keyed):
    tz = ZoneInfo("Asia/Kolkata")
    db = app_db.SessionLocal()
    try:
        admin.put("/api/settings/backup", json={"time": "02:00", "enabled": True})
        before = datetime(2026, 11, 2, 1, 30, tzinfo=tz)
        after = datetime(2026, 11, 2, 2, 5, tzinfo=tz)
        assert backup.due(db, before) is False
        assert backup.due(db, after) is True
        backup.run_and_record(db, include_vectors=False, keep=5, by="test")
        # the backup was taken "now" (real clock), so judge "today" by that: a later tick on the same day is not due
        today = datetime.now(tz)
        later_same_day = today.replace(hour=23, minute=59)
        assert backup.due(db, later_same_day) is False
        assert backup.due(db, later_same_day + timedelta(days=1)) is True
        admin.put("/api/settings/backup", json={"enabled": False})
        assert backup.due(db, later_same_day + timedelta(days=1)) is False
    finally:
        db.close()


def test_unencrypted_backups_are_refused_in_production(admin, monkeypatch, tmp_path):
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "b"))
    monkeypatch.delenv("BACKUP_ENCRYPTION_KEY", raising=False)
    get_settings.cache_clear()
    monkeypatch.setattr(type(get_settings()), "is_production", property(lambda self: True))
    from app.core.errors import AppError

    with pytest.raises(AppError, match="BACKUP_ENCRYPTION_KEY"):
        backup.create()


def test_security_checklist_reports_backup_health(admin, keyed):
    items = {i["id"]: i for i in admin.get("/api/system/security").json()["items"]}
    assert (
        items["backup"]["ok"] is False
        and items["backup_encrypted"]["ok"] is True
        and items["backup_tested"]["ok"] is False
    )
    name = admin.post("/api/system/backup/run").json()["backups"][0]["file"]
    admin.post("/api/system/backup/verify", json={"file": name})
    items = {i["id"]: i for i in admin.get("/api/system/security").json()["items"]}
    assert items["backup"]["ok"] and items["backup_tested"]["ok"]


def test_restore_through_the_command_line_brings_everything_back(tmp_path):
    """The real thing, in a separate process and a separate data folder: back up, lose the data, restore."""
    data = tmp_path / "data"
    data.mkdir()
    env = {
        **os.environ,
        "DATA_DIR": str(data),
        "DATABASE_URL": f"sqlite:///{(data / 'gms.db').as_posix()}",
        "BACKUP_ENCRYPTION_KEY": KEY,
        "APP_SECRET_KEY": "x" * 40,
        "BOOTSTRAP_ADMIN_PASSWORD": "Blue-Heron-Walks-0914",
        "BACKUP_DIR": str(data / "backups"),
    }
    backend = Path(__file__).resolve().parents[1]

    def py(code: str) -> str:
        r = subprocess.run(
            [sys.executable, "-c", code], cwd=backend, env=env, capture_output=True, text=True, timeout=120
        )
        assert r.returncode == 0, r.stderr[-2000:]
        return r.stdout.strip()

    def cli(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "app.cli", *args], cwd=backend, env=env, capture_output=True, text=True, timeout=120
        )

    py(
        "from app.main import run_migrations, bootstrap; run_migrations(); bootstrap();"
        "from app.db import SessionLocal; from app.models import Patient; db=SessionLocal();"
        "[db.add(Patient(mrn=f'R-{i}', first_name='Re', last_name=f'Store{i}')) for i in range(3)]; db.commit();"
        "from app.core.config import get_settings; u=get_settings().uploads_dir; u.mkdir(parents=True, exist_ok=True); (u/'scan.bin').write_bytes(b'z'*4096)"
    )
    made = cli("backup")
    assert made.returncode == 0 and "encrypted" in made.stdout
    name = next(p.name for p in (data / "backups").glob("*.gmsbak"))
    assert cli("backup-verify", name).returncode == 0

    py(
        "from app.db import SessionLocal; from app.models import Patient; db=SessionLocal(); [db.delete(p) for p in db.query(Patient)]; db.commit()"
    )
    (data / "uploads" / "scan.bin").unlink()
    assert (
        py(
            "from app.db import SessionLocal; from app.models import Patient; print(SessionLocal().query(Patient).count())"
        )
        == "0"
    )

    refused = cli("restore", name)  # without --yes nothing happens
    assert refused.returncode == 2 and "--yes" in refused.stdout
    assert (
        py(
            "from app.db import SessionLocal; from app.models import Patient; print(SessionLocal().query(Patient).count())"
        )
        == "0"
    )

    done = cli("restore", name, "--yes")
    assert done.returncode == 0, done.stderr
    assert (
        py(
            "from app.db import SessionLocal; from app.models import Patient; print(SessionLocal().query(Patient).count())"
        )
        == "3"
    )
    assert (data / "uploads" / "scan.bin").read_bytes() == b"z" * 4096
    assert list(data.glob("before-restore-*"))  # the old data was moved aside, not destroyed
    assert cli("audit-verify").returncode == 0


def test_documents_left_half_processed_by_a_crash_are_found_and_resumed(admin):
    from app.models import Document
    from app.services import documents

    pid = create_patient(admin, mrn="REC-1")["id"]
    up = upload(admin, pid, lab_pdf("Alice Tester", "REC-1", [("HbA1c", "7.1", "%", "4.0-5.6")])).json()
    db = app_db.SessionLocal()
    try:
        doc = db.get(Document, up["id"])
        assert doc.status == "ready"
        assert documents.stuck_ids() == []  # healthy documents are left alone
        doc.status = "processing"  # as if the server had stopped mid-way
        db.commit()
        assert documents.stuck_ids() == []  # …but one that is only seconds old may still be running
        db.execute(
            Document.__table__.update()
            .where(Document.id == doc.id)
            .values(updated_at=datetime.now(ZoneInfo("UTC")) - timedelta(minutes=10))
        )
        db.commit()
        assert documents.stuck_ids() == [doc.id]
    finally:
        db.close()
    import asyncio

    asyncio.run(documents.process(up["id"]))
    db = app_db.SessionLocal()
    try:
        assert db.get(Document, up["id"]).status == "ready" and documents.stuck_ids() == []
    finally:
        db.close()
