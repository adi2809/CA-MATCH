"""Skill graph miner for linking student skills to course competencies."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable, Optional, Set

from ..models import Course, StudentProfile

_STOPWORDS = {
    "and",
    "or",
    "for",
    "the",
    "with",
    "using",
    "from",
    "into",
    "via",
    "to",
    "in",
    "of",
    "a",
    "an",
}
_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9+/#&-]{2,}")


@dataclass
class SkillMatchScore:
    matched_skills: Set[str]
    coverage: float
    weighted_score: float


class SkillGraphMiner:
    """Extract and score relationships between student skills and courses."""

    def __init__(self) -> None:
        self._course_cache: dict[int, dict[str, float]] = {}

    def reset(self) -> None:
        """Clear cached competency matrices (primarily for tests)."""

        self._course_cache.clear()

    def extract_keywords_from_texts(self, *texts: Optional[str]) -> Set[str]:
        keywords: Set[str] = set()
        for text in texts:
            if not text:
                continue
            for token in _TOKEN_PATTERN.findall(text):
                normalized = token.strip().lower()
                if not normalized or normalized in _STOPWORDS:
                    continue
                keywords.add(normalized)
        return keywords

    def serialize_keywords(self, keywords: Iterable[str]) -> str | None:
        cleaned = sorted({kw.strip().lower() for kw in keywords if kw})
        return json.dumps(cleaned) if cleaned else None

    def deserialize_keywords(self, raw: Optional[str]) -> Set[str]:
        if not raw:
            return set()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {item.strip().lower() for item in raw.split(",") if item.strip()}
        return {
            str(item).strip().lower()
            for item in data
            if isinstance(item, str) and item.strip()
        }

    def _parse_competencies(self, course: Course) -> dict[str, float]:
        if course.id in self._course_cache:
            return self._course_cache[course.id]

        competencies: dict[str, float] = {}
        raw = course.competency_matrix
        if raw:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = None
            if isinstance(data, dict):
                source = data.get("skills", data)
                for key, value in source.items():
                    normalized = str(key).strip().lower()
                    if not normalized:
                        continue
                    try:
                        weight = float(value)
                    except (TypeError, ValueError):
                        weight = 1.0
                    competencies[normalized] = max(0.0, weight)
            elif isinstance(data, list):
                for item in data:
                    normalized = str(item).strip().lower()
                    if normalized:
                        competencies[normalized] = 1.0
            else:
                for part in raw.split(","):
                    normalized = part.strip().lower()
                    if normalized:
                        competencies[normalized] = 1.0

        self._course_cache[course.id] = competencies
        return competencies

    def student_keywords(self, student: StudentProfile) -> Set[str]:
        stored = self.deserialize_keywords(student.skill_keywords)
        if stored:
            return stored
        return self.extract_keywords_from_texts(
            student.resume_text,
            student.transcript_text,
        )

    def score_match(self, student: StudentProfile, course: Course) -> SkillMatchScore:
        student_skills = self.student_keywords(student)
        competencies = self._parse_competencies(course)
        if not student_skills or not competencies:
            return SkillMatchScore(set(), 0.0, 0.0)

        matched = {skill for skill in student_skills if skill in competencies}
        if not matched:
            return SkillMatchScore(set(), 0.0, 0.0)

        total_weight = sum(competencies.values())
        if total_weight <= 0:
            total_weight = float(len(competencies))
        matched_weight = sum(competencies[skill] for skill in matched)
        coverage = len(matched) / len(competencies)
        weighted_score = (matched_weight / total_weight) * 100.0
        return SkillMatchScore(matched, coverage, weighted_score)


skill_miner = SkillGraphMiner()
