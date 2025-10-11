from __future__ import annotations

from io import StringIO
from typing import List

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..dependencies import get_current_admin
from ..models import Assignment, Course, StudentProfile, Track
from ..schemas import (
    AssignmentCreate,
    AssignmentDetails,
    AssignmentRead,
    CourseCreate,
    CourseRead,
    EmailPayload,
    MatchRequest,
    MatchResult,
)
from ..services.matching_engine import run_matching

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/courses", response_model=CourseRead)
def create_course(
    course_in: CourseCreate,
    db: Session = Depends(get_db),
    _: None = Depends(get_current_admin),
) -> Course:
    if db.query(Course).filter(Course.code == course_in.code).first():
        raise HTTPException(status_code=400, detail="Course already exists")
    course = Course(**course_in.dict())
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.get("/courses", response_model=List[CourseRead])
def list_courses(
    db: Session = Depends(get_db),
    _: None = Depends(get_current_admin),
) -> List[Course]:
    return db.query(Course).all()


@router.put("/courses/{course_id}", response_model=CourseRead)
def update_course(
    course_id: int,
    course_in: CourseCreate,
    db: Session = Depends(get_db),
    _: None = Depends(get_current_admin),
) -> Course:
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    for key, value in course_in.dict().items():
        setattr(course, key, value)
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.delete("/courses/{course_id}")
def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(get_current_admin),
) -> None:
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    db.delete(course)
    db.commit()


@router.post("/courses/import", response_model=List[CourseRead])
def import_courses(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: None = Depends(get_current_admin),
) -> List[Course]:
    contents = file.file.read().decode("utf-8")
    df = pd.read_csv(StringIO(contents))
    df.columns = [col.lower() for col in df.columns]
    required_columns = {
        "course code",
        "title",
        "instructor",
        "instructor email",
        "track",
        "vacancies",
        "grade threshold",
        "similar courses",
    }
    missing = required_columns - set(df.columns)
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing columns: {missing}")

    created: List[Course] = []
    for _, row in df.iterrows():
        track_value = row.get("track")
        track = Track(track_value) if pd.notna(track_value) else None

        existing = db.query(Course).filter(Course.code == row["course code"]).first()
        if existing:
            existing.title = row["title"]
            existing.instructor = row.get("instructor")
            existing.instructor_email = row.get("instructor email")
            existing.track = track
            existing.vacancies = int(row.get("vacancies", existing.vacancies or 0))
            existing.grade_threshold = row.get("grade threshold")
            existing.similar_courses = row.get("similar courses")
            created.append(existing)
        else:
            course = Course(
                code=row["course code"],
                title=row["title"],
                instructor=row.get("instructor"),
                instructor_email=row.get("instructor email"),
                track=track,
                vacancies=int(row.get("vacancies", 0)),
                grade_threshold=row.get("grade threshold"),
                similar_courses=row.get("similar courses"),
            )
            db.add(course)
            created.append(course)
    db.commit()
    return created


@router.post("/match", response_model=MatchResult)
def start_match(
    request: MatchRequest,
    db: Session = Depends(get_db),
    _: None = Depends(get_current_admin),
) -> MatchResult:
    assignments, skipped_students = run_matching(db, course_ids=request.course_ids)
    detailed_assignments: List[AssignmentDetails] = []
    for assignment in assignments:
        db.add(assignment)
    db.commit()
    assignment_ids = [assignment.id for assignment in assignments]
    if assignment_ids:
        persisted = (
            db.query(Assignment)
            .options(
                joinedload(Assignment.student).joinedload(StudentProfile.user),
                joinedload(Assignment.course),
            )
            .filter(Assignment.id.in_(assignment_ids))
            .all()
        )
        detailed_assignments = [_to_details(assignment) for assignment in persisted]
    return MatchResult(assignments=detailed_assignments, skipped_students=skipped_students)


@router.post("/assignments", response_model=AssignmentDetails)
def create_assignment(
    assignment_in: AssignmentCreate,
    db: Session = Depends(get_db),
    _: None = Depends(get_current_admin),
) -> AssignmentDetails:
    student = db.query(StudentProfile).filter(StudentProfile.id == assignment_in.student_id).first()
    course = db.query(Course).filter(Course.id == assignment_in.course_id).first()
    if not student or not course:
        raise HTTPException(status_code=404, detail="Student or course not found")
    if course.vacancies <= 0:
        raise HTTPException(status_code=400, detail="No vacancies left for course")

    course.vacancies -= 1
    assignment = Assignment(
        student_id=assignment_in.student_id,
        course_id=assignment_in.course_id,
        status=assignment_in.status,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return _to_details(assignment)


@router.get("/assignments", response_model=List[AssignmentDetails])
def list_assignments(
    db: Session = Depends(get_db),
    _: None = Depends(get_current_admin),
) -> List[AssignmentDetails]:
    assignments = (
        db.query(Assignment)
        .options(
            joinedload(Assignment.student).joinedload(StudentProfile.user),
            joinedload(Assignment.course),
        )
        .all()
    )
    return [_to_details(assignment) for assignment in assignments]


@router.post("/communications")
def compose_email(
    payload: EmailPayload,
    db: Session = Depends(get_db),
    _: None = Depends(get_current_admin),
) -> dict:
    assignments = (
        db.query(Assignment)
        .options(
            joinedload(Assignment.student).joinedload(StudentProfile.user),
            joinedload(Assignment.course),
        )
        .all()
    )
    recipients = []
    for assignment in assignments:
        student = assignment.student
        course = assignment.course
        if not student or not course or not student.user:
            continue
        recipients.append(
            {
                "student_name": student.full_name,
                "student_email": student.user.email,
                "instructor_email": course.instructor_email,
                "course_title": course.title,
            }
        )
    return {
        "subject": payload.subject,
        "message": payload.message,
        "recipients": recipients,
        "cc_instructors": payload.cc_instructors,
    }


def _to_details(assignment: Assignment) -> AssignmentDetails:
    student = assignment.student
    course = assignment.course
    user = student.user if student else None
    return AssignmentDetails(
        id=assignment.id,
        student_id=assignment.student_id,
        course_id=assignment.course_id,
        status=assignment.status,
        student_name=student.full_name if student else None,
        student_uni=user.uni if user else None,
        student_email=user.email if user else None,
        course_code=course.code if course else None,
        course_title=course.title if course else None,
        instructor=course.instructor if course else None,
        instructor_email=course.instructor_email if course else None,
    )

