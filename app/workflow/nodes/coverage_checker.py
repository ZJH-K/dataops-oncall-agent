from __future__ import annotations

from typing import Any

from app.workflow.state import DiagnosisState


def coverage_checker_node(state: DiagnosisState) -> dict[str, Any]:
    skill = state.get("selected_diagnosis_skill", {})
    required_tools = list(skill.get("required_tools", []))
    evidence_requirements = list(skill.get("evidence_requirements", []))
    tool_calls = list(state.get("tool_calls", []))
    evidence = state.get("evidence", {})

    successful_tools = {
        call.get("tool_name")
        for call in tool_calls
        if call.get("status") == "success"
    }
    failed_tools = [
        {
            "tool_name": call.get("tool_name"),
            "error_message": call.get("error_message"),
        }
        for call in tool_calls
        if call.get("status") == "failed"
    ]
    missing_tools = [
        tool_name
        for tool_name in required_tools
        if tool_name not in successful_tools
    ]
    missing_evidence = [
        requirement
        for requirement in evidence_requirements
        if not _has_evidence(requirement, evidence)
    ]

    retry_count = int(state.get("coverage_retry_count", 0))
    if missing_tools and retry_count < 1:
        return {
            "pending_tools": missing_tools,
            "coverage_retry_count": retry_count + 1,
            "coverage_result": {
                "status": "needs_more_tools",
                "action": "retry_tools",
                "required_tools": required_tools,
                "successful_tools": sorted(successful_tools),
                "missing_tools": missing_tools,
                "failed_tools": failed_tools,
                "evidence_requirements": evidence_requirements,
                "missing_evidence": missing_evidence,
                "coverage_ratio": _coverage_ratio(required_tools, successful_tools),
                "can_report": False,
            },
        }

    status = "complete"
    confidence_limit = ""
    if missing_tools or failed_tools or missing_evidence:
        status = "partial"
        confidence_limit = (
            "部分工具或证据缺失，报告只能给出受限结论，不能过度确定根因。"
        )

    return {
        "coverage_result": {
            "status": status,
            "action": "report",
            "required_tools": required_tools,
            "successful_tools": sorted(successful_tools),
            "missing_tools": missing_tools,
            "failed_tools": failed_tools,
            "evidence_requirements": evidence_requirements,
            "missing_evidence": missing_evidence,
            "coverage_ratio": _coverage_ratio(required_tools, successful_tools),
            "can_report": True,
        },
        "confidence_limit": confidence_limit,
    }


def _coverage_ratio(required_tools: list[str], successful_tools: set[str | None]) -> float:
    if not required_tools:
        return 1.0
    return round(
        len([tool for tool in required_tools if tool in successful_tools])
        / len(required_tools),
        4,
    )


def _has_evidence(requirement: str, evidence: dict[str, Any]) -> bool:
    if requirement in {"recent_row_count_trend"}:
        return bool(evidence.get("data_volume"))
    if requirement in {"current_partition_status", "upstream_partition_status"}:
        return bool(evidence.get("table_partitions"))
    if requirement in {
        "related_task_status",
        "failed_task_status",
        "error_message",
        "retry_count",
    }:
        task_runs = evidence.get("task_runs", [])
        if requirement == "failed_task_status":
            return any(row.get("status") == "failed" for row in task_runs)
        if requirement == "error_message":
            return any(row.get("error_message") for row in task_runs)
        if requirement == "retry_count":
            return any(row.get("retry_count") is not None for row in task_runs)
        return bool(task_runs)
    if requirement in {"downstream_impact"}:
        lineage = evidence.get("lineage", {})
        return bool(lineage.get("downstream") or lineage.get("upstream"))
    if requirement in {"field_null_rate_trend", "quality_check_status"}:
        return bool(evidence.get("null_rate"))
    return True

