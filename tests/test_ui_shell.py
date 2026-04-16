from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_ui_shell_serves_same_origin_dashboard() -> None:
    client = TestClient(create_app())

    response = client.get("/ui")
    trailing_response = client.get("/ui/")

    assert response.status_code == 200
    assert trailing_response.status_code == 200
    assert "Blackline Atlas" in response.text
    assert "/health.config" in response.text
    assert "/replay/status" in response.text
    assert "/frames/current" in response.text
    assert "/frames/baseline" in response.text
    assert "/alerts" in response.text
    assert "/metrics" in response.text
    assert "Replay identity" in response.text
    assert "Decision" in response.text
    assert "Current frame snapshot" in response.text
    assert "Baseline frame snapshot" in response.text
    assert "Latest alert" in response.text
