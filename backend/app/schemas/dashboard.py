"""Overview dashboard summary schema — spec §22."""

from __future__ import annotations

from pydantic import BaseModel


class DashboardSummaryOut(BaseModel):
    active_patients: int
    total_reports: int
    total_ai_analyses: int
