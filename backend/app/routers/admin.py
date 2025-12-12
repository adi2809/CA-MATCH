from __future__ import annotations

from io import StringIO
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..dependencies import get_current_admin
from ..models import Assignment, Course, StudentCoursePreference, StudentProfile, Track, User, UserRole
from ..schemas import (
    ApplicationDetail, AssignmentCreate, AssignmentDetails, CourseApplications,
    CourseCreate, CourseRead, CourseUpdate, DashboardStats, EmailPayload, HighlightConflict,
    HighlightToggle, MatchRequest, MatchResult, SearchResult, StudentApplications,
)
from ..services.matching_engine import run_matching

router = APIRouter(prefix="/admin", tags=["admin"])


# DASHBOARD & STATISTICS
@router.get("/dashboard", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db), _: None = Depends(get_current_admin)) -> DashboardStats:
    total_students = db.query(StudentProfile).count()
    total_courses = db.query(Course).count()
    total_applications = db.query(StudentCoursePreference).count()
    total_assignments = db.query(Assignment).count()
    highlighted_applications = db.query(StudentCoursePreference).filter(
        StudentCoursePreference.highlighted == True
    ).count()
    
    courses_no_apps = db.query(Course).outerjoin(StudentCoursePreference).group_by(
        Course.id
    ).having(func.count(StudentCoursePreference.id) == 0).all()
    
    courses_with_no_applications = [
        {"code": c.code, "title": c.title, "vacancies": c.vacancies} for c in courses_no_apps
    ]
    
    return DashboardStats(
        total_students=total_students,
        total_courses=total_courses,
        total_applications=total_applications,
        total_assignments=total_assignments,
        highlighted_applications=highlighted_applications,
        courses_with_no_applications=courses_with_no_applications,
    )


# SEARCH
@router.get("/search", response_model=List[SearchResult])
def search(
    q: str = Query("", min_length=0),  # Allow empty string
    search_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: None = Depends(get_current_admin),
) -> List[SearchResult]:
    results = []
    
    if search_type == "student" or search_type is None:
        # Build query
        query = db.query(StudentProfile).join(User).options(
            joinedload(StudentProfile.user),
            joinedload(StudentProfile.preferences)
        )
        
        # Apply filter only if q is not empty
        if q and q.strip():
            query = query.filter(
                or_(User.uni.ilike(f"%{q}%"), StudentProfile.full_name.ilike(f"%{q}%"))
            )
        
        students = query.all()  # Removed .limit(100) - get all students
        
        for student in students:
            try:
                app_count = len(student.preferences) if student.preferences else 0
            except:
                app_count = 0
            
            # Use full_name if available, otherwise construct from first_name/last_name, or use UNI
            if student.full_name:
                display_name = student.full_name
            elif student.user and student.user.first_name and student.user.last_name:
                display_name = f"{student.user.first_name} {student.user.last_name}"
            elif student.user:
                display_name = student.user.uni
            else:
                display_name = "Unknown Student"
                
            results.append(SearchResult(
                result_type="student",
                id=student.id,
                display_name=display_name,
                secondary_info=student.user.uni if student.user else "Unknown",
                application_count=app_count
            ))
    
    if search_type == "course" or search_type is None:
        # Build query
        query = db.query(Course).options(joinedload(Course.preferences))
        
        # Apply filter only if q is not empty
        if q and q.strip():
            query = query.filter(
                or_(Course.code.ilike(f"%{q}%"), Course.title.ilike(f"%{q}%"))
            )
        
        courses = query.all()  # Removed .limit(100) - get all courses
        
        for course in courses:
            try:
                app_count = len(course.preferences) if course.preferences else 0
            except:
                app_count = 0
                
            results.append(SearchResult(
                result_type="course",
                id=course.id,
                display_name=course.code,
                secondary_info=course.title,
                application_count=app_count
            ))
    
    return results


# APPLICATION VIEWS
@router.get("/applications", response_model=List[ApplicationDetail])
def get_all_applications(
    student_uni: Optional[str] = Query(None),
    student_name: Optional[str] = Query(None),
    course_code: Optional[str] = Query(None),
    highlighted_only: bool = Query(False),
    db: Session = Depends(get_db),
    _: None = Depends(get_current_admin),
) -> List[ApplicationDetail]:
    query = db.query(StudentCoursePreference).options(
        joinedload(StudentCoursePreference.student).joinedload(StudentProfile.user),
        joinedload(StudentCoursePreference.course)
    )
    
    if student_uni:
        query = query.join(StudentProfile).join(User).filter(User.uni.ilike(f"%{student_uni}%"))
    if student_name:
        query = query.join(StudentProfile).filter(StudentProfile.full_name.ilike(f"%{student_name}%"))
    if course_code:
        query = query.join(Course).filter(Course.code.ilike(f"%{course_code}%"))
    if highlighted_only:
        query = query.filter(StudentCoursePreference.highlighted == True)
    
    preferences = query.all()
    assigned_pairs = {(a.student_id, a.course_id) for a in db.query(Assignment).all()}
    
    return [_to_application_detail(pref, assigned_pairs) for pref in preferences]


@router.get("/applications/student/{uni}", response_model=StudentApplications)
def get_student_applications(uni: str, db: Session = Depends(get_db), _: None = Depends(get_current_admin)) -> StudentApplications:
    user = db.query(User).filter(User.uni == uni).first()
    if not user or not user.student_profile:
        raise HTTPException(status_code=404, detail="Student not found")
    
    student = user.student_profile
    assigned_pairs = {(a.student_id, a.course_id) for a in db.query(Assignment).filter(Assignment.student_id == student.id).all()}
    applications = [_to_application_detail(pref, assigned_pairs) for pref in student.preferences]
    
    return StudentApplications(
        student_id=student.id,
        student_name=student.full_name,
        student_uni=user.uni,
        student_email=user.email,
        degree_program=student.degree_program,
        level_of_study=student.level_of_study,
        total_applications=len(applications),
        highlighted_count=sum(1 for app in applications if app.highlighted),
        applications=applications
    )


@router.get("/applications/course/{course_id}", response_model=CourseApplications)
def get_course_applications(course_id: int, db: Session = Depends(get_db), _: None = Depends(get_current_admin)) -> CourseApplications:
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    assigned_pairs = {(a.student_id, a.course_id) for a in db.query(Assignment).filter(Assignment.course_id == course_id).all()}
    applications = sorted([_to_application_detail(pref, assigned_pairs) for pref in course.preferences], key=lambda x: x.rank)
    
    # Calculate available vacancies
    assignment_count = db.query(Assignment).filter(Assignment.course_id == course_id).count()
    available_vacancies = course.vacancies - assignment_count
    
    return CourseApplications(
        course_id=course.id,
        course_code=course.code,
        course_title=course.title,
        instructor=None,  # Deprecated field, kept for schema compatibility
        track=course.track,
        vacancies=available_vacancies,  # Show remaining vacancies
        total_applications=len(applications),
        highlighted_count=sum(1 for app in applications if app.highlighted),
        applications=applications
    )


# HIGHLIGHT MANAGEMENT
@router.put("/applications/{preference_id}/highlight", response_model=ApplicationDetail)
def toggle_highlight(
    preference_id: int,
    highlight_data: HighlightToggle,
    db: Session = Depends(get_db),
    _: None = Depends(get_current_admin),
) -> ApplicationDetail:
    preference = db.query(StudentCoursePreference).options(
        joinedload(StudentCoursePreference.student).joinedload(StudentProfile.user),
        joinedload(StudentCoursePreference.course)
    ).filter(StudentCoursePreference.id == preference_id).first()
    
    if not preference:
        raise HTTPException(status_code=404, detail="Application not found")
    
    preference.highlighted = highlight_data.highlighted
    if highlight_data.notes is not None:
        preference.notes = highlight_data.notes
    
    db.commit()
    db.refresh(preference)
    
    assigned = db.query(Assignment).filter(
        Assignment.student_id == preference.student_id,
        Assignment.course_id == preference.course_id
    ).first()
    assigned_pairs = {(assigned.student_id, assigned.course_id)} if assigned else set()
    
    return _to_application_detail(preference, assigned_pairs)


@router.get("/highlighted-conflicts/{student_id}", response_model=HighlightConflict)
def get_highlight_conflicts(
    student_id: int,
    exclude_course_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: None = Depends(get_current_admin),
) -> HighlightConflict:
    student = db.query(StudentProfile).options(joinedload(StudentProfile.user)).filter(
        StudentProfile.id == student_id
    ).first()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    query = db.query(StudentCoursePreference).options(
        joinedload(StudentCoursePreference.course)
    ).filter(
        StudentCoursePreference.student_id == student_id,
        StudentCoursePreference.highlighted == True
    )
    
    if exclude_course_id:
        query = query.filter(StudentCoursePreference.course_id != exclude_course_id)
    
    highlighted_prefs = query.all()
    highlighted_courses = [
        {"course_id": p.course_id, "course_code": p.course.code, "course_title": p.course.title, "rank": p.rank}
        for p in highlighted_prefs
    ]
    
    return HighlightConflict(
        student_id=student.id,
        student_name=student.full_name,
        student_uni=student.user.uni,
        highlighted_courses=highlighted_courses,
        total_highlights=len(highlighted_courses)
    )


# COURSE MANAGEMENT (Original endpoints)
@router.post("/courses", response_model=CourseRead)
def create_course(course_in: CourseCreate, db: Session = Depends(get_db), _: None = Depends(get_current_admin)) -> Course:
    if db.query(Course).filter(Course.code == course_in.code).first():
        raise HTTPException(status_code=400, detail="Course already exists")
    
    course_data = course_in.dict()
    
    # Auto-populate instructor fields from professor if professor_id is provided
    if course_data.get("professor_id"):
        professor = db.query(User).filter(
            User.id == course_data["professor_id"],
            User.role == UserRole.PROFESSOR
        ).first()
        if professor:
            # Build instructor name from first_name and last_name if available
            if professor.first_name and professor.last_name:
                course_data["instructor"] = f"{professor.first_name} {professor.last_name}"
            else:
                course_data["instructor"] = professor.uni
            course_data["instructor_email"] = professor.email
    
    course = Course(**course_data)
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.get("/courses", response_model=List[CourseRead])
def list_courses(db: Session = Depends(get_db), _: None = Depends(get_current_admin)) -> List[Course]:
    return db.query(Course).all()


@router.put("/courses/{course_id}", response_model=CourseRead)
def update_course(
    course_id: int, course_in: CourseCreate, db: Session = Depends(get_db), _: None = Depends(get_current_admin)
) -> Course:
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    for key, value in course_in.dict().items():
        setattr(course, key, value)
    db.commit()
    db.refresh(course)
    return course


@router.delete("/courses/{course_id}")
def delete_course(course_id: int, db: Session = Depends(get_db), _: None = Depends(get_current_admin)) -> None:
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    db.delete(course)
    db.commit()


@router.post("/courses/import", response_model=List[CourseRead])
def import_courses(file: UploadFile = File(...), db: Session = Depends(get_db), _: None = Depends(get_current_admin)) -> List[Course]:
    contents = file.file.read().decode("utf-8")
    df = pd.read_csv(StringIO(contents))
    df.columns = [col.lower() for col in df.columns]
    
    created = []
    for _, row in df.iterrows():
        track = Track(row.get("track")) if pd.notna(row.get("track")) else None
        existing = db.query(Course).filter(Course.code == row["course code"]).first()
        
        if existing:
            existing.title = row["title"]
            existing.instructor = row.get("instructor")
            existing.instructor_email = row.get("instructor email")
            existing.track = track
            existing.vacancies = int(row.get("vacancies", existing.vacancies or 0))
            created.append(existing)
        else:
            course = Course(
                code=row["course code"], title=row["title"], instructor=row.get("instructor"),
                instructor_email=row.get("instructor email"), track=track,
                vacancies=int(row.get("vacancies", 0))
            )
            db.add(course)
            created.append(course)
    
    db.commit()
    return created


# MATCHING & ASSIGNMENTS
@router.post("/match", response_model=MatchResult)
def start_match(request: MatchRequest, db: Session = Depends(get_db), _: None = Depends(get_current_admin)) -> MatchResult:
    assignments, skipped = run_matching(db, course_ids=request.course_ids)
    
    for assignment in assignments:
        db.add(assignment)
    db.commit()
    
    assignment_ids = [a.id for a in assignments]
    if assignment_ids:
        persisted = db.query(Assignment).options(
            joinedload(Assignment.student).joinedload(StudentProfile.user),
            joinedload(Assignment.course),
        ).filter(Assignment.id.in_(assignment_ids)).all()
        detailed = [_to_assignment_details(a, db) for a in persisted]
    else:
        detailed = []
    
    return MatchResult(assignments=detailed, skipped_students=skipped)


@router.post("/assignments", response_model=AssignmentDetails)
def create_assignment(
    assignment_in: AssignmentCreate, db: Session = Depends(get_db), _: None = Depends(get_current_admin)
) -> AssignmentDetails:
    student = db.query(StudentProfile).filter(StudentProfile.id == assignment_in.student_id).first()
    course = db.query(Course).filter(Course.id == assignment_in.course_id).first()
    
    if not student or not course:
        raise HTTPException(status_code=404, detail="Student or course not found")
    
    # Check if student is already assigned to ANY course
    existing_assignment = db.query(Assignment).filter(Assignment.student_id == assignment_in.student_id).first()
    if existing_assignment:
        existing_course = db.query(Course).filter(Course.id == existing_assignment.course_id).first()
        raise HTTPException(
            status_code=400, 
            detail=f"Student is already assigned as TA to {existing_course.code if existing_course else 'another course'}"
        )
    
    # Check if course has available vacancies
    current_assignments = db.query(Assignment).filter(Assignment.course_id == assignment_in.course_id).count()
    if current_assignments >= course.vacancies:
        raise HTTPException(
            status_code=400, 
            detail=f"No vacancies available for {course.code}. All {course.vacancies} positions are filled."
        )
    
    assignment = Assignment(
        student_id=assignment_in.student_id,
        course_id=assignment_in.course_id,
        status=assignment_in.status,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    
    return _to_assignment_details(assignment, db)


@router.get("/assignments", response_model=List[AssignmentDetails])
def list_assignments(db: Session = Depends(get_db), _: None = Depends(get_current_admin)) -> List[AssignmentDetails]:
    assignments = db.query(Assignment).options(
        joinedload(Assignment.student).joinedload(StudentProfile.user),
        joinedload(Assignment.course),
    ).all()
    return [_to_assignment_details(a, db) for a in assignments]


@router.post("/communications")
def compose_email(payload: EmailPayload, db: Session = Depends(get_db), _: None = Depends(get_current_admin)) -> dict:
    assignments = db.query(Assignment).options(
        joinedload(Assignment.student).joinedload(StudentProfile.user),
        joinedload(Assignment.course),
    ).all()
    
    recipients = []
    for a in assignments:
        if a.student and a.course and a.student.user:
            recipients.append({
                "student_name": a.student.full_name,
                "student_email": a.student.user.email,
                "instructor_email": a.course.instructor_email,
                "course_title": a.course.title,
            })
    
    return {"subject": payload.subject, "message": payload.message, "recipients": recipients, "cc_instructors": payload.cc_instructors}


# HELPER FUNCTIONS
def _to_application_detail(pref: StudentCoursePreference, assigned_pairs: set) -> ApplicationDetail:
    student = pref.student
    course = pref.course
    user = student.user if student else None
    
    return ApplicationDetail(
        preference_id=pref.id,
        student_id=pref.student_id,
        student_name=student.full_name if student else None,
        student_uni=user.uni if user else "",
        student_email=user.email if user else None,
        course_id=pref.course_id,
        course_code=course.code if course else "",
        course_title=course.title if course else "",
        instructor=course.instructor if course else None,
        track=course.track if course else None,
        rank=pref.rank,
        highlighted=pref.highlighted,
        notes=pref.notes,
        is_assigned=(pref.student_id, pref.course_id) in assigned_pairs
    )


def _to_assignment_details(assignment: Assignment, db: Session) -> AssignmentDetails:
    student = assignment.student
    course = assignment.course
    user = student.user if student else None
    
    # Get highlight conflicts
    conflicts = db.query(StudentCoursePreference).filter(
        StudentCoursePreference.student_id == assignment.student_id,
        StudentCoursePreference.highlighted == True,
        StudentCoursePreference.course_id != assignment.course_id
    ).count()
    
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
        highlight_conflicts=conflicts
    )


# COURSE MANAGEMENT

@router.put("/courses/{course_id}")
def update_course(
    course_id: int,
    course_update: CourseUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(get_current_admin)
):
    """Update an existing course"""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Update only the fields that are provided
    update_data = course_update.model_dump(exclude_unset=True)
    
    # If professor_id is being updated, validate the professor exists and auto-populate instructor fields
    if "professor_id" in update_data:
        if update_data["professor_id"] is not None:
            professor = db.query(User).filter(
                User.id == update_data["professor_id"],
                User.role == UserRole.PROFESSOR
            ).first()
            if not professor:
                raise HTTPException(status_code=404, detail="Professor not found")
            
            # Auto-populate instructor fields
            if professor.first_name and professor.last_name:
                update_data["instructor"] = f"{professor.first_name} {professor.last_name}"
            else:
                update_data["instructor"] = professor.uni
            update_data["instructor_email"] = professor.email
        else:
            # If professor_id is being set to None, clear instructor fields
            update_data["instructor"] = None
            update_data["instructor_email"] = None
    
    # If code is being updated, check for duplicates
    if "code" in update_data and update_data["code"] != course.code:
        existing_course = db.query(Course).filter(
            Course.code == update_data["code"],
            Course.id != course_id
        ).first()
        if existing_course:
            raise HTTPException(status_code=400, detail=f"Course code {update_data['code']} already exists")
    
    # Apply updates
    for field, value in update_data.items():
        setattr(course, field, value)
    
    db.commit()
    db.refresh(course)
    
    return {
        "message": "Course updated successfully",
        "course": {
            "id": course.id,
            "code": course.code,
            "title": course.title,
            "track": course.track.value if course.track else None,
            "vacancies": course.vacancies,
            "grade_threshold": course.grade_threshold,
            "similar_courses": course.similar_courses,
            "professor_id": course.professor_id,
        }
    }


@router.get("/courses")
def list_all_courses(
    db: Session = Depends(get_db),
    _: None = Depends(get_current_admin)
):
    """Get all courses with their details"""
    courses = db.query(Course).all()
    
    result = []
    for course in courses:
        # Count assignments for this course
        assignment_count = db.query(Assignment).filter(Assignment.course_id == course.id).count()
        available_vacancies = course.vacancies - assignment_count
        
        result.append({
            "id": course.id,
            "code": course.code,
            "title": course.title,
            "track": course.track.value if course.track else None,
            "vacancies": available_vacancies,
            "total_vacancies": course.vacancies,
            "grade_threshold": course.grade_threshold,
            "similar_courses": course.similar_courses,
            "professor_id": course.professor_id,
        })
    
    return result


# PROFESSOR MANAGEMENT

@router.get("/professors")
def list_professors(db: Session = Depends(get_db), _: None = Depends(get_current_admin)):
    """Get all professors"""
    professors = db.query(User).filter(User.role == UserRole.PROFESSOR).all()
    
    result = []
    for prof in professors:
        # Count courses assigned to this professor
        course_count = db.query(Course).filter(Course.professor_id == prof.id).count()
        
        result.append({
            "id": prof.id,
            "uni": prof.uni,
            "email": prof.email,
            "course_count": course_count,
        })
    
    return result


@router.post("/professors/{user_id}/assign-course/{course_id}")
def assign_professor_to_course(
    user_id: int,
    course_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(get_current_admin),
):
    """Assign a professor to a course"""
    # Verify professor exists and is a professor
    professor = db.query(User).filter(
        User.id == user_id,
        User.role == UserRole.PROFESSOR
    ).first()
    
    if not professor:
        raise HTTPException(status_code=404, detail="Professor not found")
    
    # Verify course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Assign professor
    course.professor_id = professor.id
    course.instructor = professor.uni  # Update instructor field
    course.instructor_email = professor.email
    db.commit()
    
    return {
        "message": f"Professor {professor.uni} assigned to {course.code}",
        "course_id": course.id,
        "professor_id": professor.id,
    }


@router.delete("/professors/{user_id}/unassign-course/{course_id}")
def unassign_professor_from_course(
    user_id: int,
    course_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(get_current_admin),
):
    """Remove a professor from a course"""
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.professor_id == user_id
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found or professor not assigned")
    
    course.professor_id = None
    db.commit()
    
    return {"message": f"Professor unassigned from {course.code}"}


@router.get("/professors/{user_id}/courses")
def get_professor_courses(
    user_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(get_current_admin),
):
    """Get all courses assigned to a specific professor"""
    professor = db.query(User).filter(
        User.id == user_id,
        User.role == UserRole.PROFESSOR
    ).first()
    
    if not professor:
        raise HTTPException(status_code=404, detail="Professor not found")
    
    courses = db.query(Course).filter(Course.professor_id == user_id).all()
    
    return {
        "professor": {
            "id": professor.id,
            "uni": professor.uni,
            "email": professor.email,
        },
        "courses": [
            {
                "id": c.id,
                "code": c.code,
                "title": c.title,
                "vacancies": c.vacancies - db.query(Assignment).filter(Assignment.course_id == c.id).count(),
                "total_vacancies": c.vacancies,
            }
            for c in courses
        ],
    }

