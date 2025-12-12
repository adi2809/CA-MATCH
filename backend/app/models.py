from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class UserRole(str, Enum):
    STUDENT = "student"
    ADMIN = "admin"
    PROFESSOR = "professor"


class StudyLevel(str, Enum):
    UNDERGRAD = "undergraduate"
    MASTERS = "masters"


class Track(str, Enum):
    FINANCE = "Financial Engineering & Risk Management"
    ML = "Machine Learning & Analytics"
    OPTIMIZATION = "Optimization"
    OPERATIONS = "Operations"
    STOCHASTIC = "Stochastic Modeling and Simulation"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    uni: Mapped[str] = mapped_column(String(7), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), default=UserRole.STUDENT)

    student_profile: Mapped["StudentProfile"] = relationship(
        back_populates="user", uselist=False
    )


class StudentProfile(Base, TimestampMixin):
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)

    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    degree_program: Mapped[Optional[str]] = mapped_column(String(255))
    level_of_study: Mapped[Optional[StudyLevel]] = mapped_column(
        SQLEnum(StudyLevel), nullable=True
    )
    interests: Mapped[Optional[str]] = mapped_column(Text)
    resume_path: Mapped[Optional[str]] = mapped_column(String(512))
    transcript_path: Mapped[Optional[str]] = mapped_column(String(512))
    photo_url: Mapped[Optional[str]] = mapped_column(String(512))

    user: Mapped[User] = relationship(back_populates="student_profile")
    preferences: Mapped[List["StudentCoursePreference"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    assignments: Mapped[List["Assignment"]] = relationship(back_populates="student")


class Course(Base, TimestampMixin):
    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("code", name="uq_course_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    instructor: Mapped[Optional[str]] = mapped_column(String(255))
    instructor_email: Mapped[Optional[str]] = mapped_column(String(255))
    professor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    track: Mapped[Optional[Track]] = mapped_column(SQLEnum(Track), nullable=True)
    vacancies: Mapped[int] = mapped_column(Integer, default=0)
    grade_threshold: Mapped[Optional[str]] = mapped_column(String(32))
    similar_courses: Mapped[Optional[str]] = mapped_column(Text)

    professor: Mapped[Optional["User"]] = relationship(foreign_keys=[professor_id])
    preferences: Mapped[List["StudentCoursePreference"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    assignments: Mapped[List["Assignment"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )


class StudentCoursePreference(Base, TimestampMixin):
    __tablename__ = "student_course_preferences"
    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uq_student_course"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"))
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    # NEW FIELD: For professor recommendations/highlighting
    highlighted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    student: Mapped[StudentProfile] = relationship(back_populates="preferences")
    course: Mapped[Course] = relationship(back_populates="preferences")


class AssignmentStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"


class Assignment(Base, TimestampMixin):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"))
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    status: Mapped[AssignmentStatus] = mapped_column(
        SQLEnum(AssignmentStatus), default=AssignmentStatus.PENDING
    )

    student: Mapped[StudentProfile] = relationship(back_populates="assignments")
    course: Mapped[Course] = relationship(back_populates="assignments")
