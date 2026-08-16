"""Feedback persistence (spec §81). `submit_feedback` upserts by (target_type,
target_id, user_id) — a clinician revising their reaction to the same answer updates
the existing row rather than accumulating duplicates for the same answer/user pair.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models.feedback import Feedback, FeedbackRating, FeedbackTarget


def _existing(db: DbSession, user_id: str, target_type: FeedbackTarget, target_id: str) -> Feedback | None:
    return db.scalar(
        select(Feedback).where(
            Feedback.target_type == target_type, Feedback.target_id == target_id, Feedback.user_id == user_id
        )
    )


def submit_feedback(
    db: DbSession,
    user_id: str,
    target_type: FeedbackTarget,
    target_id: str,
    rating: FeedbackRating,
    comment: str | None,
) -> Feedback:
    existing = _existing(db, user_id, target_type, target_id)
    if existing:
        existing.rating = rating
        existing.comment = comment
        db.commit()
        db.refresh(existing)
        return existing

    feedback = Feedback(target_type=target_type, target_id=target_id, user_id=user_id, rating=rating, comment=comment)
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def get_own_feedback(db: DbSession, user_id: str, target_type: FeedbackTarget, target_id: str) -> Feedback | None:
    return _existing(db, user_id, target_type, target_id)


def list_feedback(
    db: DbSession,
    *,
    target_type: FeedbackTarget | None = None,
    rating: FeedbackRating | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Feedback]:
    stmt = select(Feedback).order_by(Feedback.created_at.desc())
    if target_type is not None:
        stmt = stmt.where(Feedback.target_type == target_type)
    if rating is not None:
        stmt = stmt.where(Feedback.rating == rating)
    stmt = stmt.limit(max(1, min(limit, 500))).offset(max(0, offset))
    return list(db.scalars(stmt))
