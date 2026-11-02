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


@command("doctor", "check this installation's configuration and surroundings before (or after) going live")
def cmd_doctor(_args) -> int:
    import shutil
    import socket
    import sqlite3
    from zoneinfo import ZoneInfo

    import httpx

    from app.core.config import get_settings

    st = get_settings()
    results: list[tuple[str, str, str]] = []  # (level, what, detail)  level: ok | warn | fail

    def add(level, what, detail=""):
        results.append((level, what, detail))

    for p in st.production_problems():
        add("fail", "Configuration", p)
    add(
        "ok" if st.is_production else "warn",
        "Environment",
        f"APP_ENV={st.app_env}" + ("" if st.is_production else " (not production)"),
    )
    try:
        st.data_dir.mkdir(parents=True, exist_ok=True)
        probe = st.data_dir / ".doctor"
        probe.write_text("x")
        probe.unlink()
        free = shutil.disk_usage(st.data_dir).free / 1024**3
        add(
            "ok" if free >= 10 else ("warn" if free >= 3 else "fail"),
            "Disk space",
            f"{free:.1f} GB free in {st.data_dir}",
        )
    except OSError as exc:
        add("fail", "Data folder", f"not writable: {exc}")
    dbpath = st.resolved_database_url.removeprefix("sqlite:///")
    if st.resolved_database_url.startswith("sqlite:///") and Path(dbpath).exists():
        try:
            c = sqlite3.connect(dbpath)
            r = c.execute("PRAGMA quick_check").fetchone()[0]
            c.close()
            add("ok" if r == "ok" else "fail", "Database", "integrity check passed" if r == "ok" else r)
        except sqlite3.Error as exc:
            add("fail", "Database", str(exc))
    try:
        ZoneInfo(st.timezone)
        add("ok", "Time zone", st.timezone)
    except Exception:
        add("fail", "Time zone", f"APP_TIMEZONE={st.timezone} is not a valid time zone name")
    add(
        "ok" if st.cookie_secure else ("fail" if st.is_production and not st.allow_insecure_http else "warn"),
        "HTTPS cookies",
        "COOKIE_SECURE is on" if st.cookie_secure else "COOKIE_SECURE is off",
    )
    add(
        "ok" if st.data_encryption_key else "warn",
        "Encrypted uploads",
        "DATA_ENCRYPTION_KEY is set" if st.data_encryption_key else "uploads are stored unencrypted",
    )
    add(
        "ok" if st.backup_encryption_key else ("fail" if st.is_production else "warn"),
        "Encrypted backups",
        "BACKUP_ENCRYPTION_KEY is set" if st.backup_encryption_key else "BACKUP_ENCRYPTION_KEY is not set",
    )
    add(
        "ok" if st.encryption_at_rest_attested else "warn",
        "Disk encryption",
        "recorded as encrypted"
        if st.encryption_at_rest_attested
        else "not recorded; encrypt the data volume and set ENCRYPTION_AT_REST_ATTESTED=true",
    )
    db = SessionLocal()
    try:
        url = runtime_config.load(db).llm.base_url
    except Exception:
        url = None
        add("warn", "AI model server", "not checked: the database has not been set up yet")
    finally:
        db.close()
    if url:
        try:
            httpx.get(url, timeout=4)
            add("ok", "AI model server", f"reachable at {url}")
        except Exception:
            add(
                "warn",
                "AI model server",
                f"cannot reach {url}. The app runs, but AI features will not until it is reachable.",
            )
    if st.clamav_host:
        try:
            with socket.create_connection((st.clamav_host, st.clamav_port), timeout=3):
                add("ok", "Virus scanner", f"{st.clamav_host}:{st.clamav_port}")
        except OSError:
            add(
                "fail" if st.clamav_fail_closed else "warn",
                "Virus scanner",
                f"cannot reach {st.clamav_host}:{st.clamav_port}",
            )
    mark = {"ok": "  OK ", "warn": " WARN", "fail": " FAIL"}
    for level, what, detail in results:
        print(f"{mark[level]}  {what}: {detail}")
    failed = sum(1 for r in results if r[0] == "fail")
    print(f"\n{failed} blocking problem(s)." if failed else "\nNo blocking problems.")
    return 1 if failed else 0


@command("clinical-selftest", "run the clinical test cases against the prescription safety rules")
def cmd_clinical_selftest(_args) -> int:
    from app.clinical import testbank

    r = testbank.run_all()
    for c in r["cases"]:
        print(f"  {'PASS' if c['ok'] else 'FAIL'}  {c['title']}")
        for p in c["problems"]:
            print(f"        {p}")
    print(f"\n{r['passed']} of {r['total']} passed.")
    return 0 if r["ok"] else 1


@command(
    "eval",
    "measure extraction, retrieval and answer quality against known answers",
    (("--suite",), {"default": "", "help": "comma separated: extraction,retrieval,abstention,grounding"}),
)
def cmd_eval(args) -> int:
    import asyncio

    from app.evals import runner

    report = asyncio.run(runner.run([s.strip() for s in args.suite.split(",") if s.strip()] or None))
    print("Models:", ", ".join(f"{k}={v}" for k, v in report["models"].items() if v))
    for r in report["suites"]:
        if r["status"] != "ok":
            print(f"  {r['status'].upper():7} {r['suite']}: {r.get('reason', '')}")
            continue
        keys = {
            k: v
            for k, v in r.items()
            if k
            in (
                "recall",
                "precision",
                "recall_at_5",
                "top1",
                "rate",
                "with_citations",
                "no_invented_citations",
                "values_expected",
                "values_found",
                "questions",
                "answered",
            )
        }
        print(f"  {'PASS' if r['pass'] else 'BELOW TARGET':12} {r['suite']:11} {keys}   target: {r['target']}")
    print("\nSaved to the data/evals folder.")
    return 0 if report["ok"] else 1
