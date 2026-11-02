"""Certificates, referral letters and visit summaries."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, ClinicalUser, WriteUser
from app.core.config import get_settings
from app.models import Branch, Letter, Patient, User
from app.services import audit, letters, pdfgen, printing, runtime_config
from app.services import branches as branch_svc

router = APIRouter(prefix="/api", tags=["letters"])


class LetterIn(BaseModel):
    kind: str
    encounter_id: str | None = None


class LetterUpdate(BaseModel):
    fields: dict | None = None
    body: str | None = Field(None, max_length=6000)


class VoidIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


def _letter(db, letter_id: str) -> Letter:
    row = db.get(Letter, letter_id)
    if row is None:
        raise HTTPException(404, "Letter not found")
    return row


@router.get("/patients/{patient_id}/letters")
def list_letters(patient_id: str, db: DB, _: ClinicalUser):
    rows = db.scalars(select(Letter).where(Letter.patient_id == patient_id).order_by(Letter.created_at.desc())).all()
    return [letters.out(r) for r in rows]


@router.post("/patients/{patient_id}/letters", status_code=201)
def create_letter(patient_id: str, body: LetterIn, db: DB, user: WriteUser):
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(404, "Patient not found")
    row = letters.create(db, body.kind, patient, user, body.encounter_id, branch_svc.active(db, user).id)
    audit.record(
        db,
        user,
        "letter.create",
        f"Started a {letters.KINDS[row.kind][0].lower()} for {patient.full_name}",
        entity_type="letter",
        entity_id=row.id,
        patient_id=patient.id,
    )
    return letters.out(row)


@router.get("/letters/{letter_id}")
def get_letter(letter_id: str, db: DB, _: ClinicalUser):
    return letters.out(_letter(db, letter_id))


@router.patch("/letters/{letter_id}")
def update_letter(letter_id: str, body: LetterUpdate, db: DB, user: WriteUser):
    return letters.out(letters.update(db, _letter(db, letter_id), body.fields, body.body))


@router.delete("/letters/{letter_id}", status_code=204)
def delete_draft(letter_id: str, db: DB, user: WriteUser):
    row = _letter(db, letter_id)
    if row.status != "draft":
        raise HTTPException(409, "An issued letter cannot be deleted. Void it instead.")
    db.delete(row)
    db.commit()


@router.post("/letters/{letter_id}/issue")
def issue_letter(letter_id: str, db: DB, user: WriteUser):
    row = _letter(db, letter_id)
    pcfg = runtime_config.load(db).print
    if (
        row.status == "draft"
        and pcfg.require_registration_no
        and get_settings().is_production
        and not user.registration_no
    ):
        raise HTTPException(422, "Add your medical registration number to your profile before issuing letters.")
    row.author_id = user.id  # the person who signs it is the one named on it
    letters.issue(db, row)
    audit.record(
        db,
        user,
        "letter.issue",
        f"Issued {row.number}",
        entity_type="letter",
        entity_id=row.id,
        patient_id=row.patient_id,
    )
    return letters.out(row)


@router.post("/letters/{letter_id}/void")
def void_letter(letter_id: str, body: VoidIn, db: DB, user: WriteUser):
    row = letters.void(db, _letter(db, letter_id), body.reason)
    audit.record(
        db,
        user,
        "letter.void",
        f"Voided {row.number}: {body.reason}",
        entity_type="letter",
        entity_id=row.id,
        patient_id=row.patient_id,
    )
    return letters.out(row)


@router.get("/letters/{letter_id}/pdf")
def letter_pdf(letter_id: str, db: DB, user: ClinicalUser, download: bool = False):
    row = _letter(db, letter_id)
    author = db.get(User, row.author_id) if row.author_id else None
    branch = db.get(Branch, row.branch_id) if row.branch_id else branch_svc.ensure_default(db)
    data = pdfgen.letter_pdf(letters.letter_view(db, row), printing.sheet_for(db, branch, author))
    patient = db.get(Patient, row.patient_id)
    audit.record(
        db,
        user,
        "letter.print",
        f"Opened {row.number or 'draft'} PDF",
        entity_type="letter",
        entity_id=row.id,
        patient_id=row.patient_id,
    )
    name = f"{(row.number or 'draft-' + row.id[:6]).lower()}-{patient.mrn if patient else 'patient'}.pdf"
    return Response(
        data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{"attachment" if download else "inline"}; filename="{name}"'},
    )
