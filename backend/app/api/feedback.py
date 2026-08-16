"""Feedback endpoints (spec §81: every AI answer can be rated Helpful/Not Helpful/
Incorrect/Missing Evidence/Outdated Evidence/Wrong Patient Context). Any authenticated
role may submit feedback — reacting to an AI answer isn't "modifying patient
information" (spec §18's viewer restriction is about clinical data, not evaluation
metadata about the AI itself). Reviewing the full feedback stream is admin-only, the
same "look back at what happened" capability as `/api/audit` (spec §18 "Review
audits").
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbDep
from app.auth.dependencies import AdminUser, CurrentUser
from app.models.clinical_module_run import ClinicalModuleRun
from app.models.conversation import Conversation
from app.models.feedback import FeedbackRating, FeedbackTarget
from app.models.message import Message
from app.schemas.feedback import FeedbackCreate, FeedbackOut
from app.services import feedback as feedback_service

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


def _assert_target_visible(db: DbDep, current_user_id: str, target_type: FeedbackTarget, target_id: str) -> None:
    if target_type == FeedbackTarget.MESSAGE:
        message = db.get(Message, target_id)
        if message is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        conversation = db.get(Conversation, message.conversation_id)
        # Conversations are private to their owner (see api/chat.py) — feedback on a
        # message follows the same visibility rule as reading the conversation itself.
        if conversation is None or conversation.user_id != current_user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    else:
        # ClinicalModuleRun drafts are chart-visible to any authenticated clinician
        # (Phase 10's own convention) — no ownership check beyond "it exists."
        run = db.get(ClinicalModuleRun, target_id)
        if run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinical module run not found")


@router.post("", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
def submit_feedback(payload: FeedbackCreate, db: DbDep, current_user: CurrentUser) -> FeedbackOut:
    _assert_target_visible(db, current_user.id, payload.target_type, payload.target_id)
    feedback = feedback_service.submit_feedback(
        db, current_user.id, payload.target_type, payload.target_id, payload.rating, payload.comment
    )
    return FeedbackOut.model_validate(feedback)


@router.get("/mine", response_model=FeedbackOut | None)
def get_my_feedback(
    db: DbDep, current_user: CurrentUser, target_type: FeedbackTarget, target_id: str
) -> FeedbackOut | None:
    feedback = feedback_service.get_own_feedback(db, current_user.id, target_type, target_id)
    return FeedbackOut.model_validate(feedback) if feedback else None


@router.get("", response_model=list[FeedbackOut])
def list_all_feedback(
    db: DbDep,
    _admin: AdminUser,
    target_type: FeedbackTarget | None = None,
    rating: FeedbackRating | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[FeedbackOut]:
    rows = feedback_service.list_feedback(db, target_type=target_type, rating=rating, limit=limit, offset=offset)
    return [FeedbackOut.model_validate(row) for row in rows]
