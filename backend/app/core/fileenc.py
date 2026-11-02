"""Authenticated file encryption (AES-256-GCM, chunked) for uploads and backups.

Format:  MAGIC (8) | base nonce (8) | chunks...
Each chunk is `len (4, big-endian) | ciphertext+tag`, encrypted with nonce = base nonce ‖ counter (4)
and associated data = MAGIC ‖ counter ‖ final-flag. The final-flag stops an attacker truncating the
file or reordering chunks without detection.
"""

from __future__ import annotations

import base64
import hashlib
import os
import struct
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"GMSENC1\n"
CHUNK = 1024 * 1024


class DecryptionError(Exception):
    pass


def derive_key(secret: str) -> bytes:
    """32-byte key from a configured secret: a base64 32-byte value is used as is, anything else is
    stretched with scrypt (so a passphrase is acceptable)."""
    try:
        raw = base64.urlsafe_b64decode(secret + "=" * (-len(secret) % 4))
        if len(raw) == 32:
            return raw
    except Exception:  # noqa: S110 - not base64: treat as a passphrase
        pass
    return hashlib.scrypt(secret.encode(), salt=b"gms-clinical-ai/data-key", n=2**14, r=8, p=1, dklen=32)


def new_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def is_encrypted(head: bytes) -> bool:
    return head[: len(MAGIC)] == MAGIC


def _aad(counter: int, final: bool) -> bytes:
    return MAGIC + struct.pack(">I?", counter, final)


def encrypt_stream(src: BinaryIO, dst: BinaryIO, key: bytes) -> None:
    aes = AESGCM(key)
    base = os.urandom(8)
    dst.write(MAGIC + base)
    counter = 0
    block = src.read(CHUNK)
    while True:
        nxt = src.read(CHUNK)
        final = not nxt
        ct = aes.encrypt(base + struct.pack(">I", counter), block, _aad(counter, final))
        dst.write(struct.pack(">I", len(ct)) + ct)
        counter += 1
        if final:
            return
        block = nxt


def decrypt_chunks(src: BinaryIO, key: bytes) -> Iterator[bytes]:
    aes = AESGCM(key)
    head = src.read(len(MAGIC) + 8)
    if not is_encrypted(head) or len(head) < len(MAGIC) + 8:
        raise DecryptionError("Not an encrypted file.")
    base = head[len(MAGIC) :]
    counter = 0
    while True:
        hdr = src.read(4)
        if len(hdr) < 4:
            raise DecryptionError("The file is truncated.")
        (n,) = struct.unpack(">I", hdr)
        ct = src.read(n)
        if len(ct) < n:
            raise DecryptionError("The file is truncated.")
        peek = src.read(1)
        final = not peek
        if peek:
            src.seek(-1, os.SEEK_CUR)
        try:
            yield aes.decrypt(base + struct.pack(">I", counter), ct, _aad(counter, final))
        except InvalidTag as exc:
            raise DecryptionError("Wrong key, or the file was modified.") from exc
        counter += 1
        if final:
            return


def encrypt_bytes(data: bytes, key: bytes) -> bytes:
    import io

    out = io.BytesIO()
    encrypt_stream(io.BytesIO(data), out, key)
    return out.getvalue()


def decrypt_bytes(blob: bytes, key: bytes) -> bytes:
    import io

    return b"".join(decrypt_chunks(io.BytesIO(blob), key))


def encrypt_file(src: Path, dst: Path, key: bytes) -> None:
    with src.open("rb") as a, dst.open("wb") as b:
        encrypt_stream(a, b, key)


def decrypt_file(src: Path, dst: Path, key: bytes) -> None:
    with src.open("rb") as a, dst.open("wb") as b:
        for part in decrypt_chunks(a, key):
            b.write(part)
