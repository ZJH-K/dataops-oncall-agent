from __future__ import annotations

from typing import Any

from app.tools.providers.sqlite_provider import SQLiteDataOpsToolProvider
from app.workflow.nodes.planner import plan_step_for_tool
from app.workflow.state import DiagnosisState


def tool_executor_node(
    state: DiagnosisState,
    database_url: str | None,
) -> dict[str, Any]:
    provider = SQLiteDataOpsToolProvider(database_url=database_url)
    existing_calls = list(state.get("tool_calls", []))
    evidence = dict(state.get("evidence", {}))

    steps = _steps_to_execute(state)
    new_calls: list[dict[str, Any]] = []
    for step in steps:
        tool_name = step["tool_name"]
        arguments = {
            key: value
            for key, value in dict(step.get("arguments", {})).items()
            if value is not None
        }
        arguments["session_id"] = state["session_id"]

        tool = getattr(provider, tool_name)
        response = tool(**arguments)
        call_record = {
            "tool_name": tool_name,
            "arguments": arguments,
            **response,
        }
        new_calls.append(call_record)
        _merge_evidence(evidence, tool_name, response)

    return {
        "tool_calls": [*existing_calls, *new_calls],
        "evidence": evidence,
        "pending_tools": [],
    }


def _steps_to_execute(state: DiagnosisState) -> list[dict[str, Any]]:
    pending_tools = state.get("pending_tools", [])
    if pending_tools:
        return [plan_step_for_tool(tool_name, state) for tool_name in pending_tools]
    return list(state.get("plan", []))


def _merge_evidence(
    evidence: dict[str, Any],
    tool_name: str,
    response: dict[str, Any],
) -> None:
    if response.get("status") != "success":
        evidence.setdefault("tool_failures", []).append(
            {
                "tool_name": tool_name,
                "error_message": response.get("error_message"),
                "tool_call_id": response.get("tool_call_id"),
            }
        )
        return

    result = response.get("result") or {}
    if tool_name == "query_task_runs":
        evidence["task_runs"] = result.get("task_runs", [])
    elif tool_name == "query_table_partitions":
        evidence["table_partitions"] = result.get("partitions", [])
    elif tool_name == "query_data_volume":
        evidence["data_volume"] = result.get("volume_stats", [])
    elif tool_name == "query_null_rate":
        evidence["null_rate"] = result.get("null_rate_checks", [])
    elif tool_name == "query_lineage":
        evidence["lineage"] = result

