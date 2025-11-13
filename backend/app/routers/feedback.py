from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import Assignment, InstructorFeedback, User, UserRole
from ..schemas import (
    InstructorFeedbackCreate,
    InstructorFeedbackRead,
    InstructorFeedbackSummary,
)
from ..services.feedback import summarize_feedback_for_course

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/", response_model=InstructorFeedbackRead, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    feedback_in: InstructorFeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InstructorFeedback:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only instructors can submit feedback")

    assignment = db.query(Assignment).filter(Assignment.id == feedback_in.assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if assignment.student_id != feedback_in.student_id or assignment.course_id != feedback_in.course_id:
        raise HTTPException(status_code=400, detail="Assignment does not match provided student/course")

    existing = (
        db.query(InstructorFeedback)
        .filter(InstructorFeedback.assignment_id == assignment.id)
        .first()
    )
    if existing:
        existing.rating = feedback_in.rating
        existing.comments = feedback_in.comments
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    feedback = InstructorFeedback(
        assignment_id=assignment.id,
        student_id=assignment.student_id,
        course_id=assignment.course_id,
        rating=feedback_in.rating,
        comments=feedback_in.comments,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


@router.get("/course/{course_id}", response_model=InstructorFeedbackSummary)
def course_feedback_summary(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InstructorFeedbackSummary:
    if current_user.role not in {UserRole.ADMIN, UserRole.STUDENT}:
        raise HTTPException(status_code=403, detail="Not authorised")

    summary = summarize_feedback_for_course(db, course_id)
    return InstructorFeedbackSummary(
        course_id=summary.course_id,
        average_rating=summary.average_rating,
        review_count=summary.review_count,
        comments=summary.comments,
    )
