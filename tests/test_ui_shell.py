from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_ui_shell_serves_same_origin_dashboard() -> None:
    client = TestClient(create_app())

    response = client.get("/ui")
    trailing_response = client.get("/ui/")
    static_response = client.get("/ui-static/shell.js")

    assert response.status_code == 200
    assert trailing_response.status_code == 200
    assert static_response.status_code == 200
    assert "Blackline Atlas" in response.text
    assert "/ui-static/shell.css" in response.text
    assert "/assets" in static_response.text
    assert "/replay/status" in static_response.text
    assert "/frames/current" in static_response.text
    assert "/frames/baseline" in static_response.text
    assert "/alerts" in static_response.text
    assert "/metrics" in static_response.text
    assert "/agent/query" in static_response.text
    assert "Command channel" in response.text
    assert "Theatre map" in response.text
    assert "Selected site" in response.text
