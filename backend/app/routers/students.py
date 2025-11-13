from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..dependencies import get_current_user
from ..database import get_db
from ..models import Course, StudentCoursePreference, StudentProfile, Track, User
from ..schemas import (
    CourseRead,
    StudentCoursePreferenceCreate,
    StudentCoursePreferenceRead,
    StudentProfileCreate,
    StudentProfileRead,
)
from ..services.document_ocr import extract_text_from_document

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/me", response_model=StudentProfileRead)
def read_profile(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> StudentProfileRead:
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return _to_schema(profile)


@router.put("/me", response_model=StudentProfileRead)
def update_profile(
    profile_in: StudentProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StudentProfileRead:
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        profile = StudentProfile(user_id=current_user.id)
        db.add(profile)

    profile.full_name = profile_in.full_name
    profile.degree_program = profile_in.degree_program
    profile.level_of_study = profile_in.level_of_study
    interest_values = [interest.value for interest in (profile_in.interests or [])]
    profile.interests = ",".join(interest_values)
    profile.resume_path = profile_in.resume_path
    profile.transcript_path = profile_in.transcript_path
    profile.resume_text = _extract_or_clear(profile_in.resume_path)
    profile.transcript_text = _extract_or_clear(profile_in.transcript_path)
    profile.photo_url = profile_in.photo_url
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _to_schema(profile)


@router.post("/preferences", response_model=List[StudentCoursePreferenceRead])
def set_preferences(
    preferences: List[StudentCoursePreferenceCreate],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[StudentCoursePreference]:
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    db.query(StudentCoursePreference).filter(
        StudentCoursePreference.student_id == profile.id
    ).delete(synchronize_session=False)

    saved: List[StudentCoursePreference] = []
    for pref_in in preferences:
        course = db.query(Course).filter(Course.id == pref_in.course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail=f"Course {pref_in.course_id} not found")
        if pref_in.track and course.track and pref_in.track != course.track:
            raise HTTPException(status_code=400, detail="Track mismatch for course")

        preference = StudentCoursePreference(
            student_id=profile.id,
            course_id=course.id,
            rank=pref_in.rank,
            track=pref_in.track or course.track,
            faculty_requested=pref_in.faculty_requested,
            grade_in_course=pref_in.grade_in_course,
            basket_grade_average=pref_in.basket_grade_average,
        )
        db.add(preference)
        saved.append(preference)

    db.commit()
    db.refresh(profile)
    return saved


@router.get("/preferences", response_model=List[StudentCoursePreferenceRead])
def get_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[StudentCoursePreference]:
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    preferences = (
        db.query(StudentCoursePreference)
        .filter(StudentCoursePreference.student_id == profile.id)
        .order_by(StudentCoursePreference.rank.asc())
        .all()
    )
    return preferences


@router.get("/courses", response_model=List[CourseRead])
def list_courses(db: Session = Depends(get_db)) -> List[CourseRead]:
    courses = db.query(Course).all()
    return courses


def _to_schema(profile: StudentProfile) -> StudentProfileRead:
    interests = (
        [Track(interest) for interest in profile.interests.split(",") if interest]
        if profile.interests
        else []
    )
    return StudentProfileRead(
        id=profile.id,
        user_id=profile.user_id,
        full_name=profile.full_name,
        degree_program=profile.degree_program,
        level_of_study=profile.level_of_study,
        interests=interests,
        resume_path=profile.resume_path,
        transcript_path=profile.transcript_path,
        photo_url=profile.photo_url,
        resume_text=profile.resume_text,
        transcript_text=profile.transcript_text,
    )


def _extract_or_clear(path: str | None) -> str | None:
    if not path:
        return None
    try:
        text = extract_text_from_document(path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return text

