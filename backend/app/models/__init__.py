"""ORM model package.

Import every model module here so `Base.metadata` is fully populated before Alembic
autogenerate or `Base.metadata.create_all()` runs. Phase 01 only defines `users` and
`sessions` — enough to prove the migration/auth-storage path end-to-end. Patient,
encounter, report, and knowledge tables land in Phase 04+ per the build plan.
"""

from app.models.session import Session
from app.models.user import User

__all__ = ["Session", "User"]
