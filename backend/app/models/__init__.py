"""ORM model package.

Import every model module here so `Base.metadata` is fully populated before Alembic
autogenerate or `Base.metadata.create_all()` runs.
"""

from app.models.allergy import Allergy
from app.models.audit_log import AuditLog
from app.models.chunk import Chunk
from app.models.citation import Citation
from app.models.clinical_module_run import ClinicalModuleRun
from app.models.condition import Condition
from app.models.conversation import Conversation
from app.models.encounter import Encounter
from app.models.feedback import Feedback
from app.models.ingestion_job import IngestionJob
from app.models.knowledge_document import KnowledgeDocument, KnowledgeDocumentVersion
from app.models.medication import Medication
from app.models.message import Message
from app.models.observation import Observation
from app.models.patient import Patient
from app.models.report import Report
from app.models.session import Session
from app.models.user import User
from app.models.vision_analysis import VisionAnalysis
from app.models.web_cache import WebCacheEntry

__all__ = [
    "Allergy",
    "AuditLog",
    "Chunk",
    "Citation",
    "ClinicalModuleRun",
    "Condition",
    "Conversation",
    "Encounter",
    "Feedback",
    "IngestionJob",
    "KnowledgeDocument",
    "KnowledgeDocumentVersion",
    "Medication",
    "Message",
    "Observation",
    "Patient",
    "Report",
    "Session",
    "User",
    "VisionAnalysis",
    "WebCacheEntry",
]
