"""FastAPI-layer auth dependencies — cookie extraction, current-user resolution, and
role-based authorization (spec §18). Kept separate from app/auth/service.py so the
session-validation logic itself stays testable without spinning up FastAPI.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.api.deps import DbDep, SettingsDep
from app.auth.service import get_user_by_session_token
from app.models.user import User, UserRole


def get_current_user(request: Request, db: DbDep, settings: SettingsDep) -> User:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user = get_user_by_session_token(db, raw_token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*allowed_roles: UserRole):
    """Usage: `current_user: User = Depends(require_role(UserRole.ADMIN))`. Returns a
    dependency rather than being one directly, since it needs to close over which
    roles are allowed for this particular route."""

    def dependency(user: CurrentUser) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role.value}' is not permitted to perform this action",
            )
        return user

    return dependency


# Shared by every router with clinician-write endpoints (patients, encounters, reports,
# ...) — spec §18: only admin/doctor can modify clinical data, viewer is read-only. A
# single definition here means every write route enforces the exact same role set.
WriteUser = Annotated[User, Depends(require_role(UserRole.ADMIN, UserRole.DOCTOR))]

# Knowledge Administration (Phase 12, spec §18): "Manage knowledge base" is listed only
# under Admin's permissions — Doctor's list is patient/clinical-care actions, not
# curating the shared medical_knowledge base every patient's retrieval draws from.
# Gates the entire /api/knowledge router, both reads and writes.
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]
