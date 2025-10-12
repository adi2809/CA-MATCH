from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

from sqlalchemy.orm import Session

from ..models import Assignment, Course, StudentCoursePreference, StudentProfile


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


def evaluate_candidate(student: StudentProfile, course: Course) -> float:
    preference = next(
        (pref for pref in student.preferences if pref.course_id == course.id),
        None,
    )
    base_score = _preference_score(preference) if preference else 40.0
    track_bonus = _interest_bonus(student, course)

    application_bonus = 5.0 if student.resume_path and student.transcript_path else 0.0
    return base_score + track_bonus + application_bonus


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

