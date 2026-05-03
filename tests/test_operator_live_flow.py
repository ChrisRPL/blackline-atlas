from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_operator_chat_to_live_lead_to_evidence_without_fixture_fallback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    lead_registry = tmp_path / "live_leads.json"
    lead_registry.write_text(
        json.dumps(
            [
                {
                    "lead_id": "gdeltcloud_iran_bushehr",
                    "title": "Strike reported near Bushehr civilian infrastructure",
                    "region": "Bushehr, Iran",
                    "latitude": 28.9234,
                    "longitude": 50.8203,
                    "category_guess": "civilian_building_cluster",
                    "status": "lead_only",
                    "summary": "Live source lead for operator triage.",
                    "source_url": "https://example.test/bushehr",
                    "source_date": "2026-04-30",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LEAD_REGISTRY_PATH", str(lead_registry))
    monkeypatch.setenv("AGENT_HTTP_ENABLED", "true")
    monkeypatch.setenv("AGENT_ENDPOINT", "https://planner.example/v1/plan")
    monkeypatch.setenv("AGENT_PROVIDER", "atlas_json_http")

    def fake_urlopen(request, timeout: float):
        _ = timeout
        body = json.loads(request.data.decode("utf-8"))
        user_text = next(item["text"] for item in body["inputs"] if item["role"] == "user")
        if "compare current and baseline evidence" in user_text:
            plan = {"tool": "site_compare"}
        else:
            plan = {"tool": "search_live_leads", "area": "Iran"}
        return _FakeHTTPResponse(body=json.dumps({"output_text": json.dumps(plan)}).encode("utf-8"))

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    get_settings.cache_clear()
    client = TestClient(create_app())

    lead_response = client.post(
        "/agent/query",
        json={"query": "what happened recently in Iran?"},
    )
    lead_payload = lead_response.json()

    assert lead_response.status_code == 200
    assert lead_payload["tool"] == "search_live_leads"
    assert lead_payload["status"] == "ok"
    assert lead_payload["focus_lead_id"] == "gdeltcloud_iran_bushehr"
    assert lead_payload["focus_asset_id"] is None
    assert lead_payload["alerts"] == []
    assert lead_payload["leads"][0]["region"] == "Bushehr, Iran"
    assert lead_payload["camera"]["mode"] == "focus_lead"

    compare_response = client.post(
        "/agent/query",
        json={
            "query": "compare current and baseline evidence",
            "selected_lead_id": lead_payload["focus_lead_id"],
        },
    )
    compare_payload = compare_response.json()

    assert compare_response.status_code == 200
    assert compare_payload["tool"] == "site_compare"
    assert compare_payload["status"] == "no_result"
    assert compare_payload["focus_asset_id"] is None
    assert compare_payload["focus_lead_id"] == "gdeltcloud_iran_bushehr"
    assert compare_payload["alerts"] == []
    assert compare_payload["compare"] is None
    assert "satellite evidence is not available" in compare_payload["summary"]


class _FakeHTTPResponse:
    status = 200

    def __init__(self, *, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = exc_type
        _ = exc
        _ = tb

    def read(self) -> bytes:
        return self._body
