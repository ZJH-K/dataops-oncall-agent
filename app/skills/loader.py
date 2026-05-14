from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from app.skills.models import DiagnosisSkill, REQUIRED_SKILL_FIELDS, SkillExample


DEFAULT_SKILL_DIR = Path(__file__).resolve().parent / "builtin"


class SkillLoadError(ValueError):
    pass


def _ensure_list(value: Any, field_name: str, skill_path: Path) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise SkillLoadError(f"{skill_path}: {field_name} must be a list of strings")
    return value


def _load_examples(path: Path) -> list[SkillExample]:
    with path.open("r", encoding="utf-8") as file:
        raw_examples = json.load(file)

    if not isinstance(raw_examples, list):
        raise SkillLoadError(f"{path}: examples.json must contain a list")

    examples: list[SkillExample] = []
    for raw in raw_examples:
        if not isinstance(raw, dict):
            raise SkillLoadError(f"{path}: each example must be an object")
        examples.append(
            SkillExample(
                alert=str(raw["alert"]),
                expected_skill=str(raw["expected_skill"]),
                expected_entities=dict(raw.get("expected_entities", {})),
                expected_tools=list(raw.get("expected_tools", [])),
            )
        )
    return examples


def load_skill(skill_yaml_path: Path) -> DiagnosisSkill:
    with skill_yaml_path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file)

    if not isinstance(raw, dict):
        raise SkillLoadError(f"{skill_yaml_path}: skill.yaml must contain an object")

    missing = REQUIRED_SKILL_FIELDS - set(raw)
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise SkillLoadError(f"{skill_yaml_path}: missing required fields: {missing_list}")

    skill_dir = skill_yaml_path.parent
    runbook_file = str(raw.get("runbook", "runbook.md"))
    examples_file = str(raw.get("examples", "examples.json"))
    runbook_path = skill_dir / runbook_file
    examples_path = skill_dir / examples_file

    if not runbook_path.exists():
        raise SkillLoadError(f"{skill_yaml_path}: runbook file not found: {runbook_file}")
    if not examples_path.exists():
        raise SkillLoadError(f"{skill_yaml_path}: examples file not found: {examples_file}")

    name = str(raw["name"])
    return DiagnosisSkill(
        name=name,
        display_name=str(raw.get("display_name", name.replace("_", " ").title())),
        version=int(raw.get("version", 1)),
        summary=str(raw.get("summary", "")),
        triggers=_ensure_list(raw["triggers"], "triggers", skill_yaml_path),
        symptoms=_ensure_list(raw.get("symptoms", []), "symptoms", skill_yaml_path),
        required_tools=_ensure_list(raw["required_tools"], "required_tools", skill_yaml_path),
        evidence_requirements=_ensure_list(
            raw["evidence_requirements"],
            "evidence_requirements",
            skill_yaml_path,
        ),
        risk_level=str(raw.get("risk_level", "medium")),
        requires_confirmation=bool(raw.get("requires_confirmation", False)),
        output_schema=str(raw.get("output_schema", "incident_report")),
        runbook=runbook_file,
        examples=examples_file,
        path=skill_dir,
        runbook_text=runbook_path.read_text(encoding="utf-8"),
        examples_data=_load_examples(examples_path),
    )


def load_builtin_skills(skill_dir: Path = DEFAULT_SKILL_DIR) -> dict[str, DiagnosisSkill]:
    skills: dict[str, DiagnosisSkill] = {}
    for skill_yaml_path in sorted(skill_dir.glob("*/skill.yaml")):
        skill = load_skill(skill_yaml_path)
        if skill.name in skills:
            raise SkillLoadError(f"Duplicate Diagnosis Skill name: {skill.name}")
        skills[skill.name] = skill
    return skills

