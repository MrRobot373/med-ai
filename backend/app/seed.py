"""Loads the clinic's starting data.

    python -m app.seed demo          # staff accounts, the 15 patient files, knowledge packs
    python -m app.seed knowledge     # (re)load knowledge packs only
    python -m app.seed today         # put today's expected patients on the day list again
    python -m app.seed reprocess     # retry documents that failed (e.g. AI was offline)
    python -m app.seed use-mock-ai http://127.0.0.1:9100/v1   # point all AI roles at the mock server

Patients come from patient-files/ (one folder per patient with a registration.json and
their reports, images and prescriptions — see patient-files/README.md). Everyone in them
is fictional; the medical images are from openly licensed datasets.

With the embedded vector store, run seeding while the API server is stopped (the
embedded store is single-process).
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from sqlalchemy import select

from app.core.config import PROJECT_ROOT, get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db import SessionLocal
from app.models import (
    Allergy,
    Appointment,
    Condition,
    Document,
    Encounter,
    Medication,
    Order,
    Patient,
    Prescription,
    PrescriptionItem,
    User,
)
from app.services import documents

logger = get_logger("seed")
PACKS = PROJECT_ROOT / "knowledge-packs"
PATIENT_FILES = PROJECT_ROOT / "patient-files"

STAFF = [
    # email, name, title, specialty, role, password
    ("ananya.rao@gmsclinic.local", "Dr. Ananya Rao", "Dr.", "Internal Medicine", "clinician", "Clinic@2026"),
    ("meera.pillai@gmsclinic.local", "Meera Pillai", None, "Front desk", "front_desk", "Desk@2026"),
    ("rahul.menon@gmsclinic.local", "Rahul Menon", None, "Quality & audit", "viewer", "Audit@2026"),
]
CLINICIAN_EMAIL = STAFF[0][0]
MIME = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".dcm": "application/dicom",
}


def seed_users(db) -> User:
    for email, name, title, spec, role, pw in STAFF:
        if not db.scalars(select(User).where(User.email == email)).first():
            db.add(
                User(
                    email=email, full_name=name, title=title, specialty=spec, role=role, password_hash=hash_password(pw)
                )
            )
    db.commit()
    return (
        db.scalars(select(User).where(User.email == CLINICIAN_EMAIL)).first()
        or db.scalars(select(User).where(User.role == "admin")).first()
    )


def _d(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


def _at(d: date, hh: int = 10, mm: int = 0) -> datetime:
    return datetime.combine(d, time(hh, mm), tzinfo=UTC)


def _generic(fm, name: str) -> str | None:
    return "+".join(fm.resolve(name).generic_ids) or None


def patient_folders(root: Path = PATIENT_FILES) -> list[Path]:
    return sorted(p for p in root.glob("*/registration.json")) if root.exists() else []


def seed_patients(db, clinician: User, root: Path = PATIENT_FILES) -> list[str]:
    """Creates each patient's chart from their folder and queues their documents."""
    from app.formulary.catalog import load

    fm = load("IN")
    today = date.today()
    created: list[str] = []
    for reg_path in patient_folders(root):
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
        if db.scalars(select(Patient).where(Patient.mrn == reg["uhid"])).first():
            continue
        p = Patient(
            mrn=reg["uhid"],
            first_name=reg["first_name"],
            last_name=reg["last_name"],
            date_of_birth=_d(reg["date_of_birth"]),
            sex=reg["sex"],
            phone=reg.get("phone"),
            email=reg.get("email"),
            address=reg.get("address"),
            blood_group=reg.get("blood_group"),
            tags=reg.get("tags", []),
            notes=reg.get("summary"),
            synthetic=True,
            created_by=clinician.id,
        )
        db.add(p)
        db.flush()
        for c in reg["conditions"]:
            db.add(
                Condition(
                    patient_id=p.id,
                    name=c["name"],
                    code=c.get("code"),
                    status=c.get("status", "active"),
                    onset_date=_d(c.get("since")),
                )
            )
        for a in reg["allergies"]:
            db.add(
                Allergy(
                    patient_id=p.id,
                    substance=a["substance"],
                    reaction=a.get("reaction"),
                    severity=a.get("severity", "unknown"),
                )
            )
        for m in reg["medications"]:
            db.add(
                Medication(
                    patient_id=p.id,
                    name=m["name"],
                    generic=_generic(fm, m["name"]),
                    dose=m.get("dose"),
                    route="oral",
                    frequency=m.get("frequency"),
                    indication=m.get("indication"),
                    start_date=_d(m.get("since")),
                    status="active",
                )
            )
        encounters: list[Encounter] = []
        for v in reg["visits"]:
            when = _at(_d(v["date"]), 10, 30)
            enc = Encounter(
                patient_id=p.id,
                type="outpatient",
                status="completed",
                started_at=when,
                ended_at=when + timedelta(minutes=15),
                reason=v.get("reason"),
                history=v.get("history"),
                examination=v.get("examination"),
                vitals=v.get("vitals") or {},
                assessment=v.get("assessment"),
                plan=v.get("plan"),
                clinician_id=clinician.id,
                diagnoses=[{"name": d, "code": None} for d in v.get("diagnoses", [])],
            )
            db.add(enc)
            db.flush()
            encounters.append(enc)
            rx = v.get("prescription")
            if not rx:
                continue
            visit_day = _d(v["date"])
            pres = Prescription(
                patient_id=p.id,
                encounter_id=enc.id,
                clinician_id=clinician.id,
                status="final",
                diagnosis="; ".join(v.get("diagnoses", [])) or None,
                advice=rx.get("advice"),
                follow_up_date=visit_day + timedelta(days=rx["follow_up_days"]) if rx.get("follow_up_days") else None,
                finalized_at=when + timedelta(minutes=14),
            )
            db.add(pres)
            db.flush()
            for pos, it in enumerate(rx["items"]):
                generic = _generic(fm, it["drug"])
                pres.items.append(
                    PrescriptionItem(
                        position=pos,
                        drug=it["drug"],
                        generic=generic,
                        dose=it["dose"],
                        frequency=it["frequency"],
                        duration_days=it.get("duration_days"),
                        instructions=it.get("instructions"),
                        checks=[],
                    )
                )
                end = None if rx.get("long_term") else visit_day + timedelta(days=it.get("duration_days") or 0)
                db.add(
                    Medication(
                        patient_id=p.id,
                        encounter_id=enc.id,
                        name=it["drug"],
                        generic=generic,
                        dose=it["dose"],
                        route="oral",
                        frequency=it["frequency"],
                        indication=pres.diagnosis,
                        start_date=visit_day,
                        end_date=end,
                        status="active" if end is None or end >= today else "stopped",
                        notes=it.get("instructions"),
                        source="prescription",
                        prescription_id=pres.id,
                    )
                )
        for o in reg["orders"]:
            visit = o.get("visit")
            db.add(
                Order(
                    patient_id=p.id,
                    encounter_id=encounters[visit].id if visit is not None and visit < len(encounters) else None,
                    clinician_id=clinician.id,
                    test_name=o["test"],
                    category=o["category"],
                    reason=o.get("reason"),
                    ordered_at=_at(_d(o["date"]), 11, 0),
                )
            )
        db.commit()
        folder = reg_path.parent
        for meta in reg["documents"]:
            if not meta.get("load", True):
                continue
            path = folder / meta["file"]
            try:
                doc = documents.create(
                    db,
                    clinician,
                    data=path.read_bytes(),
                    filename=path.name,
                    declared_mime=MIME.get(path.suffix.lower()),
                    scope="patient",
                    patient=p,
                    title=meta["title"],
                    kind=meta.get("kind"),
                    document_date=_d(meta.get("date")),
                )
                created.append(doc.id)
            except AppError as exc:
                logger.warning("Skipping %s: %s", path, exc.message)
        logger.info(
            "%s — %s: chart created, %d documents queued",
            p.mrn,
            p.full_name,
            sum(1 for m in reg["documents"] if m.get("load", True)),
        )
    return created


def seed_today(db, clinician: User, root: Path = PATIENT_FILES) -> int:
    """Puts patients whose registration names a visit today on today's list."""
    added = 0
    today = date.today()
    for reg_path in patient_folders(root):
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
        slot = reg.get("today")
        p = db.scalars(select(Patient).where(Patient.mrn == reg["uhid"])).first()
        if not slot or p is None:
            continue
        if db.scalar(select(Appointment).where(Appointment.patient_id == p.id, Appointment.day == today)):
            continue
        db.add(
            Appointment(
                patient_id=p.id,
                day=today,
                time=slot["time"],
                reason=slot["reason"],
                status=slot.get("status", "expected"),
                clinician_id=clinician.id,
                created_by=clinician.id,
            )
        )
        added += 1
    db.commit()
    return added


def seed_knowledge(db, admin: User) -> list[str]:
    created: list[str] = []
    if not PACKS.exists():
        return created
    for path in sorted(PACKS.glob("*/*")):
        if path.is_dir() or path.name.lower() == "readme.md":
            continue
        domain = path.parent.name.replace("-", "_")
        title = path.stem.replace("-", " ").replace("_", " ").title()
        if path.suffix == ".md":
            first = path.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
            title = first or title
        try:
            doc = documents.create(
                db,
                admin,
                data=path.read_bytes(),
                filename=path.name,
                declared_mime=None,
                scope="knowledge",
                title=title,
                kind="guideline",
                domain=domain,
                source_org="GMS clinical knowledge pack",
                version="1.0",
            )
            created.append(doc.id)
        except AppError as exc:
            logger.info("Skipping %s: %s", path.name, exc.message)
    return created


async def _process_all(ids: list[str]) -> None:
    for i, doc_id in enumerate(ids, start=1):
        await documents.process(doc_id)
        db = SessionLocal()
        d = db.get(Document, doc_id)
        logger.info("[%d/%d] %s → %s%s", i, len(ids), d.title, d.status, f" ({d.error})" if d.error else "")
        db.close()


def main(argv: list[str]) -> int:
    configure_logging("INFO")
    from app.main import bootstrap, run_migrations

    get_settings().uploads_dir.mkdir(parents=True, exist_ok=True)
    run_migrations()
    bootstrap()
    cmd = argv[1] if len(argv) > 1 else "demo"
    db = SessionLocal()
    try:
        admin = db.scalars(select(User).where(User.role == "admin")).first()
        ids: list[str] = []
        if cmd == "demo":
            clinician = seed_users(db)
            ids += seed_knowledge(db, admin)
            ids += seed_patients(db, clinician)
            seed_today(db, clinician)
        elif cmd == "today":
            print(f"Added {seed_today(db, seed_users(db))} patients to today's list")
            return 0
        elif cmd == "knowledge":
            ids += seed_knowledge(db, admin)
        elif cmd == "use-mock-ai":
            from app.services import runtime_config

            url = argv[2] if len(argv) > 2 else "http://127.0.0.1:9100/v1"
            cfg = runtime_config.load(db)
            cfg = runtime_config.apply_section_update(
                cfg, "llm", {"provider": "openai", "base_url": url, "model": "mock-clinical-llm"}
            )
            cfg = runtime_config.apply_section_update(cfg, "vision", {"use_main_llm": True})
            cfg = runtime_config.apply_section_update(cfg, "clinical", {"use_main_llm": True})
            cfg = runtime_config.apply_section_update(
                cfg, "embeddings", {"provider": "openai", "base_url": url, "model": "mock-embed"}
            )
            cfg = runtime_config.apply_section_update(
                cfg, "reranker", {"provider": "remote", "base_url": url, "model": "mock-rerank"}
            )
            runtime_config.save(db, cfg)
            print(f"All AI roles now use the mock server at {url}")
            return 0
        elif cmd == "reprocess":
            ids = [d.id for d in db.scalars(select(Document).where(Document.status.in_(["failed", "processing"])))]
        else:
            print(__doc__)
            return 2
    finally:
        db.close()
    logger.info("Processing %d documents…", len(ids))
    asyncio.run(_process_all(ids))
    from app.rag.vector_store import reset_clients

    reset_clients()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
