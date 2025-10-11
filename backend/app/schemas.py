from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

from .models import AssignmentStatus, StudyLevel, Track, UserRole


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


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
    track: Optional[Track]


class StudentCoursePreferenceCreate(StudentCoursePreferenceBase):
    pass


class StudentCoursePreferenceRead(StudentCoursePreferenceBase):
    id: int
    student_id: int

    class Config:
        orm_mode = True


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

