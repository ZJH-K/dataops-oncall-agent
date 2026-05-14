from typing import Any, TypedDict


class DiagnosisState(TypedDict, total=False):
    session_id: str
    raw_alert: str
    alert_context: dict[str, Any]
    selected_diagnosis_skill: dict[str, Any]
    candidate_diagnosis_skills: list[dict[str, Any]]
    retrieved_docs: list[dict[str, Any]]
    plan: list[dict[str, Any]]
    pending_tools: list[str]
    tool_calls: list[dict[str, Any]]
    llm_decisions: list[dict[str, Any]]
    evidence: dict[str, Any]
    coverage_result: dict[str, Any]
    final_report: str
    incident_id: str
    needs_clarification: bool
    clarification_question: str
    confidence_limit: str
    errors: list[dict[str, Any]]
    coverage_retry_count: int


DEMO_BIZ_DATE = "2026-05-14"
DEMO_LOOKBACK_START_DATE = "2026-05-08"
