"""Point-of-care API: the day list, consultations, prescriptions with safety checks,
investigation orders and their results, and the medicine catalogue."""

from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import DB, AIUser, ClinicalUser, CurrentUser, StaffUser, WriteUser
from app.clinical.context import age
from app.db import utcnow
from app.formulary import dosing, images
from app.models import (
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
from app.services import audit, consult, orders, runtime_config

router = APIRouter(prefix="/api", tags=["care"])


# ---------------------------------------------------------------------------------------------
# Appointments — deliberately minimal: who is expected today
# ---------------------------------------------------------------------------------------------


class AppointmentIn(BaseModel):
    patient_id: str
    day: date | None = None
    time: str | None = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    reason: str | None = Field(None, max_length=300)


class AppointmentUpdate(BaseModel):
    day: date | None = None
    time: str | None = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    reason: str | None = Field(None, max_length=300)
    status: Literal["expected", "arrived", "seen", "cancelled"] | None = None


def appointment_out(db, a: Appointment) -> dict:
    p = db.get(Patient, a.patient_id)
    return {
        "id": a.id,
        "day": a.day.isoformat(),
        "time": a.time,
        "reason": a.reason,
        "status": a.status,
        "encounter_id": a.encounter_id,
        "patient_id": a.patient_id,
        "patient": {
            "id": p.id,
            "name": p.full_name,
            "mrn": p.mrn,
            "age": age(p.date_of_birth),
            "sex": p.sex,
            "phone": p.phone,
        }
        if p
        else None,
    }


@router.get("/appointments")
def list_appointments(db: DB, _: CurrentUser, day: date | None = None, patient_id: str | None = None):
    stmt = select(Appointment)
    if patient_id:
        stmt = stmt.where(Appointment.patient_id == patient_id, Appointment.day >= date.today() - timedelta(days=1))
    else:
        stmt = stmt.where(Appointment.day == (day or date.today()))
    rows = db.scalars(
        stmt.order_by(Appointment.day, Appointment.time.is_(None), Appointment.time, Appointment.created_at)
    ).all()
    return [appointment_out(db, a) for a in rows]


@router.post("/appointments", status_code=201)
def add_appointment(body: AppointmentIn, db: DB, user: StaffUser):
    p = consult.patient_or_404(db, body.patient_id)
    day = body.day or date.today()
    dup = db.scalar(
        select(Appointment).where(
            Appointment.patient_id == p.id, Appointment.day == day, Appointment.status != "cancelled"
        )
    )
    if dup:
        raise HTTPException(409, f"{p.full_name} is already on the list for {day.isoformat()}")
    a = Appointment(
        patient_id=p.id,
        day=day,
        time=body.time,
        reason=body.reason,
        created_by=user.id,
        clinician_id=user.id if user.role == "clinician" else None,
    )
    db.add(a)
    db.commit()
    audit.record(
        db,
        user,
        "appointment.create",
        f"Added {p.full_name} to the list for {day.isoformat()}",
        entity_type="appointment",
        entity_id=a.id,
        patient_id=p.id,
    )
    return appointment_out(db, a)


@router.patch("/appointments/{appointment_id}")
def update_appointment(appointment_id: str, body: AppointmentUpdate, db: DB, user: StaffUser):
    a = db.get(Appointment, appointment_id)
    if a is None:
        raise HTTPException(404, "Appointment not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    db.commit()
    return appointment_out(db, a)


@router.delete("/appointments/{appointment_id}", status_code=204)
def delete_appointment(appointment_id: str, db: DB, user: StaffUser):
    a = db.get(Appointment, appointment_id)
    if a is None:
        raise HTTPException(404, "Appointment not found")
    db.delete(a)
    db.commit()


# ---------------------------------------------------------------------------------------------
# Pre-visit brief
# ---------------------------------------------------------------------------------------------


@router.get("/patients/{patient_id}/previsit")
def previsit(patient_id: str, db: DB, _: ClinicalUser):
    p = consult.patient_or_404(db, patient_id)
    return {
        "facts": consult.previsit_facts(db, p),
        "brief": consult.run_out(consult.latest_run(db, "previsit_brief", patient_id=p.id)),
    }


@router.post("/patients/{patient_id}/previsit/brief")
async def generate_brief(patient_id: str, db: DB, user: AIUser):
    p = consult.patient_or_404(db, patient_id)
    return consult.run_out(await consult.previsit_brief(db, user, p))


# ---------------------------------------------------------------------------------------------
# Consultation
# ---------------------------------------------------------------------------------------------


class ConsultStart(BaseModel):
    appointment_id: str | None = None
    reason: str | None = Field(None, max_length=500)


class Diagnosis(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    code: str | None = None
    add_to_problems: bool = False


class ConsultUpdate(BaseModel):
    reason: str | None = Field(None, max_length=500)
    history: str | None = None
    examination: str | None = None
    assessment: str | None = None
    plan: str | None = None
    notes: str | None = None
    vitals: dict | None = None
    diagnoses: list[Diagnosis] | None = None


class ConsultComplete(BaseModel):
    follow_up_date: date | None = None


def _encounter(db, encounter_id: str) -> Encounter:
    enc = db.get(Encounter, encounter_id)
    if enc is None:
        raise HTTPException(404, "Consultation not found")
    return enc


def encounter_out(enc: Encounter) -> dict:
    return {
        "id": enc.id,
        "patient_id": enc.patient_id,
        "type": enc.type,
        "status": enc.status,
        "started_at": enc.started_at.isoformat(),
        "ended_at": enc.ended_at.isoformat() if enc.ended_at else None,
        "reason": enc.reason,
        "history": enc.history,
        "examination": enc.examination,
        "assessment": enc.assessment,
        "plan": enc.plan,
        "notes": enc.notes,
        "vitals": enc.vitals or {},
        "diagnoses": enc.diagnoses or [],
        "clinician_id": enc.clinician_id,
    }


def _draft_for(db, enc: Encounter) -> Prescription | None:
    return db.scalar(
        select(Prescription)
        .where(Prescription.encounter_id == enc.id, Prescription.status != "cancelled")
        .order_by(Prescription.created_at.desc())
    )


@router.post("/patients/{patient_id}/consultations", status_code=201)
def start_consultation(patient_id: str, body: ConsultStart, db: DB, user: WriteUser):
    p = consult.patient_or_404(db, patient_id)
    return encounter_out(consult.start_consultation(db, user, p, body.appointment_id, body.reason))


@router.get("/consultations/{encounter_id}")
def consultation(encounter_id: str, db: DB, _: ClinicalUser):
    enc = _encounter(db, encounter_id)
    rx = _draft_for(db, enc)
    ords = db.scalars(
        select(Order).where(Order.encounter_id == enc.id, Order.status != "cancelled").order_by(Order.ordered_at)
    ).all()
    return {
        "encounter": encounter_out(enc),
        "prescription": consult.prescription_out(rx) if rx else None,
        "orders": [order_out(db, o) for o in ords],
        "diagnosis_check": consult.run_out(consult.latest_run(db, "diagnosis_check", encounter_id=enc.id)),
        "rx_review": consult.run_out(consult.latest_run(db, "rx_review", key=("prescription_id", rx.id)))
        if rx
        else None,
    }


@router.patch("/consultations/{encounter_id}")
def update_consultation(encounter_id: str, body: ConsultUpdate, db: DB, user: WriteUser):
    enc = _encounter(db, encounter_id)
    data = body.model_dump(exclude_unset=True)
    if "diagnoses" in data:
        data["diagnoses"] = [d for d in data["diagnoses"] if d["name"].strip()]
    for k, v in data.items():
        setattr(enc, k, v)
    db.commit()
    return encounter_out(enc)


@router.post("/consultations/{encounter_id}/diagnosis-check")
async def diagnosis_check(encounter_id: str, db: DB, user: AIUser):
    return consult.run_out(await consult.diagnosis_check(db, user, _encounter(db, encounter_id)))


@router.post("/consultations/{encounter_id}/complete")
def complete_consultation(encounter_id: str, body: ConsultComplete, db: DB, user: WriteUser):
    enc = _encounter(db, encounter_id)
    rx = _draft_for(db, enc)
    if rx and rx.status == "draft" and rx.items:
        raise HTTPException(409, "Finalise or discard the prescription before completing the consultation.")
    enc.status, enc.ended_at = "completed", utcnow()
    existing = {c.name.lower() for c in db.scalars(select(Condition).where(Condition.patient_id == enc.patient_id))}
    added = []
    for d in enc.diagnoses or []:
        if d.get("add_to_problems") and d["name"].lower() not in existing:
            db.add(
                Condition(
                    patient_id=enc.patient_id,
                    encounter_id=enc.id,
                    name=d["name"],
                    code=d.get("code"),
                    status="active",
                    onset_date=date.today(),
                )
            )
            added.append(d["name"])
    for a in db.scalars(select(Appointment).where(Appointment.encounter_id == enc.id)):
        a.status = "seen"
    follow = body.follow_up_date or (rx.follow_up_date if rx else None)
    if (
        follow
        and follow > date.today()
        and not db.scalar(
            select(Appointment).where(Appointment.patient_id == enc.patient_id, Appointment.day == follow)
        )
    ):
        db.add(
            Appointment(
                patient_id=enc.patient_id, day=follow, reason="Follow-up", created_by=user.id, clinician_id=user.id
            )
        )
    db.commit()
    p = db.get(Patient, enc.patient_id)
    audit.record(
        db,
        user,
        "consultation.complete",
        f"Completed consultation with {p.full_name}",
        entity_type="encounter",
        entity_id=enc.id,
        patient_id=p.id,
        details={"problems_added": added},
    )
    return encounter_out(enc)


# ---------------------------------------------------------------------------------------------
# Prescriptions
# ---------------------------------------------------------------------------------------------


class RxItemIn(BaseModel):
    drug: str = Field(min_length=1, max_length=200)
    dose: str | None = Field("1 tab", max_length=60)
    frequency: str | None = Field("BD", max_length=20)
    duration_days: int | None = Field(None, ge=0, le=3650)
    route: str | None = Field(None, max_length=40)
    instructions: str | None = Field(None, max_length=300)
    strength_mg: float | None = None
    override_reason: str | None = Field(None, max_length=500)


class RxIn(BaseModel):
    diagnosis: str | None = Field(None, max_length=500)
    advice: str | None = None
    follow_up_date: date | None = None
    items: list[RxItemIn] = []


class RxCheckIn(BaseModel):
    patient_id: str
    prescription_id: str | None = None
    items: list[RxItemIn]


class RxFinalize(BaseModel):
    overrides: dict[str, str] = {}  # item id -> reason for proceeding despite a critical finding


def _rx(db, rx_id: str) -> Prescription:
    rx = db.get(Prescription, rx_id)
    if rx is None:
        raise HTTPException(404, "Prescription not found")
    return rx


@router.get("/patients/{patient_id}/prescriptions")
def list_prescriptions(patient_id: str, db: DB, _: ClinicalUser):
    rows = db.scalars(
        select(Prescription)
        .where(Prescription.patient_id == patient_id, Prescription.status != "cancelled")
        .order_by(Prescription.created_at.desc())
    ).all()
    return [consult.prescription_out(r) for r in rows]


@router.post("/consultations/{encounter_id}/prescription", status_code=201)
def open_prescription(encounter_id: str, db: DB, user: WriteUser):
    enc = _encounter(db, encounter_id)
    rx = _draft_for(db, enc)
    if rx is None:
        dx = "; ".join(d.get("name", "") for d in enc.diagnoses or []) or None
        rx = Prescription(
            patient_id=enc.patient_id, encounter_id=enc.id, clinician_id=user.id, status="draft", diagnosis=dx
        )
        db.add(rx)
        db.commit()
    return consult.prescription_out(rx)


@router.get("/prescriptions/{rx_id}")
def read_prescription(rx_id: str, db: DB, _: ClinicalUser):
    rx = _rx(db, rx_id)
    data = consult.prescription_out(rx)
    p = db.get(Patient, rx.patient_id)
    doc = db.get(User, rx.clinician_id) if rx.clinician_id else None
    data["patient"] = {
        "id": p.id,
        "name": p.full_name,
        "mrn": p.mrn,
        "age": age(p.date_of_birth),
        "sex": p.sex,
        "phone": p.phone,
        "address": p.address,
    }
    data["clinician"] = {"name": doc.full_name, "email": doc.email} if doc else None
    enc = db.get(Encounter, rx.encounter_id) if rx.encounter_id else None
    data["encounter"] = encounter_out(enc) if enc else None
    data["review"] = consult.run_out(consult.latest_run(db, "rx_review", key=("prescription_id", rx.id)))
    return data


@router.put("/prescriptions/{rx_id}")
def save_prescription(rx_id: str, body: RxIn, db: DB, user: WriteUser):
    rx = _rx(db, rx_id)
    if rx.status != "draft":
        raise HTTPException(409, "This prescription is final. Start a new one to make changes.")
    patient = db.get(Patient, rx.patient_id)
    items = [i.model_dump() for i in body.items]
    result = consult.run_checks(db, patient, items, rx.id)
    rx.diagnosis, rx.advice, rx.follow_up_date = body.diagnosis, body.advice, body.follow_up_date
    rx.items.clear()
    db.flush()
    for pos, (i, res) in enumerate(zip(items, result["items"], strict=True)):
        rx.items.append(
            PrescriptionItem(
                position=pos,
                drug=i["drug"].strip(),
                generic="+".join(g["id"] for g in res["generics"]) or None,
                strength_mg=i.get("strength_mg"),
                dose=i.get("dose") or "",
                route=i.get("route"),
                frequency=i.get("frequency") or "",
                duration_days=i.get("duration_days"),
                instructions=i.get("instructions"),
                checks=res["findings"],
                override_reason=i.get("override_reason"),
            )
        )
    rx.context = {
        "patient": result["patient"],
        "summary": result["summary"],
        "status": result["status"],
        "region": result["region"],
        "formulary_version": result["formulary_version"],
    }
    db.commit()
    data = consult.prescription_out(rx)
    data["check"] = result
    return data


@router.post("/prescriptions/check")
def check_prescription(body: RxCheckIn, db: DB, _: ClinicalUser):
    p = consult.patient_or_404(db, body.patient_id)
    return consult.run_checks(db, p, [i.model_dump() for i in body.items], body.prescription_id)


@router.post("/prescriptions/{rx_id}/review")
async def review_prescription(rx_id: str, db: DB, user: AIUser):
    return consult.run_out(await consult.review_prescription(db, user, _rx(db, rx_id)))


@router.post("/prescriptions/{rx_id}/finalize")
def finalize_prescription(rx_id: str, body: RxFinalize, db: DB, user: WriteUser):
    rx = _rx(db, rx_id)
    if rx.status != "draft":
        raise HTTPException(409, "Already finalised")
    if not rx.items:
        raise HTTPException(400, "The prescription has no medicines")
    patient = db.get(Patient, rx.patient_id)
    result = consult.run_checks(db, patient, [consult._item_dict(i) for i in rx.items], rx.id)
    missing = []
    for item, res in zip(rx.items, result["items"], strict=True):
        item.checks = res["findings"]
        reason = (body.overrides.get(item.id) or item.override_reason or "").strip()
        if any(f["severity"] == "critical" for f in res["findings"]):
            if not reason:
                missing.append(item.drug)
            item.override_reason = reason or None
    if missing:
        db.rollback()
        raise HTTPException(422, "Record a reason to proceed for: " + ", ".join(missing))

    # Add to the chart: replaces any active entry for the same medicine.
    today = date.today()
    active = list(
        db.scalars(select(Medication).where(Medication.patient_id == patient.id, Medication.status == "active"))
    )
    fm = consult.formulary(db)
    for item in rx.items:
        gens = set((item.generic or "").split("+")) - {""}
        for m in active:
            mg = set((m.generic or "").split("+")) - {""} or set(fm.resolve(m.name).generic_ids)
            if gens and mg == gens and m.prescription_id != rx.id:
                m.status, m.end_date = "stopped", today
                m.notes = ((m.notes or "") + f" Replaced by prescription of {today.isoformat()}.").strip()
        db.add(
            Medication(
                patient_id=patient.id,
                encounter_id=rx.encounter_id,
                name=item.drug,
                generic=item.generic,
                dose=item.dose,
                route=item.route or "oral",
                frequency=item.frequency,
                indication=rx.diagnosis,
                start_date=today,
                end_date=today + timedelta(days=item.duration_days) if item.duration_days else None,
                status="active",
                notes=item.instructions,
                source="prescription",
                prescription_id=rx.id,
            )
        )
    rx.status, rx.finalized_at = "final", utcnow()
    rx.context = {
        **(rx.context or {}),
        "patient": result["patient"],
        "summary": result["summary"],
        "status": result["status"],
    }
    db.commit()
    audit.record(
        db,
        user,
        "prescription.finalize",
        f"Finalised prescription for {patient.full_name}",
        entity_type="prescription",
        entity_id=rx.id,
        patient_id=patient.id,
        details={
            "items": [i.drug for i in rx.items],
            "overrides": {i.drug: i.override_reason for i in rx.items if i.override_reason},
        },
    )
    return consult.prescription_out(rx)


@router.post("/prescriptions/{rx_id}/discard")
def discard_prescription(rx_id: str, db: DB, user: WriteUser):
    rx = _rx(db, rx_id)
    if rx.status == "final":
        # A final prescription is a record: cancelling stops its medicines but keeps it.
        for m in db.scalars(
            select(Medication).where(Medication.prescription_id == rx.id, Medication.status == "active")
        ):
            m.status, m.end_date = "stopped", date.today()
    rx.status = "cancelled"
    db.commit()
    audit.record(
        db,
        user,
        "prescription.cancel",
        "Cancelled prescription",
        entity_type="prescription",
        entity_id=rx.id,
        patient_id=rx.patient_id,
    )
    return {"ok": True}


# ---------------------------------------------------------------------------------------------
# Formulary
# ---------------------------------------------------------------------------------------------


@router.get("/formulary/search")
def formulary_search(
    db: DB, _: ClinicalUser, q: str = Query(..., min_length=1, max_length=80), limit: int = Query(12, le=30)
):
    return consult.formulary(db).search(q, limit)


@router.get("/formulary/meta")
def formulary_meta(db: DB, _: ClinicalUser):
    cfg = runtime_config.load(db)
    fm = consult.formulary(db)
    return {
        "region": fm.region,
        "name": fm.meta.get("name"),
        "version": fm.meta.get("version"),
        "source_note": fm.meta.get("source_note"),
        "generics": len(fm.generics),
        "products": len(fm.products),
        "frequencies": dosing.FREQUENCY_OPTIONS,
        "fetch_images": cfg.formulary.fetch_images,
    }


@router.get("/formulary/generics/{generic_id}")
def formulary_generic(generic_id: str, db: DB, _: ClinicalUser):
    fm = consult.formulary(db)
    g = fm.generics.get(generic_id)
    if g is None:
        raise HTTPException(404, "Unknown medicine")
    brands = [fm.product_option(p) for p in fm.products if generic_id in p.components][:30]
    meta = images.cached(generic_id)
    return {
        "id": g.id,
        "name": g.name,
        "class": g.drug_class,
        "unit": g.unit,
        "rules": g.data,
        "products": brands,
        "image": _image_public(generic_id, meta),
    }


def _image_public(gid: str, meta: dict | None) -> dict | None:
    if not meta or meta.get("status") != "ok":
        return None
    return {
        "url": f"/api/formulary/generics/{gid}/image",
        "title": meta.get("title"),
        "author": meta.get("author"),
        "license": meta.get("license"),
        "source_url": meta.get("source_url"),
    }


@router.get("/formulary/generics/{generic_id}/image-info")
async def formulary_image_info(generic_id: str, db: DB, _: ClinicalUser):
    cfg = runtime_config.load(db)
    fm = consult.formulary(db)
    g = fm.generics.get(generic_id)
    if g is None:
        raise HTTPException(404, "Unknown medicine")
    if not cfg.formulary.fetch_images:
        return {"enabled": False, "image": _image_public(generic_id, images.cached(generic_id))}
    meta = await images.fetch(generic_id, g.data.get("image") or f"{g.name} tablets")
    return {"enabled": True, "image": _image_public(generic_id, meta), "status": meta.get("status")}


@router.get("/formulary/generics/{generic_id}/image")
def formulary_image(generic_id: str, _: ClinicalUser):
    meta = images.cached(generic_id)
    path = images.file_path(meta) if meta else None
    if path is None:
        raise HTTPException(404, "No image")
    return FileResponse(
        path, media_type=meta.get("mime") or "image/jpeg", headers={"Cache-Control": "private, max-age=604800"}
    )


# ---------------------------------------------------------------------------------------------
# Orders & results
# ---------------------------------------------------------------------------------------------


class OrderIn(BaseModel):
    test_name: str = Field(min_length=2, max_length=200)
    category: Literal["lab", "radiology", "cardiology", "other"] | None = None
    reason: str | None = Field(None, max_length=500)
    urgency: Literal["routine", "urgent"] = "routine"
    encounter_id: str | None = None


class OrderUpdate(BaseModel):
    test_name: str | None = Field(None, min_length=2, max_length=200)
    reason: str | None = Field(None, max_length=500)
    urgency: Literal["routine", "urgent"] | None = None
    status: Literal["ordered", "cancelled"] | None = None


class OrderAttach(BaseModel):
    document_id: str


class OrderReviewed(BaseModel):
    note: str | None = None


def order_out(db, o: Order, clinical: bool = True) -> dict:
    doc = db.get(Document, o.result_document_id) if o.result_document_id else None
    data = {
        "id": o.id,
        "patient_id": o.patient_id,
        "encounter_id": o.encounter_id,
        "category": o.category,
        "test_name": o.test_name,
        "urgency": o.urgency,
        "status": o.status,
        "ordered_at": o.ordered_at.isoformat(),
        "result_at": o.result_at.isoformat() if o.result_at else None,
        "reviewed_at": o.reviewed_at.isoformat() if o.reviewed_at else None,
        "result_document": {"id": doc.id, "title": doc.title, "status": doc.status, "kind": doc.kind} if doc else None,
    }
    if clinical:
        data.update(
            reason=o.reason,
            review_note=o.review_note,
            ai_review=consult.run_out(consult.latest_run(db, "result_review", key=("order_id", o.id))),
        )
    return data


def _order(db, order_id: str) -> Order:
    o = db.get(Order, order_id)
    if o is None:
        raise HTTPException(404, "Order not found")
    return o


@router.get("/patients/{patient_id}/orders")
def list_orders(patient_id: str, db: DB, user: CurrentUser, status: str | None = None):
    stmt = select(Order).where(Order.patient_id == patient_id)
    if status:
        stmt = stmt.where(Order.status.in_(status.split(",")))
    clinical = user.role != "front_desk"
    return [order_out(db, o, clinical) for o in db.scalars(stmt.order_by(Order.ordered_at.desc()))]


@router.post("/patients/{patient_id}/orders", status_code=201)
def create_order(patient_id: str, body: OrderIn, db: DB, user: WriteUser):
    p = consult.patient_or_404(db, patient_id)
    o = Order(
        patient_id=p.id,
        encounter_id=body.encounter_id,
        clinician_id=user.id,
        test_name=body.test_name.strip(),
        category=body.category or orders.guess_category(body.test_name),
        reason=body.reason,
        urgency=body.urgency,
    )
    db.add(o)
    db.commit()
    audit.record(
        db,
        user,
        "order.create",
        f"Ordered {o.test_name} for {p.full_name}",
        entity_type="order",
        entity_id=o.id,
        patient_id=p.id,
    )
    return order_out(db, o)


@router.patch("/orders/{order_id}")
def update_order(order_id: str, body: OrderUpdate, db: DB, user: WriteUser):
    o = _order(db, order_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(o, k, v)
    db.commit()
    return order_out(db, o)


@router.post("/orders/{order_id}/attach")
def attach_result(order_id: str, body: OrderAttach, db: DB, user: StaffUser):
    o = _order(db, order_id)
    doc = db.get(Document, body.document_id)
    if doc is None or doc.patient_id != o.patient_id:
        raise HTTPException(400, "That report does not belong to this patient")
    orders.attach(db, o, doc)
    db.commit()
    audit.record(
        db,
        user,
        "order.result",
        f"Attached {doc.title} to {o.test_name}",
        entity_type="order",
        entity_id=o.id,
        patient_id=o.patient_id,
    )
    return order_out(db, o, user.role != "front_desk")


@router.post("/orders/{order_id}/ai-review")
async def ai_review_result(order_id: str, db: DB, user: AIUser):
    return consult.run_out(await consult.review_result(db, user, _order(db, order_id)))


@router.post("/orders/{order_id}/reviewed")
def mark_reviewed(order_id: str, body: OrderReviewed, db: DB, user: WriteUser):
    o = _order(db, order_id)
    if not o.result_document_id:
        raise HTTPException(400, "No result attached yet")
    o.status, o.reviewed_at, o.review_note = "reviewed", utcnow(), body.note
    db.commit()
    audit.record(
        db,
        user,
        "order.reviewed",
        f"Reviewed {o.test_name}",
        entity_type="order",
        entity_id=o.id,
        patient_id=o.patient_id,
    )
    return order_out(db, o)


# ---------------------------------------------------------------------------------------------
# Today — the day list with what the doctor should know about each patient
# ---------------------------------------------------------------------------------------------


@router.get("/today")
def today_list(db: DB, user: CurrentUser):
    from app.clinical.context import latest_observations

    rows = db.scalars(
        select(Appointment)
        .where(Appointment.day == date.today(), Appointment.status != "cancelled")
        .order_by(Appointment.time.is_(None), Appointment.time, Appointment.created_at)
    ).all()
    out = []
    for a in rows:
        item = appointment_out(db, a)
        if user.role != "front_desk":
            p = db.get(Patient, a.patient_id)
            latest = latest_observations(db, p.id, limit_codes=60)
            last = db.scalar(
                select(Encounter)
                .where(Encounter.patient_id == p.id, Encounter.status == "completed")
                .order_by(Encounter.started_at.desc())
            )
            item["clinical"] = {
                "conditions": [
                    c.name
                    for c in db.scalars(
                        select(Condition).where(Condition.patient_id == p.id, Condition.status == "active")
                    )
                ][:4],
                "abnormal": sum(1 for o in latest if o.flag in ("high", "low", "abnormal") and not o.acknowledged),
                "results_back": db.scalar(
                    select(func.count())
                    .select_from(Order)
                    .where(Order.patient_id == p.id, Order.status == "result_received")
                )
                or 0,
                "pending_orders": db.scalar(
                    select(func.count()).select_from(Order).where(Order.patient_id == p.id, Order.status == "ordered")
                )
                or 0,
                "last_visit": last.started_at.date().isoformat() if last else None,
                "last_reason": last.reason if last else None,
                "has_brief": consult.latest_run(db, "previsit_brief", patient_id=p.id) is not None,
            }
        out.append(item)
    counts = {s: sum(1 for x in out if x["status"] == s) for s in ("expected", "arrived", "seen")}
    return {"date": date.today().isoformat(), "appointments": out, "counts": counts}
