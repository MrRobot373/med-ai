"""Builds the printable view of a prescription (and the letterhead sheet) from the database."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.clinical.context import age
from app.core.config import get_settings
from app.models import Branch, Encounter, Patient, Prescription, User
from app.services import pdfgen, runtime_config
from app.services.runtime_config import PrintConfig

SEX = {"male": "Male", "female": "Female", "other": "Other", "unknown": ""}


def local_date(dt: datetime | None = None) -> date:
    tz = ZoneInfo(get_settings().timezone)
    return (dt or datetime.now(UTC)).astimezone(tz).date()


def fmt_date(d: date, long: bool = False) -> str:
    return d.strftime("%A, %d %B %Y") if long else d.strftime("%d %b %Y")


def branch_dict(b: Branch | None) -> dict:
    if b is None:
        return {}
    return {
        "name": b.name,
        "address": b.address,
        "phone": b.phone,
        "email": b.email,
        "registration": b.registration,
        "footer_text": b.footer_text,
    }


def doctor_dict(u: User | None) -> dict:
    if u is None:
        return {}
    name = f"{u.title} {u.full_name}".strip() if u.title and not u.full_name.startswith(u.title) else u.full_name
    return {
        "name": name,
        "email": u.email,
        "phone": u.phone,
        "qualifications": u.qualifications,
        "registration_no": u.registration_no,
        "registration_council": u.registration_council,
        "signature_data_url": u.signature_data_url,
    }


def sheet_for(db: Session, branch: Branch | None, doctor: User | None, cfg: PrintConfig | None = None) -> pdfgen.Sheet:
    rc = runtime_config.load(db)
    return pdfgen.make_sheet(
        cfg or rc.print,
        organization=rc.branding.organization,
        tagline=rc.branding.tagline,
        logo_data_url=rc.branding.logo_data_url,
        branch=branch_dict(branch),
        doctor=doctor_dict(doctor),
    )


def verify_sig(rx_id: str) -> str:
    return hmac.new(get_settings().secret_key.encode(), f"rx:{rx_id}".encode(), hashlib.sha256).hexdigest()[:16]


def verify_code(rx_id: str, cfg: PrintConfig) -> str:
    sig = verify_sig(rx_id)
    base = cfg.public_base_url.rstrip("/")
    return f"{base}/verify/rx/{rx_id}?s={sig}" if base else f"GMSRX:{rx_id}:{sig}"


def prescription_view(db: Session, rx: Prescription, cfg: PrintConfig | None = None) -> dict:
    cfg = cfg or runtime_config.load(db).print
    p = db.get(Patient, rx.patient_id)
    enc = db.get(Encounter, rx.encounter_id) if rx.encounter_id else None
    when = rx.finalized_at or rx.created_at
    return {
        "id": rx.id,
        "patient": {
            "name": p.full_name,
            "mrn": p.mrn,
            "age": age(p.date_of_birth),
            "sex": SEX.get(p.sex, ""),
            "phone": p.phone,
        },
        "date": fmt_date(local_date(when)),
        "vitals": (enc.vitals if enc else None) or {},
        "complaint": enc.reason if enc else None,
        "diagnosis": rx.diagnosis,
        "advice": rx.advice,
        "follow_up": fmt_date(rx.follow_up_date, long=True) if rx.follow_up_date else None,
        "items": [
            {
                "drug": i.drug,
                "generic": i.generic,
                "dose": i.dose,
                "frequency": i.frequency,
                "duration_days": i.duration_days,
                "instructions": i.instructions,
            }
            for i in rx.items
        ],
        "verify_code": verify_code(rx.id, cfg) if rx.status == "final" else None,
    }


def sample_view(cfg: PrintConfig) -> dict:
    return {
        "id": "SAMPLE0000000000",
        "patient": {
            "name": "Sample Patient",
            "mrn": "LCM-00000",
            "age": 45,
            "sex": "Female",
            "phone": "+91 98765 43210",
        },
        "date": fmt_date(local_date()),
        "vitals": {"bp": "128/82", "hr": 76, "temp_f": 98.4, "spo2": 98, "weight_kg": 62},
        "complaint": "Cough and cold for 4 days",
        "diagnosis": "Acute upper respiratory infection",
        "advice": "Plenty of fluids and rest. Steam inhalation twice a day.",
        "follow_up": fmt_date(local_date(), long=True),
        "items": [
            {
                "drug": "Dolo 650",
                "generic": "paracetamol",
                "dose": "1 tab",
                "frequency": "TDS",
                "duration_days": 3,
                "instructions": "After food",
            },
            {
                "drug": "Pan-D",
                "generic": "pantoprazole+domperidone",
                "dose": "1 cap",
                "frequency": "OD",
                "duration_days": 5,
                "instructions": "Before breakfast",
            },
        ],
        "verify_code": verify_code("SAMPLE0000000000", cfg),
    }
