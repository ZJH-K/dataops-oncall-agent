from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.db.connection import db_connection
from app.db.demo_seed import seed_demo_data
from app.main import app
from app.rag.indexer import build_rag_index


@pytest.fixture()
def client(tmp_path: Path) -> Iterator[TestClient]:
    database_url = f"sqlite:///{tmp_path / 'demo.db'}"
    with db_connection(database_url) as connection:
        seed_demo_data(connection)

    index_path = tmp_path / "rag_index.json"
    build_rag_index(index_path=index_path)

    old_database_url = app.state.database_url
    old_index_path = app.state.rag_index_path
    app.state.database_url = database_url
    app.state.rag_index_path = index_path
    try:
        yield TestClient(app)
    finally:
        app.state.database_url = old_database_url
        app.state.rag_index_path = old_index_path


def test_health_returns_wrapped_runtime_status(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["status"] == "ok"
    assert payload["data"]["database"] == "ok"
    assert payload["data"]["rag_index"] == "ok"
    assert payload["data"]["skills_loaded"] == 4


def test_diagnose_data_volume_drop_and_query_incident(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/diagnose",
        json={
            "session_id": "api-diagnose-session",
            "alert": "dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。",
            "options": {"debug": True},
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "completed"
    assert data["selected_diagnosis_skill"]["name"] == "data_volume_drop"
    assert data["incident_id"]
    assert data["coverage_result"]["status"] == "complete"
    assert "10000 -> 800" in data["final_report"]

    incident_response = client.get(f"/api/incidents/{data['incident_id']}")
    assert incident_response.status_code == 200
    incident = incident_response.json()["data"]
    assert incident["selected_diagnosis_skill"] == "data_volume_drop"
    assert incident["alert_context"]["table_name"] == "dws_sales_daily"

    tool_response = client.get(f"/api/incidents/{data['incident_id']}/tool-calls")
    assert tool_response.status_code == 200
    tool_names = {
        call["tool_name"]
        for call in tool_response.json()["data"]["tool_calls"]
    }
    assert "query_data_volume" in tool_names
    assert "query_lineage" in tool_names


def test_diagnose_returns_clarification_response(client: TestClient) -> None:
    response = client.post(
        "/api/diagnose",
        json={
            "session_id": "api-clarify-session",
            "alert": "今天的数据好像有点问题，帮我看一下。",
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == 422
    assert payload["data"]["status"] == "needs_clarification"
    assert payload["data"]["clarification_question"]


def test_skills_and_skill_match_api(client: TestClient) -> None:
    skills_response = client.get("/api/skills")
    assert skills_response.status_code == 200
    skills = skills_response.json()["data"]["skills"]
    assert {skill["name"] for skill in skills} >= {"data_volume_drop", "null_rate_spike"}

    detail_response = client.get("/api/skills/data_volume_drop")
    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert detail["name"] == "data_volume_drop"
    assert "query_data_volume" in detail["required_tools"]
    assert detail["runbook_preview"]

    match_response = client.post(
        "/api/skills/match",
        json={"alert": "dws_sales_daily 今日数据量较昨日下降 92%。"},
    )
    assert match_response.status_code == 200
    selected = match_response.json()["data"]["selected_diagnosis_skill"]
    assert selected["name"] == "data_volume_drop"


def test_chat_uses_session_state_after_diagnosis(client: TestClient) -> None:
    diagnose_response = client.post(
        "/api/diagnose",
        json={
            "session_id": "api-chat-session",
            "alert": "dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。",
        },
    )
    assert diagnose_response.status_code == 200

    chat_response = client.post(
        "/api/chat",
        json={"session_id": "api-chat-session", "message": "它影响哪些下游报表？"},
    )

    assert chat_response.status_code == 200
    data = chat_response.json()["data"]
    assert data["used_state"]["current_table"] == "dws_sales_daily"
    assert "ads_sales_report" in data["answer"]
    assert any(ref["type"] == "tool_call" for ref in data["references"])


def test_chat_uses_deepseek_for_generic_follow_up(
    client: TestClient,
    monkeypatch,
) -> None:
    import app.api.services as services

    monkeypatch.setattr(
        services,
        "settings",
        SimpleNamespace(
            llm_provider="deepseek",
            deepseek_api_key="fake-key",
            deepseek_model="deepseek-v4-flash",
        ),
    )

    class FakeDeepSeekClient:
        @classmethod
        def from_settings(cls):
            return cls()

        def complete(self, messages, max_tokens=700, temperature=0.2):
            assert "session_context_json" in messages[-1]["content"]
            assert "你是什么模型" in messages[-1]["content"]
            return "我是 DataOps OnCall Agent 的对话层，当前配置使用 DeepSeek 文本模型辅助回答。"

    monkeypatch.setattr(services, "DeepSeekChatClient", FakeDeepSeekClient)

    diagnose_response = client.post(
        "/api/diagnose",
        json={
            "session_id": "api-chat-llm-session",
            "alert": "dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。",
        },
    )
    assert diagnose_response.status_code == 200

    chat_response = client.post(
        "/api/chat",
        json={"session_id": "api-chat-llm-session", "message": "你是什么模型"},
    )

    assert chat_response.status_code == 200
    data = chat_response.json()["data"]
    assert "DeepSeek 文本模型" in data["answer"]
    assert any(ref["type"] == "llm" for ref in data["references"])


def test_chat_current_status_uses_evidence_summary(client: TestClient) -> None:
    diagnose_response = client.post(
        "/api/diagnose",
        json={
            "session_id": "api-chat-status-session",
            "alert": "dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。",
        },
    )
    assert diagnose_response.status_code == 200

    chat_response = client.post(
        "/api/chat",
        json={"session_id": "api-chat-status-session", "message": "现在出现了什么情况"},
    )

    assert chat_response.status_code == 200
    data = chat_response.json()["data"]
    assert "dws_sales_daily" in data["answer"]
    assert "10000" in data["answer"]
    assert "800" in data["answer"]
    assert any(ref["type"] == "coverage" for ref in data["references"])


def test_incidents_list_can_filter_by_skill(client: TestClient) -> None:
    diagnose_response = client.post(
        "/api/diagnose",
        json={
            "session_id": "api-list-session",
            "alert": "dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。",
        },
    )
    assert diagnose_response.status_code == 200

    response = client.get("/api/incidents?skill_name=data_volume_drop")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] >= 1
    assert data["items"][0]["selected_diagnosis_skill"] == "data_volume_drop"
