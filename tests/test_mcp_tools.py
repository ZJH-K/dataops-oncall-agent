from pathlib import Path
import sqlite3

import pytest

from app.db.connection import db_connection
from app.db.demo_seed import seed_demo_data
from app.tools.providers.sqlite_provider import SQLiteDataOpsToolProvider
from mcp_servers.dataops_server import invoke_tool


@pytest.fixture()
def database_url(tmp_path: Path) -> str:
    db_path = tmp_path / "demo.db"
    url = f"sqlite:///{db_path}"
    with db_connection(url) as connection:
        seed_demo_data(connection)
    return url


@pytest.fixture()
def provider(database_url: str) -> SQLiteDataOpsToolProvider:
    return SQLiteDataOpsToolProvider(database_url=database_url)


def _log_rows(database_url: str) -> list[sqlite3.Row]:
    with db_connection(database_url) as connection:
        return connection.execute(
            """
            SELECT tool_name, status, result_summary, error_message
            FROM tool_call_logs
            ORDER BY id
            """
        ).fetchall()


def test_query_task_runs_returns_failed_task_and_logs_call(
    provider: SQLiteDataOpsToolProvider,
    database_url: str,
) -> None:
    response = provider.query_task_runs(
        task_name="dwd_order_detail_daily",
        date="2026-05-14",
        session_id="test-session",
    )

    assert response["status"] == "success"
    task_runs = response["result"]["task_runs"]
    assert task_runs[0]["status"] == "failed"
    assert task_runs[0]["error_message"] == "SQL column not found: payment_status"

    logs = _log_rows(database_url)
    assert logs[-1]["tool_name"] == "query_task_runs"
    assert logs[-1]["status"] == "success"


def test_query_table_partitions_returns_missing_partition(
    provider: SQLiteDataOpsToolProvider,
) -> None:
    response = provider.query_table_partitions(
        table_name="dws_sales_daily",
        date="2026-05-14",
        session_id="test-session",
    )

    assert response["status"] == "success"
    partitions = response["result"]["partitions"]
    assert partitions[0]["status"] == "missing"
    assert partitions[0]["error_message"] == "scheduled partition not produced"


def test_query_data_volume_returns_92_percent_drop(
    provider: SQLiteDataOpsToolProvider,
) -> None:
    response = provider.query_data_volume(
        table_name="dws_sales_daily",
        start_date="2026-05-14",
        end_date="2026-05-14",
        session_id="test-session",
    )

    assert response["status"] == "success"
    volume = response["result"]["volume_stats"][0]
    assert volume["row_count"] == 800
    assert volume["previous_day_row_count"] == 10000
    assert volume["change_ratio"] == -0.92
    assert volume["anomaly_type"] == "drop"


def test_query_null_rate_returns_spike(
    provider: SQLiteDataOpsToolProvider,
) -> None:
    response = provider.query_null_rate(
        table_name="ads_user_profile",
        field_name="user_id",
        start_date="2026-05-14",
        end_date="2026-05-14",
        session_id="test-session",
    )

    assert response["status"] == "success"
    check = response["result"]["null_rate_checks"][0]
    assert check["null_rate"] == 0.35
    assert check["threshold"] == 0.02
    assert check["status"] == "failed"


def test_query_lineage_returns_downstream_impact(
    provider: SQLiteDataOpsToolProvider,
) -> None:
    response = provider.query_lineage(
        table_name="dws_sales_daily",
        direction="downstream",
        depth=2,
        session_id="test-session",
    )

    assert response["status"] == "success"
    downstream_tables = {
        row["table_name"] for row in response["result"]["downstream"]
    }
    assert downstream_tables == {"ads_revenue_dashboard", "ads_sales_report"}


def test_create_incident_report_persists_incident_and_logs_call(
    provider: SQLiteDataOpsToolProvider,
    database_url: str,
) -> None:
    response = provider.create_incident_report(
        {
            "title": "dws_sales_daily row count drop",
            "raw_alert": "dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。",
            "severity": "P2",
            "selected_diagnosis_skill": "data_volume_drop",
            "coverage_result": {"status": "covered"},
            "final_report": "Row count dropped from 10000 to 800.",
        },
        session_id="test-session",
    )

    assert response["status"] == "success"
    incident_id = response["result"]["incident_id"]

    with db_connection(database_url) as connection:
        incident = connection.execute(
            """
            SELECT incident_id, severity, selected_diagnosis_skill, final_report
            FROM incidents
            WHERE incident_id = ?
            """,
            (incident_id,),
        ).fetchone()
        log = connection.execute(
            """
            SELECT tool_name, status, incident_id
            FROM tool_call_logs
            WHERE tool_name = 'create_incident_report'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    assert incident["severity"] == "P2"
    assert incident["selected_diagnosis_skill"] == "data_volume_drop"
    assert log["status"] == "success"
    assert log["incident_id"] == incident_id


def test_tool_failure_is_returned_and_logged(
    provider: SQLiteDataOpsToolProvider,
    database_url: str,
) -> None:
    response = provider.query_lineage(
        table_name="dws_sales_daily",
        direction="sideways",
        session_id="test-session",
    )

    assert response["status"] == "failed"
    assert "direction must be one of" in response["error_message"]

    logs = _log_rows(database_url)
    assert logs[-1]["tool_name"] == "query_lineage"
    assert logs[-1]["status"] == "failed"
    assert "direction must be one of" in logs[-1]["error_message"]


def test_local_server_invoke_tool_uses_provider(database_url: str) -> None:
    response = invoke_tool(
        "query_data_volume",
        {
            "table_name": "dws_sales_daily",
            "start_date": "2026-05-14",
            "end_date": "2026-05-14",
        },
        database_url=database_url,
    )

    assert response["status"] == "success"
    assert response["result"]["volume_stats"][0]["change_ratio"] == -0.92

