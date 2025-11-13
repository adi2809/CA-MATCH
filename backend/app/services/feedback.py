"""Helpers for summarising instructor feedback and normalising ratings."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from ..models import InstructorFeedback


@dataclass
class FeedbackSummary:
    course_id: int
    average_rating: Optional[float]
    review_count: int
    comments: List[str]


def normalize_rating(rating: int) -> float:
    """Convert a 1-5 rating scale into a 0-100 score."""

    bounded = max(1, min(5, rating))
    return (bounded / 5.0) * 100.0


def summarize_feedback_for_course(db: Session, course_id: int) -> FeedbackSummary:
    entries = (
        db.query(InstructorFeedback)
        .filter(InstructorFeedback.course_id == course_id)
        .all()
    )
    if not entries:
        return FeedbackSummary(course_id, None, 0, [])

    average = sum(entry.rating for entry in entries) / len(entries)
    comments = [entry.comments for entry in entries if entry.comments]
    return FeedbackSummary(course_id, average, len(entries), comments)
