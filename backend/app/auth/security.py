"""Password and session-token cryptography — spec §17.

Two distinct secrets are hashed here, never stored in plaintext:
  1. The user's login password (Argon2id, via argon2-cffi).
  2. The random session token issued at login. Only its hash lives in `sessions.
     token_hash`; the raw token exists solely in the client's HttpOnly cookie, so a
     database read/leak alone can never be replayed as a valid session.
"""

from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_password_hasher = PasswordHasher()

SESSION_TOKEN_BYTES = 32  # 256 bits of entropy


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        _password_hasher.verify(password_hash, plain_password)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def generate_session_token() -> str:
    """A high-entropy, URL-safe random token — this is what goes in the cookie."""
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def hash_session_token(raw_token: str) -> str:
    """SHA-256 is sufficient (not Argon2) here: the input is already 256 bits of
    uniform random entropy, not a low-entropy human password, so there's nothing for
    a slow KDF to protect against beyond what a fast, collision-resistant hash gives."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
