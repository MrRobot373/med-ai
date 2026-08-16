from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.feedback import FeedbackRating, FeedbackTarget


class FeedbackCreate(BaseModel):
    target_type: FeedbackTarget
    target_id: str
    rating: FeedbackRating
    comment: str | None = None


class FeedbackOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    target_type: FeedbackTarget
    target_id: str
    user_id: str
    rating: FeedbackRating
    comment: str | None
    created_at: datetime
    updated_at: datetime
