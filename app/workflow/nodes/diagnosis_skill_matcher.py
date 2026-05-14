from __future__ import annotations

from typing import Any

from app.skills.loader import load_builtin_skills
from app.skills.matcher import DiagnosisSkillMatcher
from app.workflow.llm_decisions import append_llm_decision, ask_deepseek_json
from app.workflow.state import DiagnosisState


def diagnosis_skill_matcher_node(state: DiagnosisState) -> dict[str, Any]:
    raw_alert = state.get("raw_alert", "")
    skills = load_builtin_skills()
    matcher = DiagnosisSkillMatcher(skills)
    result = matcher.match(raw_alert)
    candidate_skills = [
        {"name": name, "score": score}
        for name, score in sorted(
            result.candidate_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]
    llm_match, llm_decision = _match_with_deepseek(
        raw_alert=raw_alert,
        alert_context=state.get("alert_context", {}),
        candidate_skills=candidate_skills,
        skill_names=list(skills),
    )
    selected_skill_name = result.skill_name
    selected_confidence = result.confidence
    selected_reason = result.reason
    matched_terms = result.matched_terms

    if _is_valid_llm_match(llm_match, list(skills)):
        llm_skill_name = str(llm_match["skill_name"])
        llm_confidence = float(llm_match.get("confidence", 0.0))
        if result.needs_clarification or llm_confidence >= max(result.confidence, 0.65):
            selected_skill_name = llm_skill_name
            selected_confidence = round(llm_confidence, 4)
            selected_reason = f"DeepSeek decision: {llm_match.get('reason', '')}".strip()
            matched_terms = list(result.matched_terms)

    if selected_skill_name is None or (
        result.needs_clarification
        and not _is_valid_llm_match(llm_match, list(skills))
    ):
        return {
            "candidate_diagnosis_skills": candidate_skills,
            "llm_decisions": append_llm_decision(state.get("llm_decisions"), llm_decision),
            "needs_clarification": True,
            "clarification_question": (
                "我还不能稳定判断故障类型。请补充表名、任务名、字段名，"
                "以及异常表现，例如数据量下降、分区缺失、任务失败或空值率升高。"
            ),
        }

    skill = skills[selected_skill_name]
    return {
        "selected_diagnosis_skill": {
            "name": skill.name,
            "display_name": skill.display_name,
            "confidence": selected_confidence,
            "reason": selected_reason,
            "required_tools": skill.required_tools,
            "evidence_requirements": skill.evidence_requirements,
            "risk_level": skill.risk_level,
            "matched_terms": matched_terms,
        },
        "candidate_diagnosis_skills": candidate_skills,
        "llm_decisions": append_llm_decision(state.get("llm_decisions"), llm_decision),
        "needs_clarification": False,
        "clarification_question": "",
    }


def _match_with_deepseek(
    raw_alert: str,
    alert_context: dict[str, Any],
    candidate_skills: list[dict[str, Any]],
    skill_names: list[str],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    return ask_deepseek_json(
        node="DiagnosisSkillMatcher",
        system_prompt=(
            "你是 DataOps Diagnosis Skill 路由器。只返回 JSON，不要解释。"
            "你只能从给定 skill_names 中选择 skill_name，不能创造新 Skill。"
            "如果信息不足，返回 needs_clarification=true 且 skill_name=null。"
            "JSON 字段：skill_name, confidence, needs_clarification, reason。"
        ),
        user_prompt=(
            f"skill_names={skill_names}\n"
            f"rule_candidates={candidate_skills}\n"
            f"alert_context={alert_context}\n"
            f"raw_alert={raw_alert}"
        ),
        max_tokens=500,
    )


def _is_valid_llm_match(
    llm_match: dict[str, Any] | None,
    skill_names: list[str],
) -> bool:
    if not llm_match or llm_match.get("needs_clarification") is True:
        return False
    skill_name = llm_match.get("skill_name")
    confidence = llm_match.get("confidence", 0.0)
    return (
        isinstance(skill_name, str)
        and skill_name in skill_names
        and isinstance(confidence, int | float)
        and float(confidence) >= 0.65
    )
