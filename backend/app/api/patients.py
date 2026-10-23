from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, or_, select

from app.api.deps import DB, AdminUser, CurrentUser, WriteUser
from app.clinical.context import age, latest_observations
from app.models import AIRun, Allergy, Condition, Document, Encounter, Medication, Observation, Patient
from app.schemas.common import (
    AllergyIn,
    AllergyOut,
    ConditionIn,
    ConditionOut,
    EncounterIn,
    EncounterOut,
    MedicationIn,
    MedicationOut,
    ObservationIn,
    ObservationOut,
    PatientIn,
    PatientListItem,
    PatientOut,
    PatientUpdate,
)
from app.services import audit

router = APIRouter(prefix="/api/patients", tags=["patients"])


def get_patient(db, patient_id: str) -> Patient:
    p = db.get(Patient, patient_id)
    if p is None:
        raise HTTPException(404, "Patient not found")
    return p


def patient_out(p: Patient) -> dict:
    data = PatientOut.model_validate(p).model_dump()
    data["age"] = age(p.date_of_birth)
    return data


@router.get("", response_model=list[PatientListItem])
def list_patients(
    db: DB,
    _: CurrentUser,
    q: str | None = None,
    status: str = "active",
    tag: str | None = None,
    sort: str = Query("recent", pattern="^(recent|name|mrn|created)$"),
    limit: int = Query(200, le=500),
):
    stmt = select(Patient)
    if status != "all":
        stmt = stmt.where(Patient.status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Patient.first_name.ilike(like),
                Patient.last_name.ilike(like),
                Patient.mrn.ilike(like),
                (Patient.first_name + " " + Patient.last_name).ilike(like),
            )
        )
    patients = list(db.scalars(stmt.limit(limit)))
    if tag:
        patients = [p for p in patients if tag in (p.tags or [])]
    ids = [p.id for p in patients]
    last_enc = (
        dict(
            db.execute(
                select(Encounter.patient_id, func.max(Encounter.started_at))
                .where(Encounter.patient_id.in_(ids))
                .group_by(Encounter.patient_id)
            ).all()
        )
        if ids
        else {}
    )
    doc_counts = (
        dict(
            db.execute(
                select(Document.patient_id, func.count())
                .where(Document.patient_id.in_(ids))
                .group_by(Document.patient_id)
            ).all()
        )
        if ids
        else {}
    )
    alerts = (
        dict(
            db.execute(
                select(Observation.patient_id, func.count())
                .where(
                    Observation.patient_id.in_(ids),
                    Observation.flag.in_(["high", "low", "abnormal"]),
                    Observation.acknowledged.is_(False),
                )
                .group_by(Observation.patient_id)
            ).all()
        )
        if ids
        else {}
    )
    mismatches = (
        dict(
            db.execute(
                select(Document.patient_id, func.count())
                .where(Document.patient_id.in_(ids), Document.identity_status == "mismatch")
                .group_by(Document.patient_id)
            ).all()
        )
        if ids
        else {}
    )
    conds: dict[str, list[str]] = {}
    if ids:
        for pid, name in db.execute(
            select(Condition.patient_id, Condition.name).where(
                Condition.patient_id.in_(ids), Condition.status == "active"
            )
        ):
            conds.setdefault(pid, []).append(name)
    out = []
    for p in patients:
        item = patient_out(p)
        item.update(
            active_conditions=conds.get(p.id, []),
            last_encounter_at=last_enc.get(p.id),
            document_count=doc_counts.get(p.id, 0),
            open_alerts=alerts.get(p.id, 0) + mismatches.get(p.id, 0),
        )
        out.append(item)

    def _ts(v):
        if v is None:
            return datetime.min.replace(tzinfo=UTC)
        return v if v.tzinfo else v.replace(tzinfo=UTC)

    if sort == "name":
        out.sort(key=lambda x: (x["last_name"].lower(), x["first_name"].lower()))
    elif sort == "mrn":
        out.sort(key=lambda x: x["mrn"])
    elif sort == "created":
        out.sort(key=lambda x: _ts(x["created_at"]), reverse=True)
    else:
        out.sort(key=lambda x: max(_ts(x["last_encounter_at"]), _ts(x["updated_at"])), reverse=True)
    return out


@router.post("", response_model=PatientOut, status_code=201)
def create_patient(body: PatientIn, db: DB, user: WriteUser):
    if db.scalars(select(Patient).where(func.lower(Patient.mrn) == body.mrn.strip().lower())).first():
        raise HTTPException(409, f"A patient with MRN {body.mrn} already exists.")
    p = Patient(**body.model_dump(), created_by=user.id)
    p.mrn = p.mrn.strip()
    db.add(p)
    db.commit()
    audit.record(
        db,
        user,
        "patient.create",
        f"Registered patient {p.full_name} ({p.mrn})",
        entity_type="patient",
        entity_id=p.id,
        patient_id=p.id,
    )
    return patient_out(p)


@router.get("/tags")
def list_tags(db: DB, _: CurrentUser):
    tags: dict[str, int] = {}
    for (t,) in db.execute(select(Patient.tags)):
        for tag in t or []:
            tags[tag] = tags.get(tag, 0) + 1
    return sorted(({"tag": k, "count": v} for k, v in tags.items()), key=lambda x: -x["count"])


@router.get("/{patient_id}", response_model=PatientOut)
def read_patient(patient_id: str, db: DB, user: CurrentUser):
    p = get_patient(db, patient_id)
    audit.record(
        db,
        user,
        "patient.view",
        f"Opened chart of {p.full_name}",
        entity_type="patient",
        entity_id=p.id,
        patient_id=p.id,
    )
    return patient_out(p)


@router.patch("/{patient_id}", response_model=PatientOut)
def update_patient(patient_id: str, body: PatientUpdate, db: DB, user: WriteUser):
    p = get_patient(db, patient_id)
    changes = body.model_dump(exclude_unset=True)
    if (
        "mrn" in changes
        and changes["mrn"].lower() != p.mrn.lower()
        and db.scalars(select(Patient).where(func.lower(Patient.mrn) == changes["mrn"].lower())).first()
    ):
        raise HTTPException(409, "Another patient already has this MRN.")
    for k, v in changes.items():
        setattr(p, k, v)
    db.commit()
    audit.record(
        db,
        user,
        "patient.update",
        f"Updated {p.full_name}",
        entity_type="patient",
        entity_id=p.id,
        patient_id=p.id,
        details={"fields": list(changes)},
    )
    return patient_out(p)


@router.delete("/{patient_id}", status_code=204)
async def delete_patient(patient_id: str, db: DB, admin: AdminUser):
    from app.rag import indexing

    p = get_patient(db, patient_id)
    for doc in db.scalars(select(Document).where(Document.patient_id == p.id)):
        await indexing.remove_document(db, doc)
    name = p.full_name
    db.delete(p)
    db.commit()
    audit.record(
        db, admin, "patient.delete", f"Permanently deleted patient {name}", entity_type="patient", entity_id=patient_id
    )


@router.get("/{patient_id}/scores")
def clinical_scores(patient_id: str, db: DB, _: CurrentUser):
    from app.clinical import scores

    return scores.compute(db, get_patient(db, patient_id))


@router.get("/{patient_id}/overview")
def overview(patient_id: str, db: DB, _: CurrentUser):
    p = get_patient(db, patient_id)
    conditions = db.scalars(
        select(Condition).where(Condition.patient_id == p.id).order_by(Condition.status, Condition.name)
    ).all()
    allergies = db.scalars(select(Allergy).where(Allergy.patient_id == p.id)).all()
    meds = db.scalars(
        select(Medication).where(Medication.patient_id == p.id).order_by(Medication.status, Medication.name)
    ).all()
    encounters = db.scalars(
        select(Encounter).where(Encounter.patient_id == p.id).order_by(Encounter.started_at.desc()).limit(5)
    ).all()
    docs = db.scalars(
        select(Document).where(Document.patient_id == p.id).order_by(Document.created_at.desc()).limit(6)
    ).all()
    latest = latest_observations(db, p.id, limit_codes=12)
    last_summary = db.scalars(
        select(AIRun)
        .where(AIRun.patient_id == p.id, AIRun.tool == "summary", AIRun.status.in_(["draft", "accepted"]))
        .order_by(AIRun.created_at.desc())
    ).first()
    alerts = []
    for o in latest:
        if o.flag in ("high", "low", "abnormal") and not o.acknowledged:
            alerts.append(
                {
                    "type": "lab",
                    "severity": "warning",
                    "title": f"{o.name} {o.flag}",
                    "detail": f"{o.value_num:g} {o.unit or ''} on {o.observed_at.date().isoformat()}",
                    "id": o.id,
                }
            )
    for d in db.scalars(select(Document).where(Document.patient_id == p.id, Document.identity_status == "mismatch")):
        alerts.append(
            {
                "type": "identity",
                "severity": "danger",
                "title": "Possible wrong-patient document",
                "detail": f"{d.title}: {d.identity_detail}",
                "id": d.id,
            }
        )
    for d in db.scalars(select(Document).where(Document.patient_id == p.id, Document.status == "failed")):
        alerts.append(
            {
                "type": "ingestion",
                "severity": "danger",
                "title": "Document could not be processed",
                "detail": f"{d.title}: {d.error}",
                "id": d.id,
            }
        )
    if not allergies:
        alerts.append(
            {
                "type": "gap",
                "severity": "info",
                "title": "Allergies not documented",
                "detail": "No allergy entries — absence is not confirmation of none.",
                "id": None,
            }
        )
    from app.api.documents import doc_out

    return {
        "patient": patient_out(p),
        "conditions": [ConditionOut.model_validate(c).model_dump() for c in conditions],
        "allergies": [AllergyOut.model_validate(a).model_dump() for a in allergies],
        "medications": [MedicationOut.model_validate(m).model_dump() for m in meds],
        "encounters": [EncounterOut.model_validate(e).model_dump() for e in encounters],
        "documents": [doc_out(d) for d in docs],
        "latest_observations": [ObservationOut.model_validate(o).model_dump() for o in latest],
        "alerts": alerts,
        "summary": {
            "id": last_summary.id,
            "output": last_summary.output,
            "created_at": last_summary.created_at,
            "status": last_summary.status,
        }
        if last_summary
        else None,
        "counts": {
            "documents": db.scalar(select(func.count()).select_from(Document).where(Document.patient_id == p.id)),
            "encounters": db.scalar(select(func.count()).select_from(Encounter).where(Encounter.patient_id == p.id)),
            "observations": db.scalar(
                select(func.count()).select_from(Observation).where(Observation.patient_id == p.id)
            ),
        },
    }


# ---- Generic sub-resource CRUD ----------------------------------------------
def _crud(name: str, model, schema_in, schema_out, label_attr: str):
    path = f"/{{patient_id}}/{name}"

    @router.get(path, response_model=list[schema_out], name=f"list_{name}")
    def list_items(patient_id: str, db: DB, _: CurrentUser):
        get_patient(db, patient_id)
        order = getattr(model, "started_at", None) or model.created_at
        return db.scalars(select(model).where(model.patient_id == patient_id).order_by(order.desc())).all()

    @router.post(path, response_model=schema_out, status_code=201, name=f"create_{name}")
    def create_item(patient_id: str, body: schema_in, db: DB, user: WriteUser):
        get_patient(db, patient_id)
        data = body.model_dump()
        if model is Encounter:
            data["started_at"] = data.get("started_at") or datetime.now(UTC)
            data["clinician_id"] = user.id
        item = model(patient_id=patient_id, **data)
        db.add(item)
        db.commit()
        audit.record(
            db,
            user,
            f"{name}.create",
            f"Added {name[:-1] if name.endswith('s') else name}: {getattr(item, label_attr) or ''}",
            entity_type=name,
            entity_id=item.id,
            patient_id=patient_id,
        )
        return item

    @router.patch(f"{path}/{{item_id}}", response_model=schema_out, name=f"update_{name}")
    def update_item(patient_id: str, item_id: str, body: dict, db: DB, user: WriteUser):
        item = db.get(model, item_id)
        if item is None or item.patient_id != patient_id:
            raise HTTPException(404, "Not found")
        merged = schema_out.model_validate(item).model_dump()
        merged.update({k: v for k, v in body.items() if k in schema_in.model_fields})
        validated = schema_in.model_validate({k: merged.get(k) for k in schema_in.model_fields if k in merged})
        for k in body:
            if k in schema_in.model_fields:
                setattr(item, k, getattr(validated, k))
        db.commit()
        audit.record(
            db,
            user,
            f"{name}.update",
            f"Updated {name[:-1]}: {getattr(item, label_attr) or ''}",
            entity_type=name,
            entity_id=item.id,
            patient_id=patient_id,
        )
        return item

    @router.delete(f"{path}/{{item_id}}", status_code=204, name=f"delete_{name}")
    def delete_item(patient_id: str, item_id: str, db: DB, user: WriteUser):
        item = db.get(model, item_id)
        if item is None or item.patient_id != patient_id:
            raise HTTPException(404, "Not found")
        label = getattr(item, label_attr)
        db.delete(item)
        db.commit()
        audit.record(
            db,
            user,
            f"{name}.delete",
            f"Removed {name[:-1]}: {label or ''}",
            entity_type=name,
            entity_id=item_id,
            patient_id=patient_id,
        )


_crud("conditions", Condition, ConditionIn, ConditionOut, "name")
_crud("allergies", Allergy, AllergyIn, AllergyOut, "substance")
_crud("medications", Medication, MedicationIn, MedicationOut, "name")
_crud("encounters", Encounter, EncounterIn, EncounterOut, "reason")


# ---- Observations -----------------------------------------------------------
@router.get("/{patient_id}/observations", response_model=list[ObservationOut])
def list_observations(patient_id: str, db: DB, _: CurrentUser, code: str | None = None):
    get_patient(db, patient_id)
    stmt = select(Observation).where(Observation.patient_id == patient_id)
    if code:
        stmt = stmt.where(Observation.code == code)
    return db.scalars(stmt.order_by(Observation.observed_at.desc())).all()


@router.get("/{patient_id}/trends")
def trends(patient_id: str, db: DB, _: CurrentUser):
    get_patient(db, patient_id)
    rows = db.scalars(
        select(Observation).where(Observation.patient_id == patient_id).order_by(Observation.observed_at)
    ).all()
    series: dict[str, dict] = {}
    for o in rows:
        s = series.setdefault(o.code, {"code": o.code, "name": o.name, "unit": o.unit, "points": []})
        s["unit"] = s["unit"] or o.unit
        s["points"].append(
            {
                "id": o.id,
                "at": o.observed_at,
                "value": o.value_num,
                "text": o.value_text,
                "flag": o.flag,
                "ref_low": o.ref_low,
                "ref_high": o.ref_high,
                "document_id": o.document_id,
                "page": o.source_page,
                "excerpt": o.source_excerpt,
                "acknowledged": o.acknowledged,
            }
        )
    out = []
    for s in series.values():
        nums = [p for p in s["points"] if p["value"] is not None]
        latest = s["points"][-1]
        prev = nums[-2] if len(nums) >= 2 else None
        s["latest"] = latest
        s["change"] = round(latest["value"] - prev["value"], 3) if prev and latest["value"] is not None else None
        s["trend"] = (
            None if s["change"] is None else ("up" if s["change"] > 0 else "down" if s["change"] < 0 else "flat")
        )
        s["abnormal"] = latest["flag"] in ("high", "low", "abnormal")
        out.append(s)
    out.sort(key=lambda s: (not s["abnormal"], s["name"]))
    return out


@router.post("/{patient_id}/observations", response_model=ObservationOut, status_code=201)
def add_observation(patient_id: str, body: ObservationIn, db: DB, user: WriteUser):
    get_patient(db, patient_id)
    flag = None
    if body.value_num is not None and (body.ref_low is not None or body.ref_high is not None):
        flag = (
            "low"
            if body.ref_low is not None and body.value_num < body.ref_low
            else "high"
            if body.ref_high is not None and body.value_num > body.ref_high
            else "normal"
        )
    code = body.code or "_".join(body.name.lower().split())
    ref_text = f"{body.ref_low:g}-{body.ref_high:g}" if body.ref_low is not None and body.ref_high is not None else None
    o = Observation(
        patient_id=patient_id,
        name=body.name,
        code=code,
        value_num=body.value_num,
        value_text=body.value_text,
        unit=body.unit,
        ref_low=body.ref_low,
        ref_high=body.ref_high,
        ref_text=ref_text,
        flag=flag,
        observed_at=body.observed_at or datetime.now(UTC),
        method="manual",
    )
    db.add(o)
    db.commit()
    audit.record(
        db,
        user,
        "observation.create",
        f"Recorded {o.name}",
        entity_type="observation",
        entity_id=o.id,
        patient_id=patient_id,
    )
    return o


@router.post("/{patient_id}/observations/{obs_id}/acknowledge", response_model=ObservationOut)
def acknowledge(patient_id: str, obs_id: str, db: DB, user: WriteUser):
    o = db.get(Observation, obs_id)
    if o is None or o.patient_id != patient_id:
        raise HTTPException(404, "Not found")
    o.acknowledged = True
    db.commit()
    audit.record(
        db,
        user,
        "observation.acknowledge",
        f"Acknowledged {o.name} ({o.flag})",
        entity_type="observation",
        entity_id=o.id,
        patient_id=patient_id,
    )
    return o


@router.delete("/{patient_id}/observations/{obs_id}", status_code=204)
def delete_observation(patient_id: str, obs_id: str, db: DB, user: WriteUser):
    o = db.get(Observation, obs_id)
    if o is None or o.patient_id != patient_id:
        raise HTTPException(404, "Not found")
    db.delete(o)
    db.commit()


# ---- Timeline & export ------------------------------------------------------
@router.get("/{patient_id}/timeline")
def timeline(patient_id: str, db: DB, _: CurrentUser):
    p = get_patient(db, patient_id)
    events = []

    def add(at, kind, title, detail=None, ref=None, tone="neutral"):
        if at is None:
            return
        if not isinstance(at, datetime):
            at = datetime.combine(at, datetime.min.time(), tzinfo=UTC)
        events.append(
            {
                "at": at if at.tzinfo else at.replace(tzinfo=UTC),
                "kind": kind,
                "title": title,
                "detail": detail,
                "ref": ref,
                "tone": tone,
            }
        )

    for e in db.scalars(select(Encounter).where(Encounter.patient_id == p.id)):
        add(
            e.started_at,
            "encounter",
            f"{e.type.replace('_', ' ').title()} visit",
            e.reason,
            {"encounter_id": e.id},
            "primary",
        )
    for d in db.scalars(select(Document).where(Document.patient_id == p.id)):
        add(
            d.document_date or d.created_at,
            "document",
            d.title,
            d.kind.replace("_", " "),
            {"document_id": d.id},
            "danger" if d.identity_status == "mismatch" else "info",
        )
    for c in db.scalars(select(Condition).where(Condition.patient_id == p.id)):
        add(
            c.onset_date or c.created_at,
            "condition",
            f"Diagnosis: {c.name}",
            c.status,
            {"condition_id": c.id},
            "warning" if c.status == "active" else "neutral",
        )
    for m in db.scalars(select(Medication).where(Medication.patient_id == p.id)):
        add(
            m.start_date or m.created_at,
            "medication",
            f"Started {m.name}",
            " ".join(filter(None, [m.dose, m.frequency])),
            {"medication_id": m.id},
            "success",
        )
        if m.end_date:
            add(m.end_date, "medication", f"Stopped {m.name}", m.notes, {"medication_id": m.id}, "neutral")
    obs_by_day: dict = {}
    for o in db.scalars(select(Observation).where(Observation.patient_id == p.id)):
        obs_by_day.setdefault((o.observed_at.date(), o.document_id), []).append(o)
    for (day, doc_id), items in obs_by_day.items():
        abnormal = [o for o in items if o.flag in ("high", "low", "abnormal")]
        add(
            day,
            "labs",
            f"{len(items)} results recorded",
            f"{len(abnormal)} outside reference range" if abnormal else "all within stated ranges",
            {"document_id": doc_id},
            "warning" if abnormal else "success",
        )
    for r in db.scalars(select(AIRun).where(AIRun.patient_id == p.id, AIRun.status == "accepted")):
        add(
            r.reviewed_at or r.created_at,
            "ai",
            f"Accepted AI {r.tool.replace('_', ' ')}",
            None,
            {"run_id": r.id},
            "primary",
        )
    events.sort(key=lambda e: e["at"], reverse=True)
    return events


@router.get("/{patient_id}/export", response_class=PlainTextResponse)
def export_summary(patient_id: str, db: DB, user: CurrentUser):
    from app.clinical.context import patient_record_text

    p = get_patient(db, patient_id)
    last = db.scalars(
        select(AIRun)
        .where(AIRun.patient_id == p.id, AIRun.tool == "summary", AIRun.status == "accepted")
        .order_by(AIRun.created_at.desc())
    ).first()
    lines = [
        f"# Patient summary — {p.full_name}",
        "",
        f"_Exported {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} by {user.full_name}_",
        "",
        "## Structured record",
        "",
    ]
    lines += [
        f"- {line}" if not line.startswith("- ") else f"  {line}"
        for line in patient_record_text(db, p, max_encounters=10).splitlines()
    ]
    if last and last.output:
        o = last.output
        lines += ["", "## Clinician-accepted AI summary", "", o.get("one_liner", "")]
        for key, title in (
            ("key_findings", "Key findings"),
            ("recent_changes", "Recent changes"),
            ("missing_information", "Missing information"),
            ("follow_up_considerations", "Follow-up considerations"),
        ):
            items = o.get(key) or []
            if items:
                lines += ["", f"### {title}"] + [
                    f"- {i['finding'] if isinstance(i, dict) and 'finding' in i else i}" for i in items
                ]
    lines += ["", "---", "Clinical decision support output. Verify against the source record before use."]
    audit.record(
        db,
        user,
        "patient.export",
        f"Exported summary of {p.full_name}",
        entity_type="patient",
        entity_id=p.id,
        patient_id=p.id,
    )
    return PlainTextResponse(
        "\n".join(lines), headers={"Content-Disposition": f'attachment; filename="{p.mrn}-summary.md"'}
    )
