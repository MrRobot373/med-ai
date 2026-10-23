from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Auth / users -----------------------------------------------------------
class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(ORM):
    id: str
    email: str
    full_name: str
    title: str | None
    specialty: str | None
    role: str
    is_active: bool
    preferences: dict
    last_login_at: datetime | None
    created_at: datetime


class ProfileIn(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=200)
    title: str | None = Field(None, max_length=80)
    specialty: str | None = Field(None, max_length=120)


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


class UserCreate(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+$", max_length=255)
    full_name: str = Field(min_length=1, max_length=200)
    title: str | None = None
    specialty: str | None = None
    role: Literal["admin", "clinician", "viewer"] = "clinician"
    password: str = Field(min_length=8, max_length=200)


class UserUpdate(BaseModel):
    full_name: str | None = None
    title: str | None = None
    specialty: str | None = None
    role: Literal["admin", "clinician", "viewer"] | None = None
    is_active: bool | None = None


class ResetPasswordIn(BaseModel):
    new_password: str = Field(min_length=8, max_length=200)


# ---- Patients ---------------------------------------------------------------
Sex = Literal["male", "female", "other", "unknown"]


class PatientIn(BaseModel):
    mrn: str = Field(min_length=1, max_length=64)
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    date_of_birth: date | None = None
    sex: Sex = "unknown"
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    blood_group: str | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)


class PatientUpdate(BaseModel):
    mrn: str | None = Field(None, min_length=1, max_length=64)
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    sex: Sex | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    blood_group: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    status: Literal["active", "archived"] | None = None


class PatientOut(ORM):
    id: str
    mrn: str
    first_name: str
    last_name: str
    full_name: str
    date_of_birth: date | None
    age: int | None = None
    sex: str
    phone: str | None
    email: str | None
    address: str | None
    blood_group: str | None
    notes: str | None
    tags: list[str]
    status: str
    synthetic: bool
    created_at: datetime
    updated_at: datetime


class PatientListItem(PatientOut):
    active_conditions: list[str] = []
    last_encounter_at: datetime | None = None
    open_alerts: int = 0
    document_count: int = 0


class ConditionIn(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    code: str | None = None
    status: Literal["active", "resolved", "inactive", "suspected"] = "active"
    onset_date: date | None = None
    notes: str | None = None
    encounter_id: str | None = None


class ConditionOut(ORM, ConditionIn):
    id: str
    patient_id: str
    created_at: datetime


class AllergyIn(BaseModel):
    substance: str = Field(min_length=1, max_length=200)
    reaction: str | None = None
    severity: Literal["mild", "moderate", "severe", "unknown"] = "unknown"
    status: Literal["active", "inactive", "refuted"] = "active"
    notes: str | None = None


class AllergyOut(ORM, AllergyIn):
    id: str
    patient_id: str
    created_at: datetime


class MedicationIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    dose: str | None = None
    route: str | None = None
    frequency: str | None = None
    indication: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: Literal["active", "stopped", "on_hold"] = "active"
    notes: str | None = None
    encounter_id: str | None = None


class MedicationOut(ORM, MedicationIn):
    id: str
    patient_id: str
    source: str
    source_document_id: str | None
    created_at: datetime


class EncounterIn(BaseModel):
    type: Literal["outpatient", "inpatient", "emergency", "telehealth", "follow_up", "procedure"] = "outpatient"
    status: Literal["planned", "in_progress", "completed", "cancelled"] = "in_progress"
    started_at: datetime | None = None
    ended_at: datetime | None = None
    reason: str | None = None
    notes: str | None = None
    vitals: dict[str, Any] = Field(default_factory=dict)


class EncounterOut(ORM):
    id: str
    patient_id: str
    type: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    reason: str | None
    notes: str | None
    vitals: dict
    clinician_id: str | None
    created_at: datetime


class ObservationIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    code: str | None = None
    value_num: float | None = None
    value_text: str | None = None
    unit: str | None = None
    ref_low: float | None = None
    ref_high: float | None = None
    observed_at: datetime | None = None


class ObservationOut(ORM):
    id: str
    patient_id: str
    document_id: str | None
    name: str
    code: str
    value_num: float | None
    value_text: str | None
    unit: str | None
    ref_low: float | None
    ref_high: float | None
    ref_text: str | None
    flag: str | None
    observed_at: datetime
    source_page: int | None
    source_excerpt: str | None
    method: str
    acknowledged: bool


# ---- Documents --------------------------------------------------------------
class DocumentOut(ORM):
    id: str
    scope: str
    patient_id: str | None
    encounter_id: str | None
    title: str
    filename: str
    mime_type: str
    size_bytes: int
    kind: str
    domain: str | None
    source_org: str | None
    version: str | None
    document_date: date | None
    status: str
    is_active: bool
    error: str | None
    identity_status: str
    identity_detail: str | None
    review_status: str
    page_count: int
    chunk_count: int
    extraction: dict
    created_at: datetime
    updated_at: datetime


class DocumentUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    kind: str | None = None
    domain: str | None = None
    source_org: str | None = None
    version: str | None = None
    document_date: date | None = None
    review_status: Literal["pending", "reviewed"] | None = None
    identity_status: Literal["match", "mismatch", "unverified", "confirmed"] | None = None
    is_active: bool | None = None


class ChunkOut(ORM):
    id: str
    ordinal: int
    page: int | None
    section: str | None
    text: str
    token_count: int


# ---- Chat / AI --------------------------------------------------------------
class ConversationIn(BaseModel):
    patient_id: str | None = None
    title: str | None = None
    use_web: bool = False


class ConversationUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    pinned: bool | None = None
    use_web: bool | None = None


class ConversationOut(ORM):
    id: str
    patient_id: str | None
    scope: str
    title: str
    pinned: bool
    use_web: bool
    created_at: datetime
    updated_at: datetime


class AskIn(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class FeedbackIn(BaseModel):
    rating: Literal["up", "down"] | None
    note: str | None = Field(None, max_length=2000)


class ToolRunIn(BaseModel):
    patient_id: str | None = None
    encounter_id: str | None = None
    document_id: str | None = None
    prior_document_id: str | None = None
    current_document_id: str | None = None
    presentation: str | None = None
    question: str | None = None
    domains: list[str] | None = None
    extra_notes: str | None = None


class AIRunOut(ORM):
    id: str
    tool: str
    patient_id: str | None
    encounter_id: str | None
    input: dict
    output: dict | None
    citations: list
    status: str
    error: str | None
    model: str | None
    latency_ms: int | None
    created_at: datetime
    reviewed_at: datetime | None


class ReviewIn(BaseModel):
    decision: Literal["accepted", "discarded", "draft"]


class ResearchIn(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    patient_id: str | None = None
    sources: list[str] | None = None
    synthesize: bool = True


class RetrievalTestIn(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    patient_id: str | None = None
    include_knowledge: bool = True
    domains: list[str] | None = None
