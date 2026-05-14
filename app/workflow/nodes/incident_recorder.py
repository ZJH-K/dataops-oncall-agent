from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any

from app.db.connection import db_connection
from app.tools.providers.sqlite_provider import SQLiteDataOpsToolProvider
from app.workflow.state import DiagnosisState


SHANGHAI_TZ = timezone(timedelta(hours=8))


def incident_recorder_node(
    state: DiagnosisState,
    database_url: str | None,
) -> dict[str, Any]:
    provider = SQLiteDataOpsToolProvider(database_url=database_url)
    status = "needs_clarification" if state.get("needs_clarification") else "completed"
    skill_name = state.get("selected_diagnosis_skill", {}).get("name")
    severity = _severity_for_state(state)
    response = provider.create_incident_report(
        {
            "title": _title_for_state(state),
            "raw_alert": state.get("raw_alert", ""),
            "status": status,
            "severity": severity,
            "selected_diagnosis_skill": skill_name,
            "alert_context": state.get("alert_context", {}),
            "coverage_result": state.get("coverage_result", {}),
            "final_report": state.get("final_report", ""),
            "confidence_limit": state.get("confidence_limit"),
        },
        session_id=state["session_id"],
    )

    incident_id = None
    if response.get("status") == "success":
        incident_id = response.get("result", {}).get("incident_id")
        _persist_session_state(database_url, state, str(incident_id))

    return {
        "incident_id": incident_id,
        "tool_calls": [
            *state.get("tool_calls", []),
            {"tool_name": "create_incident_report", **response},
        ],
    }


def _persist_session_state(
    database_url: str | None,
    state: DiagnosisState,
    incident_id: str,
) -> None:
    state_snapshot: dict[str, Any] = {
        "raw_alert": state.get("raw_alert"),
        "alert_context": state.get("alert_context", {}),
        "selected_diagnosis_skill": state.get("selected_diagnosis_skill", {}),
        "retrieved_docs": state.get("retrieved_docs", []),
        "plan": state.get("plan", []),
        "tool_calls": state.get("tool_calls", []),
        "evidence": state.get("evidence", {}),
        "coverage_result": state.get("coverage_result", {}),
        "incident_id": incident_id,
    }
    now = datetime.now(SHANGHAI_TZ).isoformat()
    context = state.get("alert_context", {})
    with db_connection(database_url) as connection:
        connection.execute(
            """
            UPDATE sessions
            SET
                current_incident_id = ?,
                current_table = ?,
                current_task = ?,
                current_field = ?,
                selected_diagnosis_skill = ?,
                state_json = ?,
                updated_at = ?
            WHERE session_id = ?
            """,
            (
                incident_id,
                context.get("table_name"),
                context.get("task_name"),
                context.get("field_name"),
                state.get("selected_diagnosis_skill", {}).get("name"),
                json.dumps(state_snapshot, ensure_ascii=False, default=str),
                now,
                state["session_id"],
            ),
        )


def _severity_for_state(state: DiagnosisState) -> str:
    skill = state.get("selected_diagnosis_skill", {})
    if skill.get("risk_level") == "high":
        return "P1"
    if state.get("confidence_limit"):
        return "P3"
    if skill.get("name") == "data_volume_drop":
        return "P2"
    return "P3"


def _title_for_state(state: DiagnosisState) -> str:
    context = state.get("alert_context", {})
    if state.get("needs_clarification"):
        return "Needs clarification for DataOps diagnosis"
    table_name = context.get("table_name")
    skill_name = state.get("selected_diagnosis_skill", {}).get("name")
    if table_name and skill_name:
        return f"{table_name} {skill_name}"
    return "DataOps diagnosis report"

