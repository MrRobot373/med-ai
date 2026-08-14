#!/usr/bin/env python
"""Seed demo accounts (admin / doctor / viewer) — spec §17: "Create demo accounts
through a seed script, but credentials must be configurable" and "Never put production
passwords directly in source code."

Reads SEED_<ROLE>_EMAIL / SEED_<ROLE>_PASSWORD from the environment (see .env.example).
Any password left unset is generated randomly, printed once, and saved to
data/sqlite/.demo_credentials.txt (gitignored) so a presenter can find it again without
it ever having been hardcoded anywhere in source.

Idempotent: an account that already exists is left untouched (including its password) —
re-running this script is safe and won't lock out a presenter who already changed a
demo password by hand.

Usage:
    python scripts/seed_demo.py
"""

from __future__ import annotations

import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.config.settings import PROJECT_ROOT  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402

DEMO_ACCOUNTS = [
    # (env prefix, role, default email, display name)
    ("SEED_ADMIN", UserRole.ADMIN, "admin@gms.local", "Dr. Admin"),
    ("SEED_DOCTOR", UserRole.DOCTOR, "doctor@gms.local", "Dr. Demo"),
    ("SEED_VIEWER", UserRole.VIEWER, "viewer@gms.local", "Demo Viewer"),
]

CREDENTIALS_FILE = PROJECT_ROOT / "data" / "sqlite" / ".demo_credentials.txt"


def main() -> int:
    db = SessionLocal()
    created: list[tuple[str, str, str]] = []  # (email, password, role)

    try:
        for env_prefix, role, default_email, display_name in DEMO_ACCOUNTS:
            email = os.environ.get(f"{env_prefix}_EMAIL", default_email).strip().lower()

            existing = db.scalar(select(User).where(User.email == email))
            if existing is not None:
                print(f"[skip] {email} ({role.value}) already exists - left untouched")
                continue

            password = os.environ.get(f"{env_prefix}_PASSWORD") or secrets.token_urlsafe(12)
            db.add(
                User(
                    email=email,
                    display_name=display_name,
                    password_hash=hash_password(password),
                    role=role,
                    active=True,
                )
            )
            created.append((email, password, role.value))
            print(f"[created] {email} ({role.value})")
    except OperationalError as exc:
        print(f"Database error - have you run migrations yet? (alembic upgrade head)\n{exc}")
        return 1
    else:
        db.commit()
    finally:
        db.close()

    if created:
        _write_credentials_file(created)
        print(f"\nCredentials for newly created accounts saved to: {CREDENTIALS_FILE}")
    else:
        print("\nNo new accounts created.")

    return 0


def _write_credentials_file(created: list[tuple[str, str, str]]) -> None:
    CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "SYNTHETIC DEMO CREDENTIALS — NOT FOR PRODUCTION USE",
        f"Generated {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    for email, password, role in created:
        lines.append(f"{role:8} {email:30} {password}")
    CREDENTIALS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
