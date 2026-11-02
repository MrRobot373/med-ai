"""Encrypted, verifiable backups of everything the clinic cannot lose, and a safe way back.

What a backup holds
  db/gms.db        a consistent snapshot of the database (taken with SQLite's online backup, no downtime)
  uploads/…        every uploaded report and image (already encrypted if DATA_ENCRYPTION_KEY is set)
  vectors/…        the search index (optional: it can be rebuilt from the database)
  manifest.json    app version, schema revision, counts and a SHA-256 for every file

The archive is a tar.gz that is then encrypted with AES-256-GCM (`.gmsbak`) when BACKUP_ENCRYPTION_KEY is set.
The runtime settings inside the database hold API keys encrypted under APP_SECRET_KEY, so a restore also
needs the same APP_SECRET_KEY — keep both keys somewhere that is *not* the server.

Restore is deliberately command-line only (python -m app.cli restore): replacing the live database from inside
the running app would be one mis-click away from losing the day's work.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import sqlite3
import tarfile
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core import fileenc
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.db import utcnow
from app.models import AppSetting

logger = get_logger("backup")
FORMAT = 1
PREFIX = "gms-backup-"
LOCK_STALE_SECONDS = 4 * 3600


def _sqlite_path() -> Path:
    url = get_settings().resolved_database_url
    if not url.startswith("sqlite:///"):
        raise AppError(
            "Built-in backup supports the bundled SQLite database. This install uses another database; "
            "back it up with that database's own tools.",
            status_code=422,
        )
    return Path(url.removeprefix("sqlite:///"))


def key() -> bytes | None:
    k = get_settings().backup_encryption_key
    return fileenc.derive_key(k) if k else None


def directory() -> Path:
    d = get_settings().backup_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


class _Hashing(io.RawIOBase):
    """Wraps a file so that the bytes tarfile reads are hashed on the way past."""

    def __init__(self, f):
        self.f, self.h = f, hashlib.sha256()

    def readable(self):
        return True

    def read(self, n=-1):
        b = self.f.read(n)
        self.h.update(b)
        return b

    def close(self):
        self.f.close()
        super().close()


def _add_file(tar: tarfile.TarFile, src: Path, arcname: str, hashes: dict) -> None:
    try:
        st = src.stat()
        info = tarfile.TarInfo(arcname)
        info.size, info.mtime, info.mode = st.st_size, st.st_mtime, 0o600
        with src.open("rb") as raw:
            w = _Hashing(raw)
            tar.addfile(info, w)
        hashes[arcname] = w.h.hexdigest()
    except FileNotFoundError:  # a file deleted while the backup ran
        logger.info("Skipped %s: it disappeared during the backup", src)


def _snapshot_db(dst: Path) -> None:
    src = sqlite3.connect(f"file:{_sqlite_path().as_posix()}?mode=ro", uri=True, timeout=30)
    try:
        out = sqlite3.connect(dst)
        try:
            src.backup(out)
        finally:
            out.close()
    finally:
        src.close()


def _counts(dbfile: Path) -> dict:
    c = sqlite3.connect(dbfile)
    try:

        def n(table):
            try:
                return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.Error:
                return None

        rev = None
        with contextlib.suppress(sqlite3.Error):
            rev = c.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        return {
            "schema": rev,
            "patients": n("patients"),
            "documents": n("documents"),
            "users": n("users"),
            "prescriptions": n("prescriptions"),
        }
    finally:
        c.close()


def _lock() -> Path:
    path = directory() / ".lock"
    if path.exists() and time.time() - path.stat().st_mtime < LOCK_STALE_SECONDS:
        raise AppError("A backup is already running.", status_code=409)
    path.write_text(str(os.getpid()))
    return path


def create(*, include_vectors: bool = True, keep: int | None = None) -> dict:
    """Takes a backup now. Returns {file, size, encrypted, sha256, manifest}."""
    from app.api.system import APP_VERSION

    st = get_settings()
    k = key()
    if st.is_production and k is None:
        raise AppError("Set BACKUP_ENCRYPTION_KEY: production backups must be encrypted.", status_code=422)
    lock = _lock()
    started = datetime.now(UTC)
    stamp = started.strftime("%Y%m%d-%H%M%S")
    out_dir = directory()
    final = out_dir / f"{PREFIX}{stamp}{'.gmsbak' if k else '.tar.gz'}"
    tmpdir = Path(tempfile.mkdtemp(prefix="gms-bak-", dir=out_dir))
    try:
        snap = tmpdir / "gms.db"
        _snapshot_db(snap)
        hashes: dict[str, str] = {}
        tar_path = tmpdir / "archive.tar.gz"
        with tarfile.open(tar_path, "w:gz", compresslevel=6) as tar:
            _add_file(tar, snap, "db/gms.db", hashes)
            if st.uploads_dir.exists():
                for f in sorted(st.uploads_dir.rglob("*")):
                    if f.is_file():
                        _add_file(tar, f, f"uploads/{f.relative_to(st.uploads_dir).as_posix()}", hashes)
            if include_vectors and st.vector_dir.exists():
                for f in sorted(st.vector_dir.rglob("*")):
                    if f.is_file() and f.name != ".lock":
                        _add_file(tar, f, f"vectors/{f.relative_to(st.vector_dir).as_posix()}", hashes)
            manifest = {
                "format": FORMAT,
                "created_at": started.isoformat(),
                "app_version": APP_VERSION,
                "encrypted": bool(k),
                "includes_vectors": include_vectors,
                "files": hashes,
                **_counts(snap),
            }
            data = json.dumps(manifest, indent=1).encode()
            info = tarfile.TarInfo("manifest.json")
            info.size, info.mtime = len(data), time.time()
            tar.addfile(info, io.BytesIO(data))
        part = final.with_suffix(final.suffix + ".part")
        if k:
            fileenc.encrypt_file(tar_path, part, k)
        else:
            shutil.copyfile(tar_path, part)
        part.replace(final)
        final.chmod(0o600)
        digest = hashlib.sha256(final.read_bytes()).hexdigest() if final.stat().st_size < 512 * 1024**2 else None
        if keep:
            prune(keep)
        return {
            "file": final.name,
            "size": final.stat().st_size,
            "encrypted": bool(k),
            "sha256": digest,
            "manifest": manifest,
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        with contextlib.suppress(FileNotFoundError):
            lock.unlink()


def listing() -> list[dict]:
    out = []
    for f in sorted(directory().glob(f"{PREFIX}*"), reverse=True):
        if f.suffix in (".gmsbak", ".gz") and not f.name.endswith(".part"):
            out.append(
                {
                    "file": f.name,
                    "size": f.stat().st_size,
                    "created_at": datetime.fromtimestamp(f.stat().st_mtime, UTC).isoformat(),
                    "encrypted": f.suffix == ".gmsbak",
                }
            )
    return out


def path_of(name: str) -> Path:
    if "/" in name or "\\" in name or not name.startswith(PREFIX):
        raise AppError("Unknown backup.", status_code=404)
    p = directory() / name
    if not p.is_file():
        raise AppError("Unknown backup.", status_code=404)
    return p


def prune(keep: int) -> list[str]:
    old = listing()[keep:]
    for b in old:
        (directory() / b["file"]).unlink(missing_ok=True)
    return [b["file"] for b in old]


def _open_archive(file: Path, workdir: Path) -> Path:
    """Decrypts (if needed) into workdir and returns the tar path."""
    if file.suffix == ".gmsbak":
        k = key()
        if k is None:
            raise AppError(
                "This backup is encrypted. Set BACKUP_ENCRYPTION_KEY to the key used when it was made.", status_code=422
            )
        out = workdir / "archive.tar.gz"
        try:
            fileenc.decrypt_file(file, out, k)
        except fileenc.DecryptionError as exc:
            raise AppError(f"This backup cannot be opened: {exc}", status_code=422) from exc
        return out
    return file


def extract_verified(file: Path, dest: Path) -> dict:
    """Unpacks into `dest`, checking every file against the manifest. Returns the manifest."""
    work = Path(tempfile.mkdtemp(prefix="gms-open-", dir=directory()))
    try:
        archive = _open_archive(file, work)
        with tarfile.open(archive, "r:gz") as tar:
            try:
                member = tar.extractfile("manifest.json")
                manifest = json.loads(member.read()) if member else None
            except KeyError:
                manifest = None
            if not manifest or manifest.get("format") != FORMAT:
                raise AppError("This is not a valid backup (no manifest).", status_code=422)
            for m in tar.getmembers():
                if m.name.startswith(("/", "..")) or ".." in Path(m.name).parts:
                    raise AppError("The backup contains an unsafe path.", status_code=422)
            tar.extractall(dest, filter="data")
        for name, expected in manifest["files"].items():
            got = hashlib.sha256((dest / name).read_bytes()).hexdigest() if (dest / name).exists() else None
            if got != expected:
                raise AppError(f"The backup is damaged: {name} does not match its checksum.", status_code=422)
        return manifest
    finally:
        shutil.rmtree(work, ignore_errors=True)


def verify(file: Path) -> dict:
    """Opens a backup file into a scratch folder, checks every checksum and the database's integrity. Changes nothing."""
    scratch = Path(tempfile.mkdtemp(prefix="gms-verify-", dir=directory()))
    try:
        manifest = extract_verified(file, scratch)
        c = sqlite3.connect(scratch / "db" / "gms.db")
        try:
            integrity = c.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            c.close()
        if integrity != "ok":
            raise AppError(f"The database inside this backup is damaged ({integrity}).", status_code=422)
        return {
            "ok": True,
            "file": file.name,
            "created_at": manifest["created_at"],
            "app_version": manifest["app_version"],
            "schema": manifest.get("schema"),
            "patients": manifest.get("patients"),
            "documents": manifest.get("documents"),
            "files": len(manifest["files"]),
        }
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def restore(file: Path) -> dict:
    """Replaces the live data with a backup. The server must be stopped. The old data is moved aside, not deleted."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    st = get_settings()
    dbfile = _sqlite_path()
    scratch = Path(tempfile.mkdtemp(prefix="gms-restore-", dir=directory()))
    try:
        manifest = extract_verified(file, scratch)
        cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "migrations"))
        known = {r.revision for r in ScriptDirectory.from_config(cfg).walk_revisions()}
        if manifest.get("schema") and manifest["schema"] not in known:
            raise AppError(
                "This backup was made by a newer version of the product. Install that version first, then restore.",
                status_code=422,
            )
        aside = st.data_dir / f"before-restore-{datetime.now():%Y%m%d-%H%M%S}"
        aside.mkdir(parents=True)
        for p in (dbfile, Path(f"{dbfile}-wal"), Path(f"{dbfile}-shm")):
            if p.exists():
                shutil.move(str(p), aside / p.name)
        for d in (st.uploads_dir, st.vector_dir):
            if d.exists():
                shutil.move(str(d), aside / d.name)
        dbfile.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(scratch / "db" / "gms.db", dbfile)
        for src, dst in ((scratch / "uploads", st.uploads_dir), (scratch / "vectors", st.vector_dir)):
            if src.exists():
                shutil.copytree(src, dst)
        st.uploads_dir.mkdir(parents=True, exist_ok=True)
        return {
            "restored_from": file.name,
            "created_at": manifest["created_at"],
            "old_data_moved_to": str(aside),
            "schema": manifest.get("schema"),
            "patients": manifest.get("patients"),
            "includes_vectors": manifest.get("includes_vectors"),
        }
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


# ---- status shown in Settings ------------------------------------------------------------------------------------------
def _status(db: Session) -> dict:
    row = db.get(AppSetting, "backup_status")
    return dict(row.value) if row and row.value else {}


def _set_status(db: Session, **changes) -> None:
    value = {**_status(db), **changes}
    db.merge(AppSetting(key="backup_status", value=value, updated_at=utcnow()))
    db.commit()


def status(db: Session) -> dict:
    from app.services import runtime_config

    cfg = runtime_config.load(db).backup
    st = get_settings()
    s = _status(db)
    return {
        **s,
        "config": cfg.model_dump(),
        "encrypted": key() is not None,
        "directory": str(directory()),
        "backups": listing(),
        "supported": st.resolved_database_url.startswith("sqlite:///"),
    }


def run_and_record(db: Session, *, include_vectors: bool, keep: int, by: str = "schedule") -> dict:
    try:
        r = create(include_vectors=include_vectors, keep=keep)
    except Exception as exc:
        msg = getattr(exc, "message", None) or str(exc)
        _set_status(db, last_error=msg, last_error_at=utcnow().isoformat())
        raise
    _set_status(
        db, last_ok_at=utcnow().isoformat(), last_file=r["file"], last_size=r["size"], last_error=None, last_by=by
    )
    return r


def verify_and_record(db: Session, name: str) -> dict:
    """`name` is a file name inside the backup folder (never a path)."""
    try:
        r = verify(path_of(name))
    except AppError as exc:
        _set_status(
            db,
            last_verify_ok=False,
            last_verify_at=utcnow().isoformat(),
            last_verify_message=exc.message,
            last_verify_file=name,
        )
        raise
    _set_status(
        db,
        last_verify_ok=True,
        last_verify_at=utcnow().isoformat(),
        last_verify_message=f"{r['patients']} patients, {r['files']} files",
        last_verify_file=name,
    )
    return r


def due(db: Session, now_local: datetime) -> bool:
    """True when today's scheduled backup has not been taken yet and its time has passed."""
    from app.services import runtime_config

    cfg = runtime_config.load(db).backup
    if not cfg.enabled:
        return False
    hh, mm = (int(x) for x in cfg.time.split(":"))
    if (now_local.hour, now_local.minute) < (hh, mm):
        return False
    last = _status(db).get("last_ok_at")
    if last:
        last_local = datetime.fromisoformat(last).astimezone(now_local.tzinfo)
        if last_local.date() == now_local.date():
            return False
    err_at = _status(db).get("last_error_at")
    # after a failure, wait half an hour before trying again
    return not (err_at and (utcnow() - datetime.fromisoformat(err_at)).total_seconds() < 1800)
