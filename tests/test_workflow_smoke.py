from pathlib import Path
from types import SimpleNamespace

import pytest

from app.db.connection import db_connection
from app.db.demo_seed import seed_demo_data
from app.rag.indexer import build_rag_index
from app.workflow.nodes import reporter
from app.workflow.graph import run_diagnosis


MVP_SCENARIOS = [
    {
        "case_id": "airflow_task_failed",
        "alert": "DAG dwd_order_detail_daily 今天凌晨运行失败，请帮我诊断原因。",
        "expected_skill": "airflow_task_failed",
        "required_tools": {"query_task_runs", "query_lineage"},
        "expected_source": "docs/runbooks/airflow_task_failed.md",
        "report_keywords": ["dwd_order_detail_daily", "SQL column not found"],
    },
    {
        "case_id": "partition_missing",
        "alert": "dws_sales_daily 今天没有生成 dt=2026-05-14 分区，请帮我排查。",
        "expected_skill": "partition_missing",
        "required_tools": {
            "query_table_partitions",
            "query_task_runs",
            "query_lineage",
        },
        "expected_source": "docs/runbooks/partition_missing.md",
        "report_keywords": ["dws_sales_daily", "query_table_partitions"],
    },
    {
        "case_id": "data_volume_drop",
        "alert": "dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。",
        "expected_skill": "data_volume_drop",
        "required_tools": {
            "query_data_volume",
            "query_task_runs",
            "query_table_partitions",
            "query_lineage",
        },
        "expected_source": "docs/runbooks/data_volume_drop.md",
        "report_keywords": ["10000 -> 800", "ads_sales_report"],
    },
    {
        "case_id": "null_rate_spike",
        "alert": "ads_user_profile 表中 user_id 字段空值率突然升高，请分析影响范围。",
        "expected_skill": "null_rate_spike",
        "required_tools": {"query_null_rate", "query_task_runs", "query_lineage"},
        "expected_source": "docs/runbooks/null_rate_spike.md",
        "report_keywords": ["ads_user_profile", "0.35"],
    },
]


@pytest.fixture()
def workflow_env(tmp_path: Path) -> tuple[str, Path]:
    database_url = f"sqlite:///{tmp_path / 'demo.db'}"
    with db_connection(database_url) as connection:
        seed_demo_data(connection)
    index_path = tmp_path / "rag_index.json"
    build_rag_index(index_path=index_path)
    return database_url, index_path


def test_data_volume_drop_workflow_smoke(workflow_env: tuple[str, Path]) -> None:
    database_url, index_path = workflow_env

    state = run_diagnosis(
        "dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。",
        session_id="workflow-smoke-session",
        database_url=database_url,
        index_path=index_path,
    )

    assert state["selected_diagnosis_skill"]["name"] == "data_volume_drop"
    assert state["retrieved_docs"]
    assert any(
        doc["source_file"] == "docs/runbooks/data_volume_drop.md"
        for doc in state["retrieved_docs"]
    )
    assert {
        "query_data_volume",
        "query_task_runs",
        "query_table_partitions",
        "query_lineage",
    }.issubset({call["tool_name"] for call in state["tool_calls"]})
    assert state["coverage_result"]["status"] == "complete"
    assert state["coverage_result"]["coverage_ratio"] == 1.0
    assert state["incident_id"]
    assert "10000 -> 800" in state["final_report"]
    assert "docs/runbooks/data_volume_drop.md" in state["final_report"]

    with db_connection(database_url) as connection:
        incident = connection.execute(
            """
            SELECT incident_id, status, selected_diagnosis_skill, final_report
            FROM incidents
            WHERE incident_id = ?
            """,
            (state["incident_id"],),
        ).fetchone()
        session = connection.execute(
            """
            SELECT current_incident_id, current_table, selected_diagnosis_skill, state_json
            FROM sessions
            WHERE session_id = ?
            """,
            ("workflow-smoke-session",),
        ).fetchone()

    assert incident["status"] == "completed"
    assert incident["selected_diagnosis_skill"] == "data_volume_drop"
    assert "CoverageChecker" in incident["final_report"]
    assert session["current_incident_id"] == state["incident_id"]
    assert session["current_table"] == "dws_sales_daily"
    assert session["selected_diagnosis_skill"] == "data_volume_drop"
    assert "tool_calls" in session["state_json"]


@pytest.mark.parametrize("scenario", MVP_SCENARIOS, ids=[case["case_id"] for case in MVP_SCENARIOS])
def test_all_mvp_scenarios_run_end_to_end(
    workflow_env: tuple[str, Path],
    scenario: dict[str, object],
) -> None:
    database_url, index_path = workflow_env

    state = run_diagnosis(
        str(scenario["alert"]),
        session_id=f"workflow-{scenario['case_id']}",
        database_url=database_url,
        index_path=index_path,
    )

    assert state["selected_diagnosis_skill"]["name"] == scenario["expected_skill"]
    assert any(
        doc["source_file"] == scenario["expected_source"]
        for doc in state["retrieved_docs"]
    )

    successful_tools = {
        call["tool_name"]
        for call in state["tool_calls"]
        if call["status"] == "success"
    }
    assert set(scenario["required_tools"]).issubset(successful_tools)
    assert state["coverage_result"]["status"] == "complete"
    assert state["coverage_result"]["coverage_ratio"] == 1.0
    assert state["incident_id"]

    _assert_report_references_evidence(
        state["final_report"],
        expected_source=str(scenario["expected_source"]),
        required_tools=set(scenario["required_tools"]),
    )
    for keyword in scenario["report_keywords"]:
        assert str(keyword) in state["final_report"]


def test_workflow_needs_clarification_path(workflow_env: tuple[str, Path]) -> None:
    database_url, index_path = workflow_env

    state = run_diagnosis(
        "今天的数据好像有点问题，帮我看一下。",
        session_id="workflow-clarify-session",
        database_url=database_url,
        index_path=index_path,
    )

    assert state["needs_clarification"]
    assert state["clarification_question"]
    assert "当前告警信息不足" in state["final_report"]
    assert state["incident_id"]


def test_workflow_marks_missing_evidence_as_limited(
    workflow_env: tuple[str, Path],
) -> None:
    database_url, index_path = workflow_env

    state = run_diagnosis(
        "dws_unknown_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。",
        session_id="workflow-limited-session",
        database_url=database_url,
        index_path=index_path,
    )

    assert state["selected_diagnosis_skill"]["name"] == "data_volume_drop"
    assert state["coverage_result"]["status"] == "partial"
    assert state["coverage_result"]["missing_evidence"]
    assert "不能过度确定根因" in state["confidence_limit"]
    assert "证据缺失" in state["final_report"] or "证据不足" in state["final_report"]


def test_reporter_can_append_deepseek_summary(monkeypatch) -> None:
    monkeypatch.setattr(
        reporter,
        "settings",
        SimpleNamespace(llm_provider="deepseek", deepseek_api_key="fake-key"),
    )

    class FakeDeepSeekClient:
        @classmethod
        def from_settings(cls):
            return cls()

        def complete(self, messages, max_tokens=600, temperature=0.2):
            return "- DeepSeek 摘要"

    monkeypatch.setattr(reporter, "DeepSeekChatClient", FakeDeepSeekClient)

    result = reporter.reporter_node(
        {
            "raw_alert": "dws_sales_daily 今日数据量较昨日下降 92%",
            "alert_context": {"table_name": "dws_sales_daily", "biz_date": "2026-05-14"},
            "selected_diagnosis_skill": {
                "name": "data_volume_drop",
                "confidence": 0.99,
                "reason": "数据量下降",
                "required_tools": ["query_data_volume"],
            },
            "plan": [],
            "retrieved_docs": [],
            "tool_calls": [],
            "coverage_result": {"status": "partial"},
            "evidence": {},
        }
    )

    assert "## 10. DeepSeek 辅助摘要" in result["final_report"]
    assert "- DeepSeek 摘要" in result["final_report"]


def _assert_report_references_evidence(
    final_report: str,
    expected_source: str,
    required_tools: set[str],
) -> None:
    assert "## 4. RAG 引用来源" in final_report
    assert "## 5. 工具调用证据" in final_report
    assert "## 6. CoverageChecker" in final_report
    assert "## 9. 证据不足说明" in final_report
    assert expected_source in final_report
    for tool_name in required_tools:
        assert tool_name in final_report
