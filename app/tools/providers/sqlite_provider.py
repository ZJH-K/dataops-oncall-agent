from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import json
from time import perf_counter
from typing import Any
from uuid import uuid4
import sqlite3

from app.db.connection import db_connection
from app.db.repositories import rows_to_dicts
from app.db.schema import initialize_schema
from app.tools.schemas import ToolResponse


SHANGHAI_TZ = timezone(timedelta(hours=8))
VALID_LINEAGE_DIRECTIONS = {"upstream", "downstream", "both"}


def _now_iso() -> str:
    return datetime.now(SHANGHAI_TZ).isoformat()


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _require_text(value: str | None, field_name: str) -> str:
    if value is None or not str(value).strip():
        raise ValueError(f"{field_name} is required")
    return str(value).strip()


class SQLiteDataOpsToolProvider:
    def __init__(
        self,
        database_url: str | None = None,
        default_session_id: str = "demo_session",
    ) -> None:
        self.database_url = database_url
        self.default_session_id = default_session_id

    def query_task_runs(
        self,
        task_name: str | None = None,
        table_name: str | None = None,
        date: str | None = None,
        status: str | None = None,
        session_id: str = "demo_session",
        incident_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        arguments = {
            "task_name": task_name,
            "table_name": table_name,
            "date": date,
            "status": status,
            "session_id": session_id,
            "incident_id": incident_id,
            "run_id": run_id,
        }

        def handler(connection: sqlite3.Connection) -> dict[str, Any]:
            sql = """
                SELECT
                    tr.run_id,
                    tr.dag_id,
                    tr.task_name,
                    tr.biz_date,
                    tr.status,
                    tr.start_time,
                    tr.end_time,
                    tr.duration_seconds,
                    tr.error_type,
                    tr.error_message,
                    tr.log_excerpt,
                    tr.retry_count,
                    d.produces_table
                FROM task_runs tr
                JOIN dags d ON tr.dag_id = d.dag_id
                WHERE (? IS NULL OR tr.dag_id = ? OR tr.task_name = ?)
                  AND (? IS NULL OR d.produces_table = ?)
                  AND (? IS NULL OR tr.biz_date = ?)
                  AND (? IS NULL OR tr.status = ?)
                ORDER BY tr.biz_date DESC, tr.start_time DESC
            """
            rows = connection.execute(
                sql,
                (
                    task_name,
                    task_name,
                    task_name,
                    table_name,
                    table_name,
                    date,
                    date,
                    status,
                    status,
                ),
            ).fetchall()
            task_runs = rows_to_dicts(rows)
            return {"task_runs": task_runs, "count": len(task_runs)}

        return self._execute_tool(
            "query_task_runs",
            arguments,
            handler,
            session_id=session_id,
            incident_id=incident_id,
            run_id=run_id,
        )

    def query_table_partitions(
        self,
        table_name: str,
        date: str | None = None,
        session_id: str = "demo_session",
        incident_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        arguments = {
            "table_name": table_name,
            "date": date,
            "session_id": session_id,
            "incident_id": incident_id,
            "run_id": run_id,
        }

        def handler(connection: sqlite3.Connection) -> dict[str, Any]:
            target_table = _require_text(table_name, "table_name")
            sql = """
                SELECT
                    table_name,
                    partition_date,
                    partition_name,
                    status,
                    row_count,
                    file_size_mb,
                    created_time,
                    updated_time,
                    error_message
                FROM table_partitions
                WHERE table_name = ?
                  AND (? IS NULL OR partition_date = ?)
                ORDER BY partition_date DESC
            """
            rows = connection.execute(sql, (target_table, date, date)).fetchall()
            partitions = rows_to_dicts(rows)
            return {"partitions": partitions, "count": len(partitions)}

        return self._execute_tool(
            "query_table_partitions",
            arguments,
            handler,
            session_id=session_id,
            incident_id=incident_id,
            run_id=run_id,
        )

    def query_data_volume(
        self,
        table_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
        session_id: str = "demo_session",
        incident_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        arguments = {
            "table_name": table_name,
            "start_date": start_date,
            "end_date": end_date,
            "session_id": session_id,
            "incident_id": incident_id,
            "run_id": run_id,
        }

        def handler(connection: sqlite3.Connection) -> dict[str, Any]:
            target_table = _require_text(table_name, "table_name")
            sql = """
                SELECT
                    table_name,
                    stat_date,
                    row_count,
                    previous_day_row_count,
                    seven_day_avg_row_count,
                    change_ratio,
                    anomaly_flag,
                    anomaly_type
                FROM data_volume_stats
                WHERE table_name = ?
                  AND (? IS NULL OR stat_date >= ?)
                  AND (? IS NULL OR stat_date <= ?)
                ORDER BY stat_date
            """
            rows = connection.execute(
                sql,
                (target_table, start_date, start_date, end_date, end_date),
            ).fetchall()
            volume_stats = rows_to_dicts(rows)
            return {"volume_stats": volume_stats, "count": len(volume_stats)}

        return self._execute_tool(
            "query_data_volume",
            arguments,
            handler,
            session_id=session_id,
            incident_id=incident_id,
            run_id=run_id,
        )

    def query_null_rate(
        self,
        table_name: str,
        field_name: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        session_id: str = "demo_session",
        incident_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        arguments = {
            "table_name": table_name,
            "field_name": field_name,
            "start_date": start_date,
            "end_date": end_date,
            "session_id": session_id,
            "incident_id": incident_id,
            "run_id": run_id,
        }

        def handler(connection: sqlite3.Connection) -> dict[str, Any]:
            target_table = _require_text(table_name, "table_name")
            sql = """
                SELECT
                    check_id,
                    table_name,
                    field_name,
                    biz_date,
                    actual_value AS null_rate,
                    expected_value,
                    threshold,
                    status,
                    severity,
                    message
                FROM quality_checks
                WHERE table_name = ?
                  AND check_type = 'null_rate'
                  AND (? IS NULL OR field_name = ?)
                  AND (? IS NULL OR biz_date >= ?)
                  AND (? IS NULL OR biz_date <= ?)
                ORDER BY biz_date
            """
            rows = connection.execute(
                sql,
                (
                    target_table,
                    field_name,
                    field_name,
                    start_date,
                    start_date,
                    end_date,
                    end_date,
                ),
            ).fetchall()
            null_rate_checks = rows_to_dicts(rows)
            return {"null_rate_checks": null_rate_checks, "count": len(null_rate_checks)}

        return self._execute_tool(
            "query_null_rate",
            arguments,
            handler,
            session_id=session_id,
            incident_id=incident_id,
            run_id=run_id,
        )

    def query_lineage(
        self,
        table_name: str,
        direction: str = "downstream",
        depth: int = 3,
        session_id: str = "demo_session",
        incident_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        arguments = {
            "table_name": table_name,
            "direction": direction,
            "depth": depth,
            "session_id": session_id,
            "incident_id": incident_id,
            "run_id": run_id,
        }

        def handler(connection: sqlite3.Connection) -> dict[str, Any]:
            target_table = _require_text(table_name, "table_name")
            normalized_direction = direction.casefold()
            if normalized_direction not in VALID_LINEAGE_DIRECTIONS:
                raise ValueError(
                    "direction must be one of: upstream, downstream, both"
                )
            max_depth = max(1, min(int(depth), 5))
            result: dict[str, Any] = {
                "table_name": target_table,
                "direction": normalized_direction,
                "depth": max_depth,
            }
            if normalized_direction in {"downstream", "both"}:
                result["downstream"] = self._query_downstream(
                    connection,
                    target_table,
                    max_depth,
                )
            if normalized_direction in {"upstream", "both"}:
                result["upstream"] = self._query_upstream(
                    connection,
                    target_table,
                    max_depth,
                )
            return result

        return self._execute_tool(
            "query_lineage",
            arguments,
            handler,
            session_id=session_id,
            incident_id=incident_id,
            run_id=run_id,
        )

    def create_incident_report(
        self,
        report_payload: dict[str, Any],
        session_id: str = "demo_session",
        incident_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        arguments = {
            "report_payload": report_payload,
            "session_id": session_id,
            "incident_id": incident_id,
            "run_id": run_id,
        }

        def handler(connection: sqlite3.Connection) -> dict[str, Any]:
            if not isinstance(report_payload, dict):
                raise ValueError("report_payload must be a JSON object")

            target_incident_id = str(
                report_payload.get("incident_id") or incident_id or f"inc_{uuid4().hex[:12]}"
            )
            title = str(report_payload.get("title") or "DataOps diagnosis report")
            raw_alert = str(report_payload.get("raw_alert") or "")
            if not raw_alert:
                raise ValueError("report_payload.raw_alert is required")

            now = _now_iso()
            connection.execute(
                """
                INSERT INTO incidents (
                    incident_id,
                    session_id,
                    title,
                    raw_alert,
                    status,
                    severity,
                    selected_diagnosis_skill,
                    alert_context_json,
                    coverage_result_json,
                    final_report,
                    confidence_limit,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    title = excluded.title,
                    raw_alert = excluded.raw_alert,
                    status = excluded.status,
                    severity = excluded.severity,
                    selected_diagnosis_skill = excluded.selected_diagnosis_skill,
                    alert_context_json = excluded.alert_context_json,
                    coverage_result_json = excluded.coverage_result_json,
                    final_report = excluded.final_report,
                    confidence_limit = excluded.confidence_limit,
                    updated_at = excluded.updated_at
                """,
                (
                    target_incident_id,
                    session_id,
                    title,
                    raw_alert,
                    str(report_payload.get("status") or "completed"),
                    str(report_payload.get("severity") or "P3"),
                    report_payload.get("selected_diagnosis_skill"),
                    _json(report_payload.get("alert_context", {})),
                    _json(report_payload.get("coverage_result", {})),
                    report_payload.get("final_report"),
                    report_payload.get("confidence_limit"),
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE sessions
                SET current_incident_id = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (target_incident_id, now, session_id),
            )
            return {
                "incident_id": target_incident_id,
                "status": str(report_payload.get("status") or "completed"),
            }

        return self._execute_tool(
            "create_incident_report",
            arguments,
            handler,
            session_id=session_id,
            incident_id=incident_id,
            run_id=run_id,
        )

    def _execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        handler: Callable[[sqlite3.Connection], dict[str, Any]],
        session_id: str,
        incident_id: str | None,
        run_id: str | None,
    ) -> dict[str, Any]:
        tool_call_id = f"toolcall_{uuid4().hex[:16]}"
        started_at = perf_counter()

        with db_connection(self.database_url) as connection:
            initialize_schema(connection)
            effective_session_id = session_id or self.default_session_id
            self._ensure_session(connection, effective_session_id)

            try:
                result = handler(connection)
                latency_ms = int((perf_counter() - started_at) * 1000)
                result_summary = self._summarize_result(tool_name, result)
                log_incident_id = incident_id
                if log_incident_id is None and isinstance(result, dict):
                    maybe_incident_id = result.get("incident_id")
                    log_incident_id = str(maybe_incident_id) if maybe_incident_id else None

                self._log_tool_call(
                    connection=connection,
                    tool_call_id=tool_call_id,
                    run_id=run_id,
                    incident_id=log_incident_id,
                    session_id=effective_session_id,
                    tool_name=tool_name,
                    arguments=arguments,
                    status="success",
                    result=result,
                    result_summary=result_summary,
                    error_message=None,
                    latency_ms=latency_ms,
                )
                return ToolResponse(
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    status="success",
                    latency_ms=latency_ms,
                    result_summary=result_summary,
                    result=result,
                ).to_dict()
            except Exception as exc:
                latency_ms = int((perf_counter() - started_at) * 1000)
                error_message = str(exc)
                self._log_tool_call(
                    connection=connection,
                    tool_call_id=tool_call_id,
                    run_id=run_id,
                    incident_id=incident_id,
                    session_id=effective_session_id,
                    tool_name=tool_name,
                    arguments=arguments,
                    status="failed",
                    result=None,
                    result_summary="tool call failed",
                    error_message=error_message,
                    latency_ms=latency_ms,
                )
                return ToolResponse(
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    status="failed",
                    latency_ms=latency_ms,
                    result_summary="tool call failed",
                    error_message=error_message,
                ).to_dict()

    def _ensure_session(
        self,
        connection: sqlite3.Connection,
        session_id: str,
    ) -> None:
        now = _now_iso()
        connection.execute(
            """
            INSERT INTO sessions (
                session_id,
                state_json,
                created_at,
                updated_at
            )
            VALUES (?, '{}', ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET updated_at = excluded.updated_at
            """,
            (session_id, now, now),
        )

    def _log_tool_call(
        self,
        connection: sqlite3.Connection,
        tool_call_id: str,
        run_id: str | None,
        incident_id: str | None,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        status: str,
        result: dict[str, Any] | None,
        result_summary: str,
        error_message: str | None,
        latency_ms: int,
    ) -> None:
        safe_run_id = self._existing_value(connection, "diagnosis_runs", "run_id", run_id)
        safe_incident_id = self._existing_value(
            connection,
            "incidents",
            "incident_id",
            incident_id,
        )
        connection.execute(
            """
            INSERT INTO tool_call_logs (
                tool_call_id,
                run_id,
                incident_id,
                session_id,
                tool_name,
                arguments_json,
                status,
                result_json,
                result_summary,
                error_message,
                latency_ms,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tool_call_id,
                safe_run_id,
                safe_incident_id,
                session_id,
                tool_name,
                _json(arguments),
                status,
                _json(result) if result is not None else None,
                result_summary,
                error_message,
                latency_ms,
                _now_iso(),
            ),
        )

    def _existing_value(
        self,
        connection: sqlite3.Connection,
        table_name: str,
        column_name: str,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        row = connection.execute(
            f"SELECT 1 FROM {table_name} WHERE {column_name} = ? LIMIT 1",
            (value,),
        ).fetchone()
        return value if row else None

    def _summarize_result(self, tool_name: str, result: dict[str, Any]) -> str:
        if tool_name == "query_task_runs":
            return f"{result.get('count', 0)} task runs"
        if tool_name == "query_table_partitions":
            return f"{result.get('count', 0)} partitions"
        if tool_name == "query_data_volume":
            return f"{result.get('count', 0)} volume records"
        if tool_name == "query_null_rate":
            return f"{result.get('count', 0)} null-rate checks"
        if tool_name == "query_lineage":
            downstream = len(result.get("downstream", []))
            upstream = len(result.get("upstream", []))
            return f"{upstream} upstream, {downstream} downstream lineage nodes"
        if tool_name == "create_incident_report":
            return f"incident saved: {result.get('incident_id')}"
        return "tool call succeeded"

    def _query_downstream(
        self,
        connection: sqlite3.Connection,
        table_name: str,
        max_depth: int,
    ) -> list[dict[str, Any]]:
        sql = """
            WITH RECURSIVE downstream(table_name, depth) AS (
                SELECT downstream_table, 1
                FROM lineage_edges
                WHERE upstream_table = ?

                UNION ALL

                SELECT le.downstream_table, d.depth + 1
                FROM lineage_edges le
                JOIN downstream d ON le.upstream_table = d.table_name
                WHERE d.depth < ?
            )
            SELECT table_name, depth
            FROM downstream
            ORDER BY depth, table_name
        """
        return rows_to_dicts(connection.execute(sql, (table_name, max_depth)).fetchall())

    def _query_upstream(
        self,
        connection: sqlite3.Connection,
        table_name: str,
        max_depth: int,
    ) -> list[dict[str, Any]]:
        sql = """
            WITH RECURSIVE upstream(table_name, depth) AS (
                SELECT upstream_table, 1
                FROM lineage_edges
                WHERE downstream_table = ?

                UNION ALL

                SELECT le.upstream_table, u.depth + 1
                FROM lineage_edges le
                JOIN upstream u ON le.downstream_table = u.table_name
                WHERE u.depth < ?
            )
            SELECT table_name, depth
            FROM upstream
            ORDER BY depth, table_name
        """
        return rows_to_dicts(connection.execute(sql, (table_name, max_depth)).fetchall())

