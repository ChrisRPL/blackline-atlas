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
