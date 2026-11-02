"""Finding and merging duplicate charts, and importing patients from a spreadsheet.

Registered before the main patients router so that fixed paths such as /duplicates are not read as a patient id.
"""

from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import DB, StaffUser, WriteUser
from app.models import Patient
from app.rag import registry_access
from app.services import audit, dedupe
from app.services import branches as branch_svc

router = APIRouter(prefix="/api/patients", tags=["patients"])


class PersonIn(BaseModel):
    first_name: str = ""
    last_name: str = ""
    date_of_birth: date | None = None
    phone: str | None = None
    email: str | None = None
    exclude_id: str | None = None


@router.post("/duplicates/check")
def check_duplicates(body: PersonIn, db: DB, _: StaffUser):
    """Used while registering: who in the clinic might this already be? Reveals only what the front desk already sees."""
    if len(body.first_name.strip()) < 2 and not body.phone and not body.email:
        return []
    return dedupe.find_matches(db, body.model_dump(exclude={"exclude_id"}), exclude_id=body.exclude_id)


@router.get("/duplicates")
def list_duplicates(db: DB, _: WriteUser):
    return dedupe.scan_all(db)


@router.get("/next-mrn")
def next_mrn(db: DB, _: StaffUser):
    """What the next automatic MRN will look like (it is only reserved when a patient is saved)."""
    prefix = dedupe.mrn_prefix(db)
    from app.models import Counter

    row = db.get(Counter, "MRN")
    return {"prefix": prefix, "example": f"{prefix}-{((row.value if row else db.query(Patient).count()) + 1):05d}"}


class MergeIn(BaseModel):
    keep_id: str
    merge_id: str
    confirm_mrn: str = Field(description="The MRN of the chart being merged away, typed to confirm")


@router.post("/merge")
async def merge_patients(body: MergeIn, db: DB, user: WriteUser):
    keep, dupe = db.get(Patient, body.keep_id), db.get(Patient, body.merge_id)
    if keep is None or dupe is None:
        raise HTTPException(404, "Patient not found")
    if body.confirm_mrn.strip().lower() != dupe.mrn.lower():
        raise HTTPException(422, f"Type the MRN {dupe.mrn} to confirm that this chart should be merged away.")
    result = dedupe.merge(db, keep, dupe)
    db.commit()
    await registry_access.reassign_patient_vectors(db, dupe.id, keep.id)
    audit.record(
        db,
        user,
        "patient.merge",
        f"Merged chart {dupe.mrn} ({dupe.full_name}) into {keep.mrn} ({keep.full_name})",
        entity_type="patient",
        entity_id=keep.id,
        patient_id=keep.id,
        details={"merged_id": dupe.id, "merged_mrn": dupe.mrn, **result},
    )
    audit.record(
        db,
        user,
        "patient.merged_away",
        f"Chart {dupe.mrn} was merged into {keep.mrn}",
        entity_type="patient",
        entity_id=dupe.id,
        patient_id=dupe.id,
        details={"into": keep.id},
    )
    return {"keep_id": keep.id, **result}


@router.post("/import")
async def import_patients(
    db: DB,
    user: StaffUser,
    file: UploadFile = File(...),
    mapping: str | None = Form(None),
    commit: bool = Form(False),
    include_possible: bool = Form(False),
):
    """Two steps with the same call: without `commit` it reports what would happen; with `commit` it does it."""
    data = await file.read()
    headers, rows = dedupe.read_table(file.filename or "", data)
    suggested = dedupe.suggest_mapping(headers)
    chosen = suggested
    if mapping:
        try:
            chosen = {
                k: (None if v in (None, "", -1) else int(v))
                for k, v in json.loads(mapping).items()
                if k in dedupe.FIELDS
            }
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, "The column mapping is not valid.") from exc
    if chosen.get("first_name") is None and chosen.get("full_name") is None:
        # Nothing to build a name from: let the person choose the columns before going further.
        return {
            "headers": headers,
            "mapping": suggested,
            "summary": None,
            "rows": [],
            "committed": False,
            "needs_mapping": True,
            "total": len(rows),
        }
    built = dedupe.build_rows(db, headers, rows, chosen)
    summary: dict[str, int] = {}
    for r in built:
        summary[r["status"]] = summary.get(r["status"], 0) + 1
    result = {
        "headers": headers,
        "mapping": chosen,
        "summary": summary,
        "total": len(built),
        "committed": False,
        "needs_mapping": False,
        "rows": [r for r in built if r["status"] != "new"][:200],
        "sample": [r["person"] for r in built if r["status"] == "new"][:8],
    }
    if not commit:
        return result
    branch = branch_svc.active(db, user)
    created = 0
    for r in built:
        if r["status"] == "new" or (r["status"] == "possible_duplicate" and include_possible):
            p = r["person"]
            patient = Patient(
                mrn=p["mrn"] or dedupe.next_mrn(db),
                first_name=p["first_name"],
                last_name=p["last_name"],
                date_of_birth=date.fromisoformat(p["date_of_birth"]) if p["date_of_birth"] else None,
                sex=p["sex"],
                phone=p["phone"],
                email=p["email"],
                address=p["address"],
                blood_group=p["blood_group"],
                notes=p["notes"],
                tags=["imported"],
                created_by=user.id,
                registered_branch_id=branch.id,
            )
            db.add(patient)
            db.flush()
            audit.record(
                db,
                user,
                "patient.create",
                f"Imported patient {patient.full_name} ({patient.mrn})",
                entity_type="patient",
                entity_id=patient.id,
                patient_id=patient.id,
                details={"import": file.filename},
                commit=False,
            )
            created += 1
    db.commit()
    audit.record(
        db,
        user,
        "patient.import",
        f"Imported {created} patients from {file.filename}",
        details={"created": created, "summary": summary},
    )
    result.update(committed=True, created=created)
    return result
