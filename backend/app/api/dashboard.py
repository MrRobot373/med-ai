"""Overview dashboard summary (spec §22): real, live-queried counts — never hardcoded,
never a "coming soon" placeholder once the feature it describes actually exists.

`frontend/src/components/DashboardSnapshot.tsx` originally shipped in Phase 01/02
before reports (Phase 05) or any AI-generated output (Phase 08-10) existed, so it
honestly said "not available yet". Phase 16's live UI review found that placeholder
was never replaced once those phases landed — it was still claiming Reports "arrives
in Phase 05" and AI analyses "arrives in Phases 08-10" against a real running app that
already has both. This endpoint gives the frontend real numbers to show instead.
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DbDep
from app.auth.dependencies import CurrentUser
from app.models.clinical_module_run import ClinicalModuleRun
from app.models.message import Message, MessageRole
from app.models.patient import Patient
from app.models.report import Report
from app.models.vision_analysis import VisionAnalysis
from app.schemas.dashboard import DashboardSummaryOut

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard/summary", response_model=DashboardSummaryOut)
def get_dashboard_summary(db: DbDep, _user: CurrentUser) -> DashboardSummaryOut:
    active_patients = db.scalar(select(func.count()).select_from(Patient).where(Patient.archived.is_(False))) or 0
    total_reports = db.scalar(select(func.count()).select_from(Report).where(Report.archived.is_(False))) or 0

    # "AI analyses" — every distinct real AI-generated clinical output: assistant chat
    # replies, clinical module runs (summary/SOAP/entities/differential/comparison),
    # and vision analyses. Deliberately not just one of these — a clinician asking "has
    # the AI done anything for this practice" means all of it, not one feature's count.
    assistant_messages = db.scalar(select(func.count()).select_from(Message).where(Message.role == MessageRole.ASSISTANT)) or 0
    module_runs = db.scalar(select(func.count()).select_from(ClinicalModuleRun)) or 0
    vision_analyses = db.scalar(select(func.count()).select_from(VisionAnalysis)) or 0

    return DashboardSummaryOut(
        active_patients=active_patients,
        total_reports=total_reports,
        total_ai_analyses=assistant_messages + module_runs + vision_analyses,
    )
