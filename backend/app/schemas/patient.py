from __future__ import annotations

from datetime import UTC, date, datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.patient import Sex


def _calculate_age(dob: date) -> int:
    today = datetime.now(UTC).date()
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return years


class PatientCreate(BaseModel):
    # mrn is optional on create — the service generates one if omitted, since most
    # demo/quick-add flows don't have a real MRN registry to pull from.
    mrn: str | None = Field(default=None, max_length=64)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    preferred_name: str | None = Field(default=None, max_length=100)
    date_of_birth: date
    sex: Sex
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class PatientUpdate(BaseModel):
    """All fields optional — PATCH semantics, only supplied fields are changed."""

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    preferred_name: str | None = Field(default=None, max_length=100)
    date_of_birth: date | None = None
    sex: Sex | None = None
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    mrn: str
    first_name: str
    last_name: str
    preferred_name: str | None
    date_of_birth: date
    sex: Sex
    phone: str | None
    email: str | None
    notes: str | None
    synthetic: bool
    archived: bool
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def age(self) -> int:
        return _calculate_age(self.date_of_birth)


class PatientListItem(BaseModel):
    """Condensed shape for the patient search/list view (spec §23 card) — includes a
    few derived fields (age, last visit, active condition names) so the frontend
    doesn't have to make N follow-up requests per card."""

    id: str
    mrn: str
    first_name: str
    last_name: str
    preferred_name: str | None
    sex: Sex
    date_of_birth: date
    synthetic: bool
    archived: bool
    last_encounter_at: datetime | None
    active_condition_names: list[str]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def age(self) -> int:
        return _calculate_age(self.date_of_birth)
