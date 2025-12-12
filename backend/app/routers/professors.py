from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..dependencies import get_current_professor, get_current_user
from ..database import get_db
from ..models import (
    Assignment,
    AssignmentStatus,
    Course,
    StudentCoursePreference,
    StudentProfile,
    User,
    UserRole,
)

router = APIRouter(prefix="/professors", tags=["professors"])


@router.get("/me")
def get_professor_profile(
    current_user: User = Depends(get_current_professor),
):
    """Get current professor's profile"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "uni": current_user.uni,
        "role": current_user.role.value,
    }


@router.get("/courses")
def get_professor_courses(
    current_user: User = Depends(get_current_professor),
    db: Session = Depends(get_db),
):
    """Get all courses assigned to this professor"""
    courses = db.query(Course).filter(Course.professor_id == current_user.id).all()
    
    result = []
    for course in courses:
        # Count applications for this course
        application_count = db.query(StudentCoursePreference).filter(
            StudentCoursePreference.course_id == course.id
        ).count()
        
        # Count current assignments
        assignment_count = db.query(Assignment).filter(
            Assignment.course_id == course.id
        ).count()
        
        result.append({
            "id": course.id,
            "code": course.code,
            "title": course.title,
            "track": course.track.value if course.track else None,
            "vacancies": course.vacancies,
            "application_count": application_count,
            "assignment_count": assignment_count,
        })
    
    return result


@router.get("/courses/{course_id}/applications")
def get_course_applications(
    course_id: int,
    current_user: User = Depends(get_current_professor),
    db: Session = Depends(get_db),
):
    """Get all applications for a specific course (professor must own the course)"""
    # Verify professor owns this course
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.professor_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found or you don't have access")
    
    # Get all preferences for this course
    preferences = db.query(StudentCoursePreference).filter(
        StudentCoursePreference.course_id == course_id
    ).order_by(StudentCoursePreference.rank.asc()).all()
    
    result = []
    for pref in preferences:
        student = db.query(StudentProfile).filter(StudentProfile.id == pref.student_id).first()
        user = db.query(User).filter(User.id == student.user_id).first() if student else None
        
        # Check if student is already assigned to this course
        is_assigned = db.query(Assignment).filter(
            Assignment.student_id == pref.student_id,
            Assignment.course_id == course_id
        ).first() is not None
        
        result.append({
            "preference_id": pref.id,
            "student_id": pref.student_id,
            "student_uni": user.uni if user else "Unknown",
            "student_email": user.email if user else None,
            "student_name": student.full_name if student else None,
            "rank": pref.rank,
            "highlighted": pref.highlighted,
            "notes": pref.notes,
            "is_assigned": is_assigned,
        })
    
    return {
        "course": {
            "id": course.id,
            "code": course.code,
            "title": course.title,
            "vacancies": course.vacancies,
        },
        "applications": result,
    }


@router.get("/courses/{course_id}/assignments")
def get_course_assignments(
    course_id: int,
    current_user: User = Depends(get_current_professor),
    db: Session = Depends(get_db),
):
    """Get all TA assignments for a specific course"""
    # Verify professor owns this course
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.professor_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found or you don't have access")
    
    assignments = db.query(Assignment).filter(Assignment.course_id == course_id).all()
    
    result = []
    for assignment in assignments:
        student = db.query(StudentProfile).filter(StudentProfile.id == assignment.student_id).first()
        user = db.query(User).filter(User.id == student.user_id).first() if student else None
        
        result.append({
            "assignment_id": assignment.id,
            "student_id": assignment.student_id,
            "student_uni": user.uni if user else "Unknown",
            "student_email": user.email if user else None,
            "student_name": student.full_name if student else None,
            "status": assignment.status.value,
        })
    
    return {
        "course": {
            "id": course.id,
            "code": course.code,
            "title": course.title,
            "vacancies": course.vacancies,
        },
        "assignments": result,
    }


@router.post("/courses/{course_id}/assign/{student_id}")
def assign_student_to_course(
    course_id: int,
    student_id: int,
    current_user: User = Depends(get_current_professor),
    db: Session = Depends(get_db),
):
    """
    Assign a student as TA to a course (Professor override).
    This bypasses the normal matching algorithm.
    """
    # Verify professor owns this course
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.professor_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found or you don't have access")
    
    # Verify student exists
    student = db.query(StudentProfile).filter(StudentProfile.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Check if already assigned
    existing = db.query(Assignment).filter(
        Assignment.student_id == student_id,
        Assignment.course_id == course_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Student is already assigned to this course")
    
    # Create assignment (Professor override - immediately confirmed)
    assignment = Assignment(
        student_id=student_id,
        course_id=course_id,
        status=AssignmentStatus.CONFIRMED,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    
    # Get student info for response
    user = db.query(User).filter(User.id == student.user_id).first()
    
    return {
        "message": f"Successfully assigned student to {course.code}",
        "assignment": {
            "id": assignment.id,
            "student_id": student_id,
            "student_uni": user.uni if user else "Unknown",
            "course_id": course_id,
            "course_code": course.code,
            "status": assignment.status.value,
        }
    }


@router.delete("/courses/{course_id}/assignments/{assignment_id}")
def remove_assignment(
    course_id: int,
    assignment_id: int,
    current_user: User = Depends(get_current_professor),
    db: Session = Depends(get_db),
):
    """Remove a TA assignment from a course"""
    # Verify professor owns this course
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.professor_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found or you don't have access")
    
    # Find and delete assignment
    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id,
        Assignment.course_id == course_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    db.delete(assignment)
    db.commit()
    
    return {"message": "Assignment removed successfully"}


@router.post("/courses/{course_id}/highlight/{preference_id}")
def highlight_application(
    course_id: int,
    preference_id: int,
    current_user: User = Depends(get_current_professor),
    db: Session = Depends(get_db),
):
    """Highlight/recommend a student application"""
    # Verify professor owns this course
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.professor_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found or you don't have access")
    
    preference = db.query(StudentCoursePreference).filter(
        StudentCoursePreference.id == preference_id,
        StudentCoursePreference.course_id == course_id
    ).first()
    
    if not preference:
        raise HTTPException(status_code=404, detail="Application not found")
    
    # Toggle highlight
    preference.highlighted = not preference.highlighted
    db.commit()
    
    return {
        "message": f"Application {'highlighted' if preference.highlighted else 'unhighlighted'}",
        "highlighted": preference.highlighted,
    }


@router.get("/search-students")
def search_students(
    q: str,
    current_user: User = Depends(get_current_professor),
    db: Session = Depends(get_db),
):
    """
    Search for students by UNI or email.
    Professors can use this to find students and add them to their courses.
    """
    if not q or len(q) < 2:
        raise HTTPException(status_code=400, detail="Search query must be at least 2 characters")
    
    search_term = f"%{q}%"
    
    # Search users with student role by UNI or email
    users = db.query(User).filter(
        User.role == UserRole.STUDENT,
        (User.uni.ilike(search_term) | User.email.ilike(search_term))
    ).limit(20).all()
    
    results = []
    for user in users:
        # Get student profile
        student = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
        
        if student:
            results.append({
                "student_id": student.id,
                "user_id": user.id,
                "uni": user.uni,
                "email": user.email,
                "full_name": student.full_name if student else None,
            })
    
    return results
