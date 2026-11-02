"""Password policy: length plus a blocklist, as recommended by NIST SP 800-63B — not arbitrary
composition rules. Applies to every new password a person chooses; it does not touch stored hashes."""

from __future__ import annotations

import re

MIN_LENGTH_FLOOR = 10

# The passwords people actually pick, plus the product's own examples and defaults.
_COMMON = {
    "password",
    "password1",
    "password12",
    "password123",
    "password1234",
    "passw0rd",
    "p@ssw0rd",
    "p@ssword",
    "123456789012",
    "1234567890123",
    "12345678901234",
    "qwertyuiop12",
    "qwertyuiopas",
    "qwerty123456",
    "asdfghjkl123",
    "letmein12345",
    "welcome12345",
    "admin1234567",
    "administrator",
    "admin@12345",
    "admin@2026",
    "clinic@2026",
    "desk@2026",
    "audit@2026",
    "changeme1234",
    "change-me-in-production",
    "iloveyou1234",
    "abcdefghijkl",
    "abc123456789",
    "000000000000",
    "111111111111",
    "doctor123456",
    "hospital1234",
    "clinic123456",
    "gmsclinical",
    "gmsclinicalai",
    "lifecaremedico",
    "monkey123456",
    "dragon123456",
    "football1234",
    "sunshine1234",
}


def validate(password: str, *, min_length: int = 12, email: str | None = None, name: str | None = None) -> list[str]:
    """Returns the list of problems (empty = acceptable)."""
    min_length = max(min_length, MIN_LENGTH_FLOOR)
    problems: list[str] = []
    if len(password) < min_length:
        problems.append(f"Use at least {min_length} characters.")
    if len(password) > 200:
        problems.append("Use at most 200 characters.")
    low = password.lower()
    squashed = re.sub(r"[^a-z0-9]", "", low)
    if low in _COMMON or squashed in _COMMON or any(c in low for c in ("password", "qwerty", "letmein")):
        problems.append("That password is too common or guessable.")
    if len(set(password)) < 5:
        problems.append("Use more than a few repeated characters.")
    if _sequence(low):
        problems.append("Avoid simple sequences such as 123456 or abcdef.")
    if email:
        local = email.split("@")[0].lower()
        if len(local) >= 4 and local in low:
            problems.append("Do not include your email name.")
    if name:
        for part in re.split(r"\W+", name.lower()):
            if len(part) >= 4 and part in low:
                problems.append("Do not include your own name.")
                break
    return problems


def _sequence(s: str) -> bool:
    run = 1
    for a, b in zip(s, s[1:], strict=False):
        run = run + 1 if (ord(b) - ord(a) == 1 and a.isalnum() and b.isalnum()) else 1
        if run >= 6:
            return True
    return False


def check(password: str, **kw) -> None:
    from app.core.errors import AppError

    problems = validate(password, **kw)
    if problems:
        raise AppError(" ".join(problems), status_code=422, code="weak_password")
