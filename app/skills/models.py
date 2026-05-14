from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REQUIRED_SKILL_FIELDS = {
    "name",
    "triggers",
    "required_tools",
    "evidence_requirements",
}


@dataclass(frozen=True)
class SkillExample:
    alert: str
    expected_skill: str
    expected_entities: dict[str, Any] = field(default_factory=dict)
    expected_tools: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DiagnosisSkill:
    name: str
    display_name: str
    version: int
    summary: str
    triggers: list[str]
    symptoms: list[str]
    required_tools: list[str]
    evidence_requirements: list[str]
    risk_level: str
    requires_confirmation: bool
    output_schema: str
    runbook: str
    examples: str
    path: Path
    runbook_text: str
    examples_data: list[SkillExample]

    @property
    def trigger_terms(self) -> set[str]:
        return {
            term.casefold()
            for term in [*self.triggers, *self.symptoms, self.name, self.display_name]
            if term
        }


@dataclass(frozen=True)
class SkillMatch:
    skill_name: str | None
    confidence: float
    needs_clarification: bool
    reason: str
    matched_terms: list[str] = field(default_factory=list)
    candidate_scores: dict[str, float] = field(default_factory=dict)

