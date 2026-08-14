from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.user import UserRole


class LoginRequest(BaseModel):
    # Deliberately NOT pydantic's EmailStr here: it rejects reserved/special-use TLDs
    # such as `.local` (used by this project's own seeded demo accounts), and some
    # configurations perform a live DNS/MX lookup for deliverability — wrong for an
    # app required to work fully offline (spec §136). Login only needs to match an
    # existing user record, not prove the address is internet-deliverable; a light
    # shape check is all that belongs here.
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def _basic_email_shape(cls, value: str) -> str:
        value = value.strip()
        if value.count("@") != 1 or any(ch.isspace() for ch in value):
            raise ValueError("Enter a valid email address")
        local, _, domain = value.partition("@")
        if not local or "." not in domain:
            raise ValueError("Enter a valid email address")
        return value


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str
    role: UserRole
    active: bool
    last_login_at: datetime | None = None
