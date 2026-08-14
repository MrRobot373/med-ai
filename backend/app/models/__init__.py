"""ORM model package.

Import every model module here so `Base.metadata` is fully populated before Alembic
autogenerate or `Base.metadata.create_all()` runs. Report, observation, and knowledge
tables land in Phase 05+ per the build plan.
"""

from app.models.allergy import Allergy
from app.models.condition import Condition
from app.models.encounter import Encounter
from app.models.medication import Medication
from app.models.patient import Patient
from app.models.session import Session
from app.models.user import User

__all__ = ["Allergy", "Condition", "Encounter", "Medication", "Patient", "Session", "User"]
