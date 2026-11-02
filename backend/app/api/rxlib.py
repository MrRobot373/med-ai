"""Prescribing shortcuts: templates, favourite medicines, frequent medicines and repeating the last visit."""

from __future__ import annotations

from collections import Counter as Tally

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from app.api.care import RxItemIn
from app.api.deps import DB, ClinicalUser, WriteUser
from app.db import utcnow
from app.models import DrugFavourite, Prescription, PrescriptionItem, RxTemplate

router = APIRouter(prefix="/api/rx", tags=["prescribing shortcuts"])


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    diagnosis: str | None = Field(None, max_length=500)
    advice: str | None = Field(None, max_length=4000)
    items: list[RxItemIn] = Field(min_length=1, max_length=30)
    is_shared: bool = False


class TemplateFromRx(BaseModel):
    prescription_id: str
    name: str = Field(min_length=1, max_length=120)
    is_shared: bool = False


def _clean(i: dict) -> dict:
    keep = ("drug", "dose", "frequency", "duration_days", "route", "instructions", "strength_mg")
    return {k: i.get(k) for k in keep if i.get(k) not in (None, "")}


def _out(t: RxTemplate, me) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "diagnosis": t.diagnosis,
        "advice": t.advice,
        "items": t.items,
        "is_shared": t.is_shared,
        "mine": t.owner_id == me.id,
        "use_count": t.use_count,
        "last_used_at": t.last_used_at,
    }


def _mine_or_admin(t: RxTemplate | None, user) -> RxTemplate:
    if t is None:
        raise HTTPException(404, "Template not found")
    if t.owner_id != user.id and user.role != "admin":
        raise HTTPException(403, "Only the owner or an administrator can change this template.")
    return t


@router.get("/templates")
def list_templates(db: DB, user: ClinicalUser):
    rows = db.scalars(
        select(RxTemplate)
        .where(or_(RxTemplate.owner_id == user.id, RxTemplate.is_shared.is_(True)))
        .order_by(RxTemplate.use_count.desc(), RxTemplate.name)
    ).all()
    return [_out(t, user) for t in rows]


@router.post("/templates", status_code=201)
def create_template(body: TemplateIn, db: DB, user: WriteUser):
    if body.is_shared and user.role != "admin":
        raise HTTPException(403, "Only an administrator can share a template with the whole clinic.")
    t = RxTemplate(
        owner_id=user.id,
        name=body.name.strip(),
        diagnosis=body.diagnosis,
        advice=body.advice,
        items=[_clean(i.model_dump()) for i in body.items],
        is_shared=body.is_shared,
    )
    db.add(t)
    db.commit()
    return _out(t, user)


@router.post("/templates/from-prescription", status_code=201)
def template_from_prescription(body: TemplateFromRx, db: DB, user: WriteUser):
    rx = db.get(Prescription, body.prescription_id)
    if rx is None or not rx.items:
        raise HTTPException(404, "That prescription has no medicines to save.")
    if body.is_shared and user.role != "admin":
        raise HTTPException(403, "Only an administrator can share a template with the whole clinic.")
    items = [
        _clean(
            {
                "drug": i.drug,
                "dose": i.dose,
                "frequency": i.frequency,
                "duration_days": i.duration_days,
                "route": i.route,
                "instructions": i.instructions,
                "strength_mg": i.strength_mg,
            }
        )
        for i in rx.items
    ]
    t = RxTemplate(
        owner_id=user.id,
        name=body.name.strip(),
        diagnosis=rx.diagnosis,
        advice=rx.advice,
        items=items,
        is_shared=body.is_shared,
    )
    db.add(t)
    db.commit()
    return _out(t, user)


@router.put("/templates/{template_id}")
def update_template(template_id: str, body: TemplateIn, db: DB, user: WriteUser):
    t = _mine_or_admin(db.get(RxTemplate, template_id), user)
    if body.is_shared != t.is_shared and user.role != "admin":
        raise HTTPException(403, "Only an administrator can change who a template is shared with.")
    t.name, t.diagnosis, t.advice, t.is_shared = body.name.strip(), body.diagnosis, body.advice, body.is_shared
    t.items = [_clean(i.model_dump()) for i in body.items]
    db.commit()
    return _out(t, user)


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(template_id: str, db: DB, user: WriteUser):
    db.delete(_mine_or_admin(db.get(RxTemplate, template_id), user))
    db.commit()


@router.post("/templates/{template_id}/used", status_code=204)
def mark_used(template_id: str, db: DB, user: ClinicalUser):
    t = db.get(RxTemplate, template_id)
    if t and (t.owner_id == user.id or t.is_shared):
        t.use_count += 1
        t.last_used_at = utcnow()
        db.commit()


def _fav_out(f: DrugFavourite) -> dict:
    return {
        "id": f.id,
        "drug": f.drug,
        "dose": f.dose,
        "frequency": f.frequency,
        "duration_days": f.duration_days,
        "route": f.route,
        "instructions": f.instructions,
    }


@router.get("/favourites")
def list_favourites(db: DB, user: ClinicalUser):
    return [
        _fav_out(f)
        for f in db.scalars(select(DrugFavourite).where(DrugFavourite.user_id == user.id).order_by(DrugFavourite.drug))
    ]


@router.post("/favourites", status_code=201)
def add_favourite(body: RxItemIn, db: DB, user: WriteUser):
    drug = body.drug.strip()
    f = db.scalars(
        select(DrugFavourite).where(DrugFavourite.user_id == user.id, DrugFavourite.drug == drug)
    ).first() or DrugFavourite(user_id=user.id, drug=drug)
    f.dose, f.frequency, f.duration_days, f.route, f.instructions = (
        body.dose,
        body.frequency,
        body.duration_days,
        body.route,
        body.instructions,
    )
    db.add(f)
    db.commit()
    return _fav_out(f)


@router.delete("/favourites/{fav_id}", status_code=204)
def remove_favourite(fav_id: str, db: DB, user: WriteUser):
    f = db.get(DrugFavourite, fav_id)
    if f and f.user_id == user.id:
        db.delete(f)
        db.commit()


@router.get("/frequent")
def frequent(db: DB, user: ClinicalUser, limit: int = 10):
    """The medicines this doctor writes most, each with the dose they most often use."""
    rows = db.execute(
        select(PrescriptionItem, Prescription.created_at)
        .join(Prescription, Prescription.id == PrescriptionItem.prescription_id)
        .where(Prescription.clinician_id == user.id, Prescription.status == "final")
        .order_by(Prescription.created_at.desc())
        .limit(600)
    ).all()
    by_drug: dict[str, list[PrescriptionItem]] = {}
    for item, _ in rows:
        by_drug.setdefault(item.drug.strip().lower(), []).append(item)
    out = []
    for items in sorted(by_drug.values(), key=len, reverse=True)[: max(1, min(limit, 30))]:
        usual = Tally((i.dose, i.frequency, i.duration_days, i.instructions) for i in items).most_common(1)[0][0]
        out.append(
            {
                "drug": items[0].drug,
                "dose": usual[0],
                "frequency": usual[1],
                "duration_days": usual[2],
                "instructions": usual[3],
                "times": len(items),
            }
        )
    return out


@router.get("/patients/{patient_id}/last")
def last_prescription(patient_id: str, db: DB, _: ClinicalUser):
    """Medicines of this patient's most recent issued prescription, ready to copy into a new one."""
    rx = db.scalars(
        select(Prescription)
        .where(Prescription.patient_id == patient_id, Prescription.status == "final")
        .order_by(Prescription.finalized_at.desc(), Prescription.created_at.desc())
    ).first()
    if rx is None:
        return {"prescription_id": None, "items": []}
    return {
        "prescription_id": rx.id,
        "date": (rx.finalized_at or rx.created_at).date().isoformat(),
        "diagnosis": rx.diagnosis,
        "advice": rx.advice,
        "items": [
            _clean(
                {
                    "drug": i.drug,
                    "dose": i.dose,
                    "frequency": i.frequency,
                    "duration_days": i.duration_days,
                    "route": i.route,
                    "instructions": i.instructions,
                    "strength_mg": i.strength_mg,
                }
            )
            for i in rx.items
        ],
    }
