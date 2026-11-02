"""Where uploaded files live, and the one place that reads and writes them.

With `DATA_ENCRYPTION_KEY` set, new files are written encrypted (AES-256-GCM); reads accept both
encrypted and plain files, so enabling encryption on an existing install is safe and
`python -m app.cli encrypt-existing` converts what is already there.

This protects the uploaded documents. The database and the search index are protected by
encrypting the disk or volume they sit on, which the installer asks the operator to confirm.
"""

from __future__ import annotations

from pathlib import Path

from app.core import fileenc
from app.core.config import get_settings


def _key() -> bytes | None:
    secret = get_settings().data_encryption_key
    return fileenc.derive_key(secret) if secret else None


def encryption_enabled() -> bool:
    return _key() is not None


def write(path: Path, data: bytes) -> None:
    key = _key()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(fileenc.encrypt_bytes(data, key) if key else data)
    tmp.replace(path)


def read(path: str | Path) -> bytes:
    raw = Path(path).read_bytes()
    if fileenc.is_encrypted(raw[:8]):
        key = _key()
        if key is None:
            raise fileenc.DecryptionError("This file is encrypted but DATA_ENCRYPTION_KEY is not set.")
        return fileenc.decrypt_bytes(raw, key)
    return raw


def exists(path: str | Path) -> bool:
    return Path(path).exists()


def delete(path: str | Path) -> None:
    Path(path).unlink(missing_ok=True)


def encrypt_existing(root: Path | None = None) -> tuple[int, int]:
    """Encrypts every plain upload in place. Returns (converted, already encrypted)."""
    key = _key()
    if key is None:
        raise fileenc.DecryptionError("Set DATA_ENCRYPTION_KEY first.")
    base = root or get_settings().uploads_dir
    done = skipped = 0
    for p in base.rglob("*"):
        if not p.is_file() or p.suffix == ".part":
            continue
        with p.open("rb") as f:
            head = f.read(8)
        if fileenc.is_encrypted(head):
            skipped += 1
            continue
        write(p, p.read_bytes())
        done += 1
    return done, skipped
