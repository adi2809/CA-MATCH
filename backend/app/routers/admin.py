from __future__ import annotations

from io import StringIO
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..dependencies import get_current_admin
from ..models import Assignment, Course, StudentCoursePreference, StudentProfile, Track, User
from ..schemas import (
    ApplicationDetail, AssignmentCreate, AssignmentDetails, CourseApplications,
    CourseCreate, CourseRead, DashboardStats, EmailPayload, HighlightConflict,
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
                
            results.append(SearchResult(
                result_type="student",
                id=student.id,
                display_name=student.full_name or "[First Last]",
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
    
    return CourseApplications(
        course_id=course.id,
        course_code=course.code,
        course_title=course.title,
        instructor=course.instructor,
        track=course.track,
        vacancies=course.vacancies,
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
    course = Course(**course_in.dict())
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
    if course.vacancies <= 0:
        raise HTTPException(status_code=400, detail="No vacancies left")
    
    course.vacancies -= 1
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
