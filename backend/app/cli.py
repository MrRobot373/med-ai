"""Operator commands for a running installation.

    python -m app.cli audit-verify                 check the audit log's tamper-evident chain
    python -m app.cli rotate-secret OLD NEW        re-encrypt stored secrets under a new APP_SECRET_KEY
    python -m app.cli encrypt-existing             encrypt uploads written before DATA_ENCRYPTION_KEY was set
    python -m app.cli unlock EMAIL                 clear a lockout
    python -m app.cli reset-mfa EMAIL              remove a person's two-step verification
    python -m app.cli create-admin EMAIL NAME      create an administrator (password asked for)

Other command groups (backup, restore, licence, status) are added by their modules below.
"""

from __future__ import annotations

import argparse
import copy
import getpass
import sys

from sqlalchemy import func, select

from app.core import passwords
from app.core.config import get_settings
from app.core.security import decrypt_secret, encrypt_secret, hash_password
from app.db import SessionLocal
from app.models import AppSetting, User
from app.services import audit
from app.services.runtime_config import SECRET_FIELDS


def cmd_audit_verify(_args) -> int:
    db = SessionLocal()
    try:
        r = audit.verify_chain(db)
    finally:
        db.close()
    print(r.message)
    if r.last_hash:
        print(f"Latest hash (keep a copy somewhere the database administrator cannot change): {r.last_hash}")
    if r.unchained:
        print(f"{r.unchained} older entries pre-date the chain.")
    return 0 if r.ok else 2


def cmd_rotate_secret(args) -> int:
    old, new = args.old, args.new
    if len(new) < 32:
        print("The new secret must be at least 32 characters.", file=sys.stderr)
        return 1
    db = SessionLocal()
    try:
        n = 0
        row = db.get(AppSetting, "runtime")
        if row is not None:
            data = copy.deepcopy(row.value)
            for section, field in SECRET_FIELDS:
                token = (data.get(section) or {}).get(field)
                if token:
                    plain = decrypt_secret(token, old)
                    if plain is None:
                        print(
                            f"Cannot decrypt {section}.{field} with the old secret — nothing was changed.",
                            file=sys.stderr,
                        )
                        return 1
                    data[section][field] = encrypt_secret(plain, new)
                    n += 1
            row.value = data
        for u in db.scalars(select(User).where(User.mfa_secret.is_not(None))):
            plain = decrypt_secret(u.mfa_secret, old)
            if plain is None:
                print(
                    f"Cannot decrypt the two-step secret of {u.email} with the old secret — nothing was changed.",
                    file=sys.stderr,
                )
                db.rollback()
                return 1
            u.mfa_secret = encrypt_secret(plain, new)
            n += 1
        db.commit()
    finally:
        db.close()
    print(
        f"Re-encrypted {n} secret(s). Now set APP_SECRET_KEY to the new value and restart. Everyone is signed out on restart only if you also clear sessions."
    )
    return 0


def cmd_encrypt_existing(_args) -> int:
    from app.core import storage

    done, skipped = storage.encrypt_existing()
    print(f"Encrypted {done} file(s); {skipped} were already encrypted.")
    return 0


def _find(db, email: str) -> User | None:
    return db.scalars(select(User).where(func.lower(User.email) == email.strip().lower())).first()


def cmd_unlock(args) -> int:
    db = SessionLocal()
    try:
        u = _find(db, args.email)
        if u is None:
            print("No such user.", file=sys.stderr)
            return 1
        u.failed_attempts, u.locked_until = 0, None
        db.commit()
        audit.record(
            db, None, "user.unlock", f"Unlocked {u.email} from the command line", entity_type="user", entity_id=u.id
        )
    finally:
        db.close()
    print("Unlocked.")
    return 0


def cmd_reset_mfa(args) -> int:
    db = SessionLocal()
    try:
        u = _find(db, args.email)
        if u is None:
            print("No such user.", file=sys.stderr)
            return 1
        u.mfa_enabled, u.mfa_secret, u.mfa_recovery, u.mfa_last_step = False, None, [], None
        for s in list(u.sessions):
            db.delete(s)
        db.commit()
        audit.record(
            db,
            None,
            "user.mfa_reset",
            f"Reset two-step verification for {u.email} from the command line",
            entity_type="user",
            entity_id=u.id,
        )
    finally:
        db.close()
    print("Two-step verification removed; the person must enrol again at next sign-in.")
    return 0


def cmd_create_admin(args) -> int:
    pw = args.password or getpass.getpass("Password: ")
    problems = passwords.validate(pw, email=args.email, name=args.name)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    db = SessionLocal()
    try:
        if _find(db, args.email):
            print("A user with that email already exists.", file=sys.stderr)
            return 1
        u = User(
            email=args.email.lower(),
            full_name=args.name,
            role="admin",
            password_hash=hash_password(pw),
            must_change_password=True,
        )
        db.add(u)
        db.commit()
        audit.record(
            db,
            None,
            "user.create",
            f"Created administrator {u.email} from the command line",
            entity_type="user",
            entity_id=u.id,
        )
    finally:
        db.close()
    print("Created. The person will be asked to choose a new password at first sign-in.")
    return 0


COMMANDS: dict[str, tuple] = {}


def command(name: str, help_: str, *arguments: tuple[tuple, dict]):
    def deco(fn):
        COMMANDS[name] = (fn, help_, arguments)
        return fn

    return deco


command("audit-verify", "check the audit log's tamper-evident chain")(cmd_audit_verify)
command("rotate-secret", "re-encrypt stored secrets under a new APP_SECRET_KEY", (("old",), {}), (("new",), {}))(
    cmd_rotate_secret
)
command("encrypt-existing", "encrypt uploads written before DATA_ENCRYPTION_KEY was set")(cmd_encrypt_existing)
command("unlock", "clear a lockout", (("email",), {}))(cmd_unlock)
command("reset-mfa", "remove a person's two-step verification", (("email",), {}))(cmd_reset_mfa)
command(
    "create-admin", "create an administrator", (("email",), {}), (("name",), {}), (("--password",), {"default": None})
)(cmd_create_admin)


def main(argv: list[str] | None = None) -> int:
    # Command groups register themselves on import.
    for mod in ("app.services.backup_cli", "app.services.licensing_cli"):
        try:
            __import__(mod)
        except ModuleNotFoundError:
            pass
    ap = argparse.ArgumentParser(
        prog="python -m app.cli", description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, (_fn, help_, arguments) in COMMANDS.items():
        sp = sub.add_parser(name, help=help_)
        for a, kw in arguments:
            sp.add_argument(*a, **kw)
    args = ap.parse_args(argv)
    get_settings().data_dir.mkdir(parents=True, exist_ok=True)
    return COMMANDS[args.cmd][0](args)


if __name__ == "__main__":
    sys.exit(main())
