from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

from .models import AssignmentStatus, StudyLevel, Track, UserRole


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Optional[UserRole] = None


class TokenData(BaseModel):
    uni: Optional[str] = None
    role: Optional[UserRole] = None


class UserBase(BaseModel):
    email: EmailStr
    uni: str = Field(min_length=6, max_length=7)


class UserCreate(UserBase):
    password: str = Field(min_length=8)
    role: UserRole = UserRole.STUDENT


class UserRead(UserBase):
    id: int
    role: UserRole
    created_at: datetime

    class Config:
        orm_mode = True


class StudentProfileBase(BaseModel):
    full_name: Optional[str]
    degree_program: Optional[str]
    level_of_study: Optional[StudyLevel]
    interests: List[Track] = []
    resume_path: Optional[str]
    transcript_path: Optional[str]
    photo_url: Optional[str]


class StudentProfileCreate(StudentProfileBase):
    pass


class StudentProfileRead(StudentProfileBase):
    id: int
    user_id: int

    class Config:
        orm_mode = True


class CourseBase(BaseModel):
    code: str
    title: str
    instructor: Optional[str]
    instructor_email: Optional[EmailStr]
    track: Optional[Track]
    vacancies: int = 0
    grade_threshold: Optional[str]
    similar_courses: Optional[str]


class CourseCreate(CourseBase):
    pass


class CourseRead(CourseBase):
    id: int

    class Config:
        orm_mode = True


class StudentCoursePreferenceBase(BaseModel):
    course_id: int
    rank: int


class StudentCoursePreferenceCreate(StudentCoursePreferenceBase):
    pass


class StudentCoursePreferenceRead(StudentCoursePreferenceBase):
    id: int
    student_id: int
    highlighted: bool = False
    notes: Optional[str] = None

    class Config:
        orm_mode = True


# NEW SCHEMAS FOR ENHANCED FEATURES

class ApplicationDetail(BaseModel):
    """Detailed view of an application with student and course info"""
    preference_id: int
    student_id: int
    student_name: Optional[str]
    student_uni: str
    student_email: Optional[str]
    course_id: int
    course_code: str
    course_title: str
    instructor: Optional[str]
    track: Optional[Track]
    rank: int
    highlighted: bool
    notes: Optional[str]
    is_assigned: bool = False

    class Config:
        orm_mode = True


class StudentApplications(BaseModel):
    """All applications for a specific student"""
    student_id: int
    student_name: Optional[str]
    student_uni: str
    student_email: Optional[str]
    degree_program: Optional[str]
    level_of_study: Optional[StudyLevel]
    total_applications: int
    highlighted_count: int
    applications: List[ApplicationDetail]


class CourseApplications(BaseModel):
    """All applications for a specific course"""
    course_id: int
    course_code: str
    course_title: str
    instructor: Optional[str]
    track: Optional[Track]
    vacancies: int
    total_applications: int
    highlighted_count: int
    applications: List[ApplicationDetail]


class HighlightToggle(BaseModel):
    """Request to toggle highlight status"""
    highlighted: bool
    notes: Optional[str] = None


class HighlightConflict(BaseModel):
    """Information about highlight conflicts"""
    student_id: int
    student_name: Optional[str]
    student_uni: str
    highlighted_courses: List[dict]  # List of {course_code, course_title, rank}
    total_highlights: int


class SearchResult(BaseModel):
    """Generic search result"""
    result_type: str  # "student" or "course"
    id: int
    display_name: str  # Student name or course code
    secondary_info: str  # UNI or course title
    application_count: int


class DashboardStats(BaseModel):
    """Admin dashboard statistics"""
    total_students: int
    total_courses: int
    total_applications: int
    total_assignments: int
    highlighted_applications: int
    courses_with_no_applications: List[dict]


class AssignmentBase(BaseModel):
    student_id: int
    course_id: int
    status: AssignmentStatus = AssignmentStatus.PENDING


class AssignmentCreate(AssignmentBase):
    pass


class AssignmentRead(AssignmentBase):
    id: int

    class Config:
        orm_mode = True


class AssignmentDetails(AssignmentRead):
    student_name: Optional[str]
    student_uni: Optional[str]
    student_email: Optional[EmailStr]
    course_code: Optional[str]
    course_title: Optional[str]
    instructor: Optional[str]
    instructor_email: Optional[EmailStr]
    highlight_conflicts: int = 0  # Number of other courses where student is highlighted


class MatchRequest(BaseModel):
    course_ids: Optional[List[int]] = None
    top_n: int = Field(default=1, ge=1)


class MatchResult(BaseModel):
    assignments: List[AssignmentDetails]
    skipped_students: List[int]


class EmailPayload(BaseModel):
    subject: str
    message: str
    cc_instructors: bool = True
