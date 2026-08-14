"""Small cross-router helpers — kept here instead of duplicated in every router module
that needs to resolve a patient by ID (patients.py, reports.py, and future encounter-
scoped routers)."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.api.deps import DbDep
from app.models.patient import Patient
from app.services import patients as patient_service


def get_patient_or_404(db: DbDep, patient_id: str) -> Patient:
    patient = patient_service.get_patient(db, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient
