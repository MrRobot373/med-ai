"""ORM model package.

Import every model module here so `Base.metadata` is fully populated before Alembic
autogenerate or `Base.metadata.create_all()` runs. Knowledge tables (documents,
document_versions) land in Phase 12 per the build plan.
"""

from app.models.allergy import Allergy
from app.models.chunk import Chunk
from app.models.citation import Citation
from app.models.condition import Condition
from app.models.conversation import Conversation
from app.models.encounter import Encounter
from app.models.ingestion_job import IngestionJob
from app.models.medication import Medication
from app.models.message import Message
from app.models.observation import Observation
from app.models.patient import Patient
from app.models.report import Report
from app.models.session import Session
from app.models.user import User

__all__ = [
    "Allergy",
    "Chunk",
    "Citation",
    "Condition",
    "Conversation",
    "Encounter",
    "IngestionJob",
    "Medication",
    "Message",
    "Observation",
    "Patient",
    "Report",
    "Session",
    "User",
]
