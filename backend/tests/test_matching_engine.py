import math
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import (
    Assignment,
    AssignmentStatus,
    Course,
    InstructorFeedback,
    StudentCoursePreference,
    StudentProfile,
    Track,
)
from app.services.matching_engine import _interest_bonus, evaluate_candidate
from app.services.skill_graph import skill_miner


@pytest.fixture(autouse=True)
def _reset_skill_graph_cache():
    skill_miner.reset()
    yield
    skill_miner.reset()


def test_interest_bonus_matches_track_with_whitespace_and_case_insensitivity():
    student = StudentProfile(interests="  machine learning & analytics , optimization ")
    course = Course(code="IEOR0001", title="Test Course", track=Track.ML)

    assert math.isclose(_interest_bonus(student, course), 15.0)


def test_interest_bonus_returns_zero_when_track_not_listed():
    student = StudentProfile(interests="Finance, Optimization")
    course = Course(code="IEOR0002", title="Another Course", track=Track.ML)

    assert math.isclose(_interest_bonus(student, course), 0.0)


_ASSIGNMENT_SEQUENCE = 1000


def _build_student_with_pref(
    *,
    student_id: int,
    course_id: int,
    rank: int,
    faculty_requested: bool = False,
    grade_in_course: str | None = None,
    basket_grade_average: str | None = None,
    resume_text: str = "",
    transcript_text: str = "",
    feedback_ratings: list[int] | None = None,
) -> StudentProfile:
    preference = StudentCoursePreference(
        student_id=student_id,
        course_id=course_id,
        rank=rank,
        faculty_requested=faculty_requested,
        grade_in_course=grade_in_course,
        basket_grade_average=basket_grade_average,
    )
    student = StudentProfile(
        id=student_id,
        interests="",
        resume_text=resume_text,
        transcript_text=transcript_text,
    )
    student.preferences = [preference]
    if feedback_ratings:
        assignment = Assignment(
            id=_build_student_with_pref.assignment_sequence,
            student_id=student_id,
            course_id=course_id,
            status=AssignmentStatus.CONFIRMED,
        )
        _build_student_with_pref.assignment_sequence += 1
        student.assignments = [assignment]
        student.instructor_feedback = [
            InstructorFeedback(
                assignment_id=assignment.id,
                student_id=student_id,
                course_id=course_id,
                rating=rating,
                comments=None,
            )
            for rating in feedback_ratings
        ]
    else:
        student.assignments = []
        student.instructor_feedback = []
    return student


_build_student_with_pref.assignment_sequence = _ASSIGNMENT_SEQUENCE


def test_faculty_request_priority_overrides_grades():
    course = Course(id=1, code="IEOR1000", title="Optimization")
    requested = _build_student_with_pref(
        student_id=1,
        course_id=1,
        rank=3,
        faculty_requested=True,
        grade_in_course="B",
    )
    high_grade = _build_student_with_pref(
        student_id=2,
        course_id=1,
        rank=1,
        grade_in_course="A",
    )

    requested_score = evaluate_candidate(requested, course)
    high_grade_score = evaluate_candidate(high_grade, course)

    assert requested_score > high_grade_score


def test_course_grade_priority_overrides_preference_rank():
    course = Course(id=1, code="IEOR1001", title="Stochastic")
    top_rank_low_grade = _build_student_with_pref(
        student_id=1,
        course_id=1,
        rank=1,
        grade_in_course="B-",
    )
    lower_rank_high_grade = _build_student_with_pref(
        student_id=2,
        course_id=1,
        rank=3,
        grade_in_course="A",
    )

    assert evaluate_candidate(lower_rank_high_grade, course) > evaluate_candidate(
        top_rank_low_grade, course
    )


def test_skill_graph_increases_score_for_matching_keywords():
    course = Course(
        id=5,
        code="IEOR2000",
        title="Machine Learning",
        competency_matrix='{"skills": {"machine": 0.5, "learning": 0.5}}',
    )
    skilled_student = _build_student_with_pref(
        student_id=10,
        course_id=5,
        rank=3,
        resume_text="Experienced in machine learning and optimization",
    )
    unskilled_student = _build_student_with_pref(
        student_id=11,
        course_id=5,
        rank=3,
        resume_text="Skilled in operations research",
    )

    assert evaluate_candidate(skilled_student, course) > evaluate_candidate(
        unskilled_student, course
    )


def test_instructor_feedback_breaks_ties():
    course = Course(id=9, code="IEOR3000", title="Data Analytics")
    high_feedback = _build_student_with_pref(
        student_id=20,
        course_id=9,
        rank=2,
        feedback_ratings=[5, 4],
    )
    neutral_feedback = _build_student_with_pref(
        student_id=21,
        course_id=9,
        rank=2,
    )

    assert evaluate_candidate(high_feedback, course) > evaluate_candidate(
        neutral_feedback, course
    )
