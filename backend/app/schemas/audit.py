from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator

from app.models.audit_log import AuditAction, AuditOutcome


class AuditLogOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    user_id: str | None
    user_email: str | None
    action: AuditAction
    outcome: AuditOutcome
    object_type: str | None
    object_id: str | None
    detail: dict[str, Any] | None
    created_at: datetime

    @field_validator("detail", mode="before")
    @classmethod
    def _parse_json(cls, value: Any) -> Any:
        if isinstance(value, str):
            return json.loads(value)
        return value
