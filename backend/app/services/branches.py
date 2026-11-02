"""Branch (site) access and the active branch of a signed-in person."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Branch, User, UserBranch

DEFAULT_CODE = "MAIN"


def ensure_default(db: Session, name: str = "Main clinic") -> Branch:
    b = db.scalars(select(Branch).where(Branch.is_default.is_(True))).first()
    if b is None:
        b = db.scalars(select(Branch).order_by(Branch.created_at)).first()
        if b is None:
            b = Branch(code=DEFAULT_CODE, name=name, is_default=True)
            db.add(b)
        else:
            b.is_default = True
        db.commit()
    return b


def accessible(db: Session, user: User) -> list[Branch]:
    """Active branches the person may work in. Administrators: all of them."""
    ensure_default(db)
    stmt = select(Branch).where(Branch.is_active.is_(True)).order_by(Branch.is_default.desc(), Branch.name)
    if user.role != "admin":
        ids = [r for (r,) in db.execute(select(UserBranch.branch_id).where(UserBranch.user_id == user.id))]
        stmt = stmt.where(Branch.id.in_(ids)) if ids else stmt.where(Branch.is_default.is_(True))
    return list(db.scalars(stmt))


def active(db: Session, user: User, requested: str | None = None) -> Branch:
    """The branch a request works in: the one asked for (if allowed), else the person's saved choice, else
    their first branch."""
    options = accessible(db, user)
    wanted = requested or (user.preferences or {}).get("branch_id")
    for b in options:
        if b.id == wanted:
            return b
    if requested:
        raise HTTPException(403, "You do not have access to that branch.")
    return options[0]


def assign(db: Session, user: User, branch_ids: list[str]) -> None:
    valid = {b.id for b in db.scalars(select(Branch).where(Branch.is_active.is_(True)))}
    chosen = [b for b in dict.fromkeys(branch_ids) if b in valid]
    for ub in db.scalars(select(UserBranch).where(UserBranch.user_id == user.id)):
        db.delete(ub)
    db.flush()
    for b in chosen:
        db.add(UserBranch(user_id=user.id, branch_id=b))


def ensure_membership(db: Session, user: User) -> None:
    """A new person starts in the default branch."""
    if user.role != "admin" and not db.scalar(select(UserBranch.branch_id).where(UserBranch.user_id == user.id)):
        db.add(UserBranch(user_id=user.id, branch_id=ensure_default(db).id))
