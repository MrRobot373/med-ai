"""Organisation structure: branches (sites) of one clinic or hospital group.

One installation serves one organisation. Branches share a single patient index (so a patient seen at
two sites has one chart) but have their own day list, letterhead details and staff assignments."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin
from app.models._ids import new_id


class Branch(TimestampMixin, Base):
    __tablename__ = "branches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(20), unique=True)  # short, appears in numbering: "MAIN", "BANER"
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(60))
    email: Mapped[str | None] = mapped_column(String(200))
    registration: Mapped[str | None] = mapped_column(String(120))  # the clinic's own registration number
    footer_text: Mapped[str | None] = mapped_column(String(300))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UserBranch(Base):
    __tablename__ = "user_branches"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"), primary_key=True)
