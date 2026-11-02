"""Public check that a printed prescription is genuine. Reveals nothing about the patient."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException, Request

from app.api.deps import DB, client_ip
from app.core.config import get_settings
from app.models import Prescription, User
from app.services import printing, runtime_config
from app.services.rate_limit import login_limiter

router = APIRouter(prefix="/api/verify", tags=["verification"])


@router.get("/rx/{rx_id}")
def verify_prescription(rx_id: str, s: str, request: Request, db: DB):
    st = get_settings()
    if not login_limiter.hit(f"verify|{client_ip(request)}", 60, 600):
        raise HTTPException(429, "Too many checks. Please wait a few minutes.")
    rx = db.get(Prescription, rx_id)
    if rx is None or not hmac.compare_digest(s, printing.verify_sig(rx_id)) or rx.status == "draft":
        raise HTTPException(404, "This prescription could not be verified.")
    doctor = db.get(User, rx.clinician_id) if rx.clinician_id else None
    org = runtime_config.load(db).branding.organization
    _ = st
    return {
        "valid": rx.status == "final",
        "status": rx.status,
        "issued_on": (rx.finalized_at or rx.created_at).date().isoformat(),
        "organisation": org,
        "doctor": doctor.full_name if doctor else None,
        "registration_no": doctor.registration_no if doctor else None,
        "medicines": len(rx.items),
    }
