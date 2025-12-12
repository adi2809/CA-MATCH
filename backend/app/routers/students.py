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
        # if pref_in.track and course.track and pref_in.track != course.track:
        #     raise HTTPException(status_code=400, detail="Track mismatch for course")

        preference = StudentCoursePreference(
        student_id=profile.id,
        course_id=course.id,
        rank=pref_in.rank,
        # track=course.track,  # Just use the course's track
    )

        db.add(preference)
        saved.append(preference)

    db.commit()
    db.refresh(profile)
    return saved


@router.post("/preferences/add", response_model=StudentCoursePreferenceRead)
def add_single_preference(
    preference: StudentCoursePreferenceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a single course preference without replacing existing ones"""
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Please complete your profile first.")

    # Check if course exists
    course = db.query(Course).filter(Course.id == preference.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail=f"Course not found")

    # Check if already applied to this course
    existing_course = db.query(StudentCoursePreference).filter(
        StudentCoursePreference.student_id == profile.id,
        StudentCoursePreference.course_id == preference.course_id
    ).first()
    
    if existing_course:
        raise HTTPException(status_code=400, detail="You have already applied to this course")

    # Check if rank is already used by another application
    existing_rank = db.query(StudentCoursePreference).filter(
        StudentCoursePreference.student_id == profile.id,
        StudentCoursePreference.rank == preference.rank
    ).first()
    
    if existing_rank:
        # Get the course code for the conflicting application
        conflicting_course = db.query(Course).filter(Course.id == existing_rank.course_id).first()
        raise HTTPException(
            status_code=400, 
            detail=f"Rank {preference.rank} is already used for {conflicting_course.code if conflicting_course else 'another course'}. Please choose a different rank."
        )

    # Create new preference
    new_preference = StudentCoursePreference(
        student_id=profile.id,
        course_id=course.id,
        rank=preference.rank,
    )
    db.add(new_preference)
    db.commit()
    db.refresh(new_preference)
    
    return {
        "id": new_preference.id,
        "course_id": new_preference.course_id,
        "rank": new_preference.rank,
        "student_id": new_preference.student_id,
        "highlighted": new_preference.highlighted,
        "notes": new_preference.notes,
        "course_code": course.code,
        "course_title": course.title,
    }


@router.get("/preferences", response_model=List[StudentCoursePreferenceRead])
def get_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    preferences = (
        db.query(StudentCoursePreference)
        .filter(StudentCoursePreference.student_id == profile.id)
        .order_by(StudentCoursePreference.rank.asc())
        .all()
    )
    
    # Build response with course info
    result = []
    for pref in preferences:
        course = db.query(Course).filter(Course.id == pref.course_id).first()
        result.append({
            "id": pref.id,
            "course_id": pref.course_id,
            "rank": pref.rank,
            "student_id": pref.student_id,
            "highlighted": pref.highlighted,
            "notes": pref.notes,
            "course_code": course.code if course else "Unknown",
            "course_title": course.title if course else "Unknown",
        })
    return result


@router.delete("/preferences/{preference_id}")
def delete_preference(
    preference_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a single course preference"""
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Find the preference
    preference = db.query(StudentCoursePreference).filter(
        StudentCoursePreference.id == preference_id,
        StudentCoursePreference.student_id == profile.id
    ).first()
    
    if not preference:
        raise HTTPException(status_code=404, detail="Application not found")
    
    db.delete(preference)
    db.commit()
    
    return {"message": "Application removed successfully"}


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
    )

