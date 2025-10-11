import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import Course, StudentProfile, Track
from app.services.matching_engine import _interest_bonus


def test_interest_bonus_matches_track_with_whitespace_and_case_insensitivity():
    student = StudentProfile(interests="  machine learning & analytics , optimization ")
    course = Course(code="IEOR0001", title="Test Course", track=Track.ML)

    assert math.isclose(_interest_bonus(student, course), 15.0)


def test_interest_bonus_returns_zero_when_track_not_listed():
    student = StudentProfile(interests="Finance, Optimization")
    course = Course(code="IEOR0002", title="Another Course", track=Track.ML)

    assert math.isclose(_interest_bonus(student, course), 0.0)
