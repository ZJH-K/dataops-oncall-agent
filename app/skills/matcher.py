from __future__ import annotations

import re

from app.skills.loader import load_builtin_skills
from app.skills.models import DiagnosisSkill, SkillMatch


DEFAULT_CONFIDENCE_THRESHOLD = 0.65


TABLE_PATTERN = re.compile(r"\b([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)?)\b")


def _normalize(text: str) -> str:
    return text.casefold().strip()


def _contains_term(alert: str, term: str) -> bool:
    normalized_term = _normalize(term)
    if not normalized_term:
        return False
    return normalized_term in alert


def _score_skill(alert: str, skill: DiagnosisSkill) -> tuple[float, list[str]]:
    matched_terms = sorted(
        term for term in skill.trigger_terms if _contains_term(alert, term)
    )
    if not matched_terms:
        return 0.0, []

    trigger_hits = sum(1 for term in skill.triggers if _contains_term(alert, term))
    symptom_hits = sum(1 for term in skill.symptoms if _contains_term(alert, term))
    name_hit = 1 if _contains_term(alert, skill.name) else 0
    example_hit = 0
    for example in skill.examples_data:
        if example.alert and _normalize(example.alert) == alert:
            example_hit = 1
            break

    score = 0.35 + (0.18 * trigger_hits) + (0.12 * symptom_hits) + (0.15 * name_hit)
    if example_hit:
        score += 0.25

    # Keep rules deterministic and easy to explain during interview demos.
    return min(score, 0.99), matched_terms


class DiagnosisSkillMatcher:
    def __init__(
        self,
        skills: dict[str, DiagnosisSkill] | None = None,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> None:
        self.skills = skills if skills is not None else load_builtin_skills()
        self.confidence_threshold = confidence_threshold

    def match(self, alert: str) -> SkillMatch:
        normalized_alert = _normalize(alert)
        candidate_scores: dict[str, float] = {}
        candidate_terms: dict[str, list[str]] = {}

        for skill in self.skills.values():
            score, matched_terms = _score_skill(normalized_alert, skill)
            candidate_scores[skill.name] = score
            candidate_terms[skill.name] = matched_terms

        if not candidate_scores:
            return SkillMatch(
                skill_name=None,
                confidence=0.0,
                needs_clarification=True,
                reason="No Diagnosis Skill registry is available.",
            )

        best_skill_name, best_score = max(
            candidate_scores.items(),
            key=lambda item: (item[1], item[0]),
        )

        if best_score < self.confidence_threshold:
            return SkillMatch(
                skill_name=None,
                confidence=best_score,
                needs_clarification=True,
                reason="No Diagnosis Skill reached the confidence threshold.",
                matched_terms=candidate_terms[best_skill_name],
                candidate_scores=candidate_scores,
            )

        return SkillMatch(
            skill_name=best_skill_name,
            confidence=best_score,
            needs_clarification=False,
            reason="Matched by deterministic Diagnosis Skill trigger rules.",
            matched_terms=candidate_terms[best_skill_name],
            candidate_scores=candidate_scores,
        )

