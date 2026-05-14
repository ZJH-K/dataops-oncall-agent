from fastapi.testclient import TestClient

from app.main import app


def test_demo_ui_root_serves_workbench() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "DataOps OnCall Agent" in response.text
    assert 'id="diagnose-button"' in response.text
    assert 'id="demo-alerts"' in response.text
    assert 'id="tool-timeline"' in response.text
    assert 'id="chat-input"' in response.text


def test_demo_ui_static_assets_are_served() -> None:
    client = TestClient(app)

    script_response = client.get("/static/app.js")
    style_response = client.get("/static/styles.css")

    assert script_response.status_code == 200
    assert style_response.status_code == 200
    assert "/api/diagnose" in script_response.text
    assert "/api/chat" in script_response.text
    assert "data_volume_drop" in script_response.text
    assert "null_rate_spike" in script_response.text
    assert ".pipeline-step" in style_response.text
