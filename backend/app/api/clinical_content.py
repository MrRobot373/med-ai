"""Clinical content review: the self-test, and sign-off by a named clinical lead and pharmacist."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, AdminUser, ClinicalUser
from app.clinical import content, testbank
from app.core.security import verify_password
from app.db import utcnow
from app.models import AppSetting, ContentSignoff
from app.services import audit, printing

router = APIRouter(prefix="/api/clinical-content", tags=["clinical content"])


def status_for(db, key: str) -> dict:
    area = content.AREAS[key]
    h = content.content_hash(area)
    rows = list(
        db.scalars(select(ContentSignoff).where(ContentSignoff.area == key).order_by(ContentSignoff.signed_at.desc()))
    )
    live = [r for r in rows if r.revoked_at is None]
    current = [r for r in live if r.content_hash == h]
    have = {r.role for r in current}
    missing = [r for r in area.roles if r not in have]
    if not missing:
        state = "signed"
    elif current:
        state = "partial"
    elif live:
        state = "changed"
    else:
        state = "unsigned"

    def out(r: ContentSignoff) -> dict:
        return {
            "id": r.id,
            "role": r.role,
            "role_label": content.ROLE_LABEL[r.role],
            "name": r.name,
            "registration_no": r.registration_no,
            "registration_council": r.registration_council,
            "statement": r.statement,
            "signed_at": r.signed_at,
            "tests": f"{r.tests_passed}/{r.tests_total}",
            "current": r.content_hash == h and r.revoked_at is None,
            "revoked": r.revoked_at is not None,
            "revoked_reason": r.revoked_reason,
        }

    return {
        "key": key,
        "label": area.label,
        "what": area.what,
        "roles": [{"role": r, "label": content.ROLE_LABEL[r]} for r in area.roles],
        "content_hash": h,
        "status": state,
        "missing": [{"role": r, "label": content.ROLE_LABEL[r]} for r in missing],
        "signoffs": [out(r) for r in rows[:12]],
    }


def overall(db) -> str:
    states = [status_for(db, k)["status"] for k in content.AREAS]
    return (
        "signed"
        if all(s == "signed" for s in states)
        else ("unsigned" if all(s == "unsigned" for s in states) else "incomplete")
    )


def _selftest(db) -> dict:
    r = testbank.run_all()
    db.merge(
        AppSetting(
            key="selftest",
            value={"at": utcnow().isoformat(), "passed": r["passed"], "total": r["total"], "bank_hash": r["bank_hash"]},
            updated_at=utcnow(),
        )
    )
    db.commit()
    return r


@router.get("")
def overview(db: DB, _: ClinicalUser):
    last = db.get(AppSetting, "selftest")
    return {
        "areas": [status_for(db, k) for k in content.AREAS],
        "selftest": last.value if last else None,
        "overall": overall(db),
    }


@router.get("/evaluation")
def latest_evaluation(_: ClinicalUser):
    """The most recent quality measurement (run with: python -m app.cli eval)."""
    from app.evals import runner

    return runner.latest()


@router.post("/selftest")
def selftest(db: DB, user: ClinicalUser):
    r = _selftest(db)
    audit.record(
        db,
        user,
        "clinical.selftest",
        f"Ran the clinical test-bank: {r['passed']} of {r['total']} passed",
        details={"failed": [c["id"] for c in r["cases"] if not c["ok"]]},
    )
    return r


class SignIn(BaseModel):
    role: str
    password: str = Field(min_length=1, max_length=200)
    statement: str | None = Field(None, max_length=1000)


@router.post("/{key}/sign")
def sign(key: str, body: SignIn, db: DB, user: ClinicalUser):
    area = content.AREAS.get(key)
    if area is None:
        raise HTTPException(404, "Unknown content area")
    if body.role not in area.roles:
        raise HTTPException(422, f"This area is signed by: {', '.join(content.ROLE_LABEL[r] for r in area.roles)}.")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(403, "Your password is not correct. A signature needs it.")
    if not user.registration_no:
        raise HTTPException(
            422, "Add your professional registration number to your profile first. It is recorded with your signature."
        )
    st = status_for(db, key)
    h = st["content_hash"]
    already = [s for s in st["signoffs"] if s["current"]]
    if any(s["role"] == body.role for s in already):
        raise HTTPException(409, f"This version has already been signed as {content.ROLE_LABEL[body.role]}.")
    if any(db.get(ContentSignoff, s["id"]).user_id == user.id for s in already):
        raise HTTPException(
            409, "A different person must sign for the other role: one person cannot approve their own review."
        )
    result = testbank.run_all()
    if key == "formulary" and not result["ok"]:
        raise HTTPException(
            422,
            f"{result['failed']} clinical test case(s) are failing, so the rules cannot be signed off. Open 'Run the clinical tests'.",
        )
    statement = (body.statement or "").strip() or (
        f"I have reviewed the {area.label.lower()} in this version and consider them appropriate for use in clinical practice in this clinic."
    )
    row = ContentSignoff(
        area=key,
        content_hash=h,
        role=body.role,
        user_id=user.id,
        name=printing.doctor_dict(user)["name"],
        registration_no=user.registration_no,
        registration_council=user.registration_council,
        statement=statement,
        tests_passed=result["passed"] if key == "formulary" else 0,
        tests_total=result["total"] if key == "formulary" else 0,
    )
    db.add(row)
    db.commit()
    audit.record(
        db,
        user,
        "clinical.signoff",
        f"Signed off {area.label} as {content.ROLE_LABEL[body.role]}",
        entity_type="content",
        entity_id=key,
        details={"content_hash": h, "role": body.role},
    )
    return status_for(db, key)


class RevokeIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/signoffs/{signoff_id}/revoke")
def revoke(signoff_id: str, body: RevokeIn, db: DB, admin: AdminUser):
    row = db.get(ContentSignoff, signoff_id)
    if row is None or row.revoked_at is not None:
        raise HTTPException(404, "Sign-off not found")
    row.revoked_at, row.revoked_reason = utcnow(), body.reason
    db.commit()
    audit.record(
        db,
        admin,
        "clinical.signoff_revoke",
        f"Revoked the sign-off of {row.name} for {row.area}: {body.reason}",
        entity_type="content",
        entity_id=row.area,
    )
    return status_for(db, row.area)
