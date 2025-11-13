import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import Course, StudentCoursePreference, StudentProfile, Track
from app.services.matching_engine import _interest_bonus, evaluate_candidate


def test_interest_bonus_matches_track_with_whitespace_and_case_insensitivity():
    student = StudentProfile(interests="  machine learning & analytics , optimization ")
    course = Course(code="IEOR0001", title="Test Course", track=Track.ML)

    assert math.isclose(_interest_bonus(student, course), 15.0)


def test_interest_bonus_returns_zero_when_track_not_listed():
    student = StudentProfile(interests="Finance, Optimization")
    course = Course(code="IEOR0002", title="Another Course", track=Track.ML)

    assert math.isclose(_interest_bonus(student, course), 0.0)


def _build_student_with_pref(
    *,
    student_id: int,
    course_id: int,
    rank: int,
    faculty_requested: bool = False,
    grade_in_course: str | None = None,
    basket_grade_average: str | None = None,
) -> StudentProfile:
    preference = StudentCoursePreference(
        student_id=student_id,
        course_id=course_id,
        rank=rank,
        faculty_requested=faculty_requested,
        grade_in_course=grade_in_course,
        basket_grade_average=basket_grade_average,
    )
    student = StudentProfile(id=student_id, interests="", resume_text="", transcript_text="")
    student.preferences = [preference]
    return student


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
