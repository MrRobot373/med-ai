"""Branches (sites) of the organisation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import DB, AdminUser, CurrentUser
from app.models import Appointment, Branch, UserBranch
from app.services import audit
from app.services import branches as svc

router = APIRouter(prefix="/api", tags=["organisation"])


class BranchIn(BaseModel):
    code: str = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)
    address: str | None = Field(None, max_length=600)
    phone: str | None = Field(None, max_length=60)
    email: str | None = Field(None, max_length=200)
    registration: str | None = Field(None, max_length=120)
    footer_text: str | None = Field(None, max_length=300)


class BranchUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    address: str | None = Field(None, max_length=600)
    phone: str | None = Field(None, max_length=60)
    email: str | None = Field(None, max_length=200)
    registration: str | None = Field(None, max_length=120)
    footer_text: str | None = Field(None, max_length=300)
    is_active: bool | None = None
    is_default: bool | None = None


def out(db, b: Branch, with_counts: bool = False) -> dict:
    d = {
        "id": b.id,
        "code": b.code,
        "name": b.name,
        "address": b.address,
        "phone": b.phone,
        "email": b.email,
        "registration": b.registration,
        "footer_text": b.footer_text,
        "is_default": b.is_default,
        "is_active": b.is_active,
    }
    if with_counts:
        d["staff"] = db.scalar(select(func.count()).select_from(UserBranch).where(UserBranch.branch_id == b.id)) or 0
        d["appointments"] = (
            db.scalar(select(func.count()).select_from(Appointment).where(Appointment.branch_id == b.id)) or 0
        )
    return d


@router.get("/branches")
def list_branches(db: DB, user: CurrentUser, all: bool = False):
    if all and user.role == "admin":
        svc.ensure_default(db)
        rows = db.scalars(select(Branch).order_by(Branch.is_default.desc(), Branch.name)).all()
        return [out(db, b, with_counts=True) for b in rows]
    return [out(db, b) for b in svc.accessible(db, user)]


@router.post("/branches", status_code=201)
def create_branch(body: BranchIn, db: DB, admin: AdminUser):
    from app.services import licensing

    code = body.code.upper()
    if db.scalar(select(Branch).where(Branch.code == code)):
        raise HTTPException(409, "A branch with this code already exists.")
    licensing.assert_can_add_branch(db)
    b = Branch(code=code, **body.model_dump(exclude={"code"}))
    db.add(b)
    db.commit()
    audit.record(db, admin, "branch.create", f"Added branch {b.name}", entity_type="branch", entity_id=b.id)
    return out(db, b, with_counts=True)


@router.patch("/branches/{branch_id}")
def update_branch(branch_id: str, body: BranchUpdate, db: DB, admin: AdminUser):
    b = db.get(Branch, branch_id)
    if b is None:
        raise HTTPException(404, "Branch not found")
    changes = body.model_dump(exclude_unset=True)
    if changes.get("is_active") is False and b.is_default:
        raise HTTPException(400, "The main branch cannot be deactivated. Make another branch the main one first.")
    if changes.get("is_default") is True:
        for other in db.scalars(select(Branch).where(Branch.is_default.is_(True))):
            other.is_default = False
        changes["is_active"] = True
    if changes.get("is_default") is False and b.is_default:
        raise HTTPException(400, "Choose another branch as the main one instead.")
    for k, v in changes.items():
        setattr(b, k, v)
    db.commit()
    audit.record(
        db, admin, "branch.update", f"Updated branch {b.name}", entity_type="branch", entity_id=b.id, details=changes
    )
    return out(db, b, with_counts=True)
