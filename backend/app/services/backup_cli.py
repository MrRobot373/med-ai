"""Command-line side of backup, restore, status and the licence (registered into app.cli)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.cli import command
from app.core.errors import AppError
from app.db import SessionLocal
from app.services import audit, backup, licensing, runtime_config


def _fail(exc: Exception) -> int:
    print(f"Error: {getattr(exc, 'message', None) or exc}", file=sys.stderr)
    return 1


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


@command(
    "backup", "take a backup now", (("--no-vectors",), {"action": "store_true", "help": "leave out the search index"})
)
def cmd_backup(args) -> int:
    db = SessionLocal()
    try:
        cfg = runtime_config.load(db).backup
        r = backup.run_and_record(
            db, include_vectors=not args.no_vectors and cfg.include_vectors, keep=cfg.keep, by="cli"
        )
    except AppError as exc:
        return _fail(exc)
    finally:
        db.close()
    m = r["manifest"]
    print(
        f"Backup written: {backup.directory() / r['file']}\n  {_human(r['size'])}, {'encrypted' if r['encrypted'] else 'NOT encrypted'}, "
        f"{m['patients']} patients, {len(m['files'])} files, schema {m['schema']}"
    )
    return 0


@command("backup-list", "list the backups on this server")
def cmd_backup_list(_args) -> int:
    rows = backup.listing()
    if not rows:
        print(f"No backups in {backup.directory()}")
    for b in rows:
        print(
            f"{b['file']}  {_human(b['size'])}  {b['created_at'][:19]}Z  {'encrypted' if b['encrypted'] else 'plain'}"
        )
    return 0


@command(
    "backup-verify",
    "open a backup in a scratch folder and check it (changes nothing)",
    (("file",), {"nargs": "?", "help": "file name or path; default: the newest"}),
)
def cmd_backup_verify(args) -> int:
    target = args.file or (backup.listing()[0]["file"] if backup.listing() else None)
    if not target:
        print("There are no backups to check.", file=sys.stderr)
        return 1
    db = SessionLocal()
    try:
        r = (
            backup.verify_and_record(db, target)
            if "/" not in target and not Path(target).is_absolute()
            else backup.verify(target)
        )
    except AppError as exc:
        return _fail(exc)
    finally:
        db.close()
    print(
        f"OK — {r['file']} from {r['created_at'][:19]}: {r['patients']} patients, {r['documents']} documents, {r['files']} files, schema {r['schema']}."
    )
    return 0


@command(
    "restore",
    "replace ALL current data with a backup (stop the server first)",
    (("file",), {"help": "file name in the backup folder, or a full path"}),
    (("--yes",), {"action": "store_true", "help": "confirm"}),
)
def cmd_restore(args) -> int:
    file = Path(args.file) if ("/" in args.file or Path(args.file).is_absolute()) else backup.path_of(args.file)
    if not file.is_file():
        print(f"No such file: {file}", file=sys.stderr)
        return 1
    if not args.yes:
        print(
            f"This will REPLACE the current patients, files and settings with {file.name}.\n"
            "The server must be stopped. Current data is moved aside, not deleted.\nRun again with --yes to go ahead."
        )
        return 2
    try:
        r = backup.restore(file)
        from app.main import bootstrap, run_migrations

        run_migrations()
        bootstrap()
    except AppError as exc:
        return _fail(exc)
    db = SessionLocal()
    try:
        audit.record(
            db,
            None,
            "backup.restore",
            f"Restored the installation from {file.name}",
            details={"created_at": r["created_at"], "patients": r["patients"]},
        )
    finally:
        db.close()
    print(
        f"Restored from {file.name} (made {r['created_at'][:19]}Z, {r['patients']} patients).\n"
        f"The previous data is in {r['old_data_moved_to']} — delete it once you are satisfied.\n"
        "Start the server. If the search index was not in the backup, run a re-index in Settings."
    )
    return 0


@command("status", "one-screen health summary for the operator")
def cmd_status(_args) -> int:
    db = SessionLocal()
    try:
        lic = licensing.state(db)
        b = backup.status(db)
        chain = audit.verify_chain(db)
        print(f"Licence:  {lic['mode']} — {lic['message']}  (install id {lic['install_id']})")
        print(
            f"Usage:    {lic['usage']['clinicians']} clinicians, {lic['usage']['staff']} staff, {lic['usage']['branches']} branches, {lic['usage']['patients']} patients"
        )
        print(
            f"Backup:   last {b.get('last_ok_at', 'NEVER')}  ({'encrypted' if b['encrypted'] else 'NOT encrypted'}); last verified {b.get('last_verify_at', 'NEVER')}"
        )
        print(f"Audit:    {chain.message}")
    finally:
        db.close()
    return 0


@command("licence", "show the installed licence and this server's install id")
def cmd_licence(_args) -> int:
    db = SessionLocal()
    try:
        print(json.dumps(licensing.state(db), indent=2, default=str))
    finally:
        db.close()
    return 0
