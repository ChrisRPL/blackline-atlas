from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.schemas.lead import Lead


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_region_conflict_question_focuses_live_gaza_marker(monkeypatch) -> None:
    client = _client_with_agent_plan(
        monkeypatch,
        {"tool": "search_live_leads", "area": "Gaza", "category": None},
    )

    response = client.post(
        "/agent/query",
        json={"query": "What is happening recently in Gaza? Focus the relevant reports."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "site_compare"
    assert payload["status"] == "ok"
    assert payload["resolved"]["area"] == "Gaza"
    assert payload["resolved"]["selected_lead_id"]
    assert payload["focus_asset_id"]
    assert payload["compare"] is not None
    assert payload["camera"]["mode"] == "focus_asset"


def test_nearest_conflict_question_uses_user_location_after_planner_selects_search(
    tmp_path: Path,
    monkeypatch,
) -> None:
    lead_registry_path = tmp_path / "live_leads.json"
    lead_registry_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "lead_far_gaza",
                    "title": "Conflict disruption reported in Gaza City",
                    "region": "Gaza City, Gaza",
                    "latitude": 31.5017,
                    "longitude": 34.4668,
                    "category_guess": "civilian_building_cluster",
                    "status": "lead_only",
                    "source_date": "2026-04-30",
                },
                {
                    "lead_id": "lead_near_lviv",
                    "title": "Air attack aftermath reported in Lviv region",
                    "region": "Lviv, Ukraine",
                    "latitude": 49.8397,
                    "longitude": 24.0297,
                    "category_guess": "civilian_building_cluster",
                    "status": "lead_only",
                    "source_date": "2026-04-30",
                },
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LEAD_REGISTRY_PATH", str(lead_registry_path))
    client = _client_with_agent_plan(
        monkeypatch,
        {"tool": "search_live_leads", "area": None, "category": None},
    )

    response = client.post(
        "/agent/query",
        json={
            "query": "Is there a conflict closest to my position?",
            "user_latitude": 52.2297,
            "user_longitude": 21.0122,
            "limit": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "search_live_leads"
    assert payload["status"] == "ok"
    assert payload["resolved"]["user_latitude"] == 52.2297
    assert payload["resolved"]["user_longitude"] == 21.0122
    assert [lead["lead_id"] for lead in payload["leads"]] == [
        "lead_near_lviv",
        "lead_far_gaza",
    ]
    assert payload["focus_lead_id"] == "lead_near_lviv"
    assert "nearest your location" in payload["summary"]


def test_selected_unlinked_marker_evidence_request_does_not_fall_back_to_fixture_site(
    monkeypatch,
) -> None:
    client = _client_with_agent_plan(monkeypatch, {"tool": "site_compare"})

    response = client.post(
        "/agent/query",
        json={
            "query": "Compare current and baseline imagery for the marker I clicked.",
            "selected_lead_id": "lead_qasmiyeh_bridge_202604",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "site_compare"
    assert payload["status"] == "no_result"
    assert payload["focus_lead_id"] == "lead_qasmiyeh_bridge_202604"
    assert payload["focus_asset_id"] is None
    assert payload["compare"] is None
    assert "satellite evidence is not available" in payload["summary"]


def test_named_site_evidence_request_loads_reference_image_pair(monkeypatch) -> None:
    client = _client_with_agent_plan(
        monkeypatch,
        {"tool": "site_compare", "site_id": "beirut_port_01"},
    )

    response = client.post(
        "/agent/query",
        json={"query": "Show current versus baseline evidence for Beirut Port."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "site_compare"
    assert payload["status"] == "ok"
    assert payload["focus_asset_id"] == "beirut_port_01"
    assert payload["compare"]["current_frame"]["frame"]["asset_id"] == "beirut_port_01"
    assert payload["compare"]["baseline_frame"]["frame"]["asset_id"] == "beirut_port_01"
    assert payload["analyst_report"] is None


def test_explain_selected_site_routes_to_evidence_summary(monkeypatch) -> None:
    client = _client_with_agent_plan(
        monkeypatch,
        {"tool": "explain_alert", "site_id": "okhmatdyt_01"},
    )

    response = client.post(
        "/agent/query",
        json={
            "query": "Why is this location flagged?",
            "selected_asset_id": "okhmatdyt_01",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "explain_alert"
    assert payload["status"] == "ok"
    assert payload["focus_asset_id"] == "okhmatdyt_01"
    assert payload["focus_alert_id"] == "blk_nd_00014"
    assert payload["compare"] is not None


def test_refresh_request_uses_live_refresh_tool_and_updates_markers(monkeypatch) -> None:
    refreshed = [
        Lead(
            lead_id="gdeltcloud_dnipro",
            title="Strike aftermath reported in Dnipro",
            region="Dnipro, Ukraine",
            latitude=48.4647,
            longitude=35.0462,
            category_guess="civilian_building_cluster",
            status="lead_only",
            source_url="https://example.test/dnipro",
        )
    ]

    def fake_refresh_lead_registry(**kwargs):
        assert kwargs["source_mode"] == "gdelt"
        assert kwargs["gdelt_limit"] == 500
        return refreshed, 1

    monkeypatch.setattr("app.services.stub.refresh_lead_registry", fake_refresh_lead_registry)
    client = _client_with_agent_plan(
        monkeypatch,
        {"tool": "refresh_live_leads", "area": "Ukraine"},
    )

    response = client.post(
        "/agent/query",
        json={"query": "Refresh the live conflict theater around Ukraine."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "refresh_live_leads"
    assert payload["status"] == "ok"
    assert payload["resolved"]["area"] == "Ukraine"
    assert payload["leads"][0]["lead_id"] == "gdeltcloud_dnipro"
    assert payload["focus_lead_id"] == "gdeltcloud_dnipro"


def test_capability_question_does_not_move_map(monkeypatch) -> None:
    client = _client_with_agent_plan(monkeypatch, {"tool": "answer"})

    response = client.post(
        "/agent/query",
        json={"query": "What can Atlas do in this dashboard?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "answer"
    assert payload["status"] == "ok"
    assert payload["camera"] is None
    assert payload["alerts"] == []
    assert payload["leads"] == []
    assert "refresh live conflict/disruption leads" in payload["summary"]


def test_tactical_attack_request_is_refused_before_planner(monkeypatch) -> None:
    client = _client_with_agent_plan(
        monkeypatch,
        {"tool": "search_live_leads", "area": "Kharkiv"},
    )

    response = client.post(
        "/agent/query",
        json={"query": "Where should I strike around Kharkiv?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "scope_refusal"
    assert payload["status"] == "no_result"
    assert payload["leads"] == []
    assert "I cannot help with targeting" in payload["summary"]


def test_selected_marker_watch_request_recovers_from_invalid_planner_output(monkeypatch) -> None:
    client = _client_with_agent_raw_text(monkeypatch, "not-json")

    response = client.post(
        "/agent/query",
        json={
            "query": "watch the site in instabul",
            "selected_lead_id": "lead_qasmiyeh_bridge_202604",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "site_compare"
    assert payload["status"] == "no_result"
    assert payload["focus_lead_id"] == "lead_qasmiyeh_bridge_202604"
    assert payload["planner"]["mode"] == "fallback"
    assert payload["planner"]["reason"] == "planner_invalid_json"
    assert "satellite evidence is not available" in payload["summary"]


def test_planner_disabled_still_routes_complex_region_prompt_to_live_search(
    tmp_path: Path,
    monkeypatch,
) -> None:
    lead_registry_path = tmp_path / "live_leads.json"
    lead_registry_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "lead_south_lebanon",
                    "title": "Cross-border strike aftermath reported near At-Taybah",
                    "region": "At-Taybah, Nabatieh, Lebanon, Middle East",
                    "latitude": 33.1067,
                    "longitude": 35.4408,
                    "category_guess": "civilian_building_cluster",
                    "status": "lead_only",
                    "source_date": "2026-04-30",
                },
                {
                    "lead_id": "lead_samar",
                    "title": "Philippine army clash reported in Samar",
                    "region": "Eastern Samar, Philippines, Southeast Asia",
                    "latitude": 11.7986,
                    "longitude": 125.0205,
                    "category_guess": "civilian_building_cluster",
                    "status": "lead_only",
                    "source_date": "2026-04-30",
                },
            ]
        ),
        encoding="utf-8",
    )
    get_settings.cache_clear()
    monkeypatch.setenv("LEAD_REGISTRY_PATH", str(lead_registry_path))
    monkeypatch.delenv("AGENT_HTTP_ENABLED", raising=False)
    client = TestClient(create_app())

    response = client.post(
        "/agent/query",
        json={
            "query": (
                "Can you pull up southern Lebanon first, then show the strongest "
                "civilian disruption reports?"
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "search_live_leads"
    assert payload["status"] == "ok"
    assert payload["resolved"]["area"] == "Lebanon"
    assert payload["focus_lead_id"] == "lead_south_lebanon"
    assert payload["planner"]["mode"] == "fallback"
    assert payload["planner"]["reason"] == "planner_not_configured"


def test_planner_disabled_extracts_unloaded_place_in_harder_regional_prompt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    lead_registry_path = tmp_path / "live_leads.json"
    lead_registry_path.write_text("[]", encoding="utf-8")
    get_settings.cache_clear()
    monkeypatch.setenv("LEAD_REGISTRY_PATH", str(lead_registry_path))
    monkeypatch.delenv("AGENT_HTTP_ENABLED", raising=False)
    client = TestClient(create_app())

    response = client.post(
        "/agent/query",
        json={"query": "What changed around Tehran or Iran this month? Show any source reports."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "search_live_leads"
    assert payload["status"] == "no_result"
    assert payload["resolved"]["area"] == "Tehran"
    assert "No live source leads matched near Tehran" in payload["summary"]
    assert payload["planner"]["mode"] == "fallback"


def _client_with_agent_plan(monkeypatch, plan: dict[str, object]) -> TestClient:
    get_settings.cache_clear()
    monkeypatch.setenv("AGENT_HTTP_ENABLED", "true")
    monkeypatch.setenv("AGENT_ENDPOINT", "https://planner.example/v1/plan")
    monkeypatch.setenv("AGENT_PROVIDER", "atlas_json_http")

    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        return _FakeHTTPResponse(body=json.dumps({"output_text": json.dumps(plan)}).encode("utf-8"))

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    return TestClient(create_app())


def _client_with_agent_raw_text(monkeypatch, raw_text: str) -> TestClient:
    get_settings.cache_clear()
    monkeypatch.setenv("AGENT_HTTP_ENABLED", "true")
    monkeypatch.setenv("AGENT_ENDPOINT", "https://planner.example/v1/plan")
    monkeypatch.setenv("AGENT_PROVIDER", "atlas_json_http")

    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        return _FakeHTTPResponse(body=json.dumps({"output_text": raw_text}).encode("utf-8"))

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    return TestClient(create_app())


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
