from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

from sqlalchemy.orm import Session

from ..models import Assignment, Course, StudentCoursePreference, StudentProfile
from ..services.feedback import normalize_rating
from ..services.skill_graph import skill_miner


@dataclass
class CandidateScore:
    student: StudentProfile
    course: Course
    score: float


def _preference_score(preference: StudentCoursePreference) -> float:
    return max(0.0, 100 - (preference.rank - 1) * 10)


def _interest_bonus(student: StudentProfile, course: Course) -> float:
    if not student.interests or not course.track:
        return 0.0
    normalized_interests = {
        interest.strip().lower()
        for interest in student.interests.split(",")
        if interest.strip()
    }
    return 15.0 if course.track.value.lower() in normalized_interests else 0.0


def _feedback_score(student: StudentProfile, course: Course) -> float:
    feedback_entries = getattr(student, "instructor_feedback", []) or []
    course_specific = [
        normalize_rating(entry.rating)
        for entry in feedback_entries
        if entry.course_id == course.id
    ]
    if course_specific:
        return sum(course_specific) / len(course_specific)

    overall = [normalize_rating(entry.rating) for entry in feedback_entries]
    if overall:
        return sum(overall) / len(overall) * 0.5
    return 0.0


GRADE_SCALE = {
    "A+": 4.33,
    "A": 4.0,
    "A-": 3.67,
    "B+": 3.33,
    "B": 3.0,
    "B-": 2.67,
    "C+": 2.33,
    "C": 2.0,
    "C-": 1.67,
    "D": 1.0,
    "F": 0.0,
}


def _grade_to_score(raw_grade: str | None) -> float:
    if raw_grade is None:
        return 0.0
    if isinstance(raw_grade, str):
        value = raw_grade.strip().upper()
        if not value:
            return 0.0
        if value in GRADE_SCALE:
            numeric = GRADE_SCALE[value]
        else:
            try:
                numeric = float(value)
            except ValueError:
                return 0.0
    else:
        numeric = float(raw_grade)

    if numeric <= 4.33:
        return max(0.0, min(100.0, (numeric / 4.33) * 100))
    if numeric <= 100:
        return max(0.0, min(100.0, numeric))
    return 100.0


def evaluate_candidate(student: StudentProfile, course: Course) -> float:
    preference = next(
        (pref for pref in student.preferences if pref.course_id == course.id),
        None,
    )
    preference_score = _preference_score(preference) if preference else 0.0
    track_bonus = _interest_bonus(student, course)

    application_bonus = 5.0 if student.resume_text or student.transcript_text else 0.0
    skill_match = skill_miner.score_match(student, course)
    instructor_feedback_score = _feedback_score(student, course)

    faculty_priority = 1.0 if preference and preference.faculty_requested else 0.0
    course_grade = _grade_to_score(preference.grade_in_course) if preference else 0.0
    basket_grade = (
        _grade_to_score(preference.basket_grade_average) if preference else 0.0
    )

    # Compose a single score while respecting lexicographic priority ordering
    score = (
        faculty_priority * 1_000_000_000_000
        + course_grade * 1_000_000_000
        + basket_grade * 1_000_000
        + preference_score * 1_000
        + skill_match.weighted_score * 100
        + instructor_feedback_score * 10
        + track_bonus
        + application_bonus
    )
    return score


def run_matching(db: Session, *, course_ids: Iterable[int] | None = None) -> Tuple[List[Assignment], List[int]]:
    courses_query = db.query(Course)
    if course_ids:
        courses_query = courses_query.filter(Course.id.in_(list(course_ids)))
    courses = courses_query.all()

    students: List[StudentProfile] = (
        db.query(StudentProfile)
        .join(StudentCoursePreference)
        .filter(StudentCoursePreference.course_id.in_([course.id for course in courses]))
        .all()
    )

    existing_assignment_keys = {
        (assignment.student_id, assignment.course_id)
        for assignment in db.query(Assignment).all()
    }

    assignments: List[Assignment] = []
    skipped_students: List[int] = []

    for course in courses:
        vacancies = course.vacancies - len([a for a in course.assignments])
        if vacancies <= 0:
            continue

        candidate_scores: List[CandidateScore] = []
        for student in students:
            if not any(pref.course_id == course.id for pref in student.preferences):
                continue
            if (student.id, course.id) in existing_assignment_keys:
                continue
            score = evaluate_candidate(student, course)
            candidate_scores.append(CandidateScore(student=student, course=course, score=score))

        candidate_scores.sort(key=lambda cs: cs.score, reverse=True)
        selected = candidate_scores[: vacancies]
        for candidate in selected:
            assignment = Assignment(student_id=candidate.student.id, course_id=course.id)
            assignments.append(assignment)
            existing_assignment_keys.add((candidate.student.id, course.id))
            course.vacancies = max(0, course.vacancies - 1)

        skipped_students.extend(
            [candidate.student.id for candidate in candidate_scores[vacancies:]]
        )

    return assignments, skipped_students

