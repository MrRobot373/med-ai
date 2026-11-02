"""Time-based one-time passwords (RFC 6238) with the standard library only.

Compatible with Google Authenticator, Microsoft Authenticator, Authy, 1Password and any other
TOTP app: SHA-1, 6 digits, 30-second step.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

STEP_SECONDS = 30
DIGITS = 6


def new_secret() -> str:
    """160-bit random secret, base32 without padding (what authenticator apps expect)."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _key(secret: str) -> bytes:
    s = secret.strip().replace(" ", "").upper()
    return base64.b32decode(s + "=" * (-len(s) % 8))


def code_at(secret: str, step: int, digits: int = DIGITS) -> str:
    digest = hmac.new(_key(secret), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**digits).zfill(digits)


def current_step(now: float | None = None) -> int:
    return int((time.time() if now is None else now) // STEP_SECONDS)


def verify(
    secret: str, code: str, *, last_step: int | None = None, now: float | None = None, window: int = 1
) -> int | None:
    """Returns the matched time step, or None. Accepts ±`window` steps for clock drift, and never
    a step at or before `last_step`, so a code cannot be used twice."""
    code = (code or "").strip().replace(" ", "")
    if len(code) != DIGITS or not code.isdigit():
        return None
    now_step = current_step(now)
    for step in range(now_step - window, now_step + window + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(code_at(secret, step), code):
            return step
    return None


def provisioning_uri(secret: str, account: str, issuer: str) -> str:
    label = quote(f"{issuer}:{account}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}"


def new_recovery_codes(n: int = 10) -> list[str]:
    """Single-use codes, e.g. `7K3F-9QMD`; 40 bits of entropy each."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return [
        "".join(secrets.choice(alphabet) for _ in range(4)) + "-" + "".join(secrets.choice(alphabet) for _ in range(4))
        for _ in range(n)
    ]


def hash_recovery(code: str) -> str:
    return hashlib.sha256(code.strip().upper().replace(" ", "").encode()).hexdigest()
