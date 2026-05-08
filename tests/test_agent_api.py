from __future__ import annotations

import json

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


def test_agent_tools_contract() -> None:
    client = TestClient(create_app())

    response = client.get("/agent/tools")

    assert response.status_code == 200
    payload = response.json()
    assert [item["name"] for item in payload] == [
        "answer",
        "scope_refusal",
        "search_live_leads",
        "latest_alerts",
        "biggest_disruptions",
        "site_compare",
        "explain_alert",
        "refresh_live_leads",
    ]


def test_agent_query_answers_capability_questions_without_map_action(monkeypatch) -> None:
    client = _client_with_agent_plan(monkeypatch, {"tool": "answer"})

    response = client.post("/agent/query", json={"query": "what can you do?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "answer"
    assert payload["status"] == "ok"
    assert payload["alerts"] == []
    assert payload["leads"] == []
    assert "refresh live conflict/disruption leads" in payload["summary"]


def test_agent_query_refuses_tactical_requests() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/agent/query",
        json={"query": "give me the best target list and strike plan near Kharkiv"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "scope_refusal"
    assert payload["status"] == "no_result"
    assert payload["alerts"] == []
    assert payload["leads"] == []
    assert "I cannot help with targeting" in payload["summary"]


def test_agent_query_latest_alerts_uses_planner_tool(monkeypatch) -> None:
    client = _client_with_agent_plan(monkeypatch, {"tool": "search_live_leads"})

    response = client.post("/agent/query", json={"query": "show latest alerts"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "search_live_leads"
    assert payload["status"] == "ok"
    assert payload["focus_asset_id"] is None
    assert payload["focus_lead_id"]
    assert payload["alerts"] == []
    assert payload["leads"]
    assert payload["resolved"]["tool"] == "search_live_leads"
    assert payload["planner"]["mode"] == "live"
    assert payload["trust"]["mode"] == "degraded"
    assert payload["camera"]["mode"] == "focus_lead"


def test_agent_query_biggest_disruptions_prioritizes_high_severity() -> None:
    client = TestClient(create_app())

    response = client.post("/agent/query", json={"tool": "biggest_disruptions"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "biggest_disruptions"
    assert payload["planner"]["mode"] == "deterministic"
    assert payload["planner"]["reason"] == "explicit_tool"
    assert payload["focus_asset_id"] == "demo_port_01"
    assert payload["alerts"][0]["severity"] == "high"
    assert payload["compare"]["asset_id"] == "demo_port_01"


def test_agent_query_site_compare_returns_selected_site_frames() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/agent/query",
        json={"tool": "site_compare", "site_id": "demo_bridge_01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "site_compare"
    assert payload["planner"]["mode"] == "deterministic"
    assert payload["planner"]["reason"] == "explicit_tool"
    assert payload["focus_asset_id"] == "demo_bridge_01"
    assert payload["compare"]["current_frame"]["frame"]["asset_id"] == "demo_bridge_01"
    assert payload["compare"]["baseline_frame"]["frame"]["asset_id"] == "demo_bridge_01"
    assert payload["resolved"]["site_id"] == "demo_bridge_01"
    assert payload["resolved"]["tool"] == "site_compare"
    assert payload["camera"]["mode"] == "focus_asset"
    assert payload["camera"]["asset_id"] == "demo_bridge_01"
    assert payload["analyst_report"] is None


def test_agent_query_site_compare_requires_selected_live_context() -> None:
    client = TestClient(create_app())

    response = client.post("/agent/query", json={"tool": "site_compare"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "site_compare"
    assert payload["status"] == "no_result"
    assert payload["focus_asset_id"] is None
    assert payload["compare"] is None
    assert "Select a live source marker" in payload["summary"]


def test_agent_query_site_compare_does_not_fallback_for_missing_selected_lead() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/agent/query",
        json={
            "tool": "site_compare",
            "selected_lead_id": "missing_live_lead",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "site_compare"
    assert payload["status"] == "no_result"
    assert payload["focus_asset_id"] is None
    assert payload["compare"] is None
    assert "no longer in the live registry" in payload["summary"]


def test_asset_analyst_report_endpoint_withholds_report_for_missing_image_files() -> None:
    client = TestClient(create_app())

    response = client.get("/analyst/assets/demo_port_01")

    assert response.status_code == 200
    assert response.json() is None


def test_agent_query_site_compare_returns_reference_event_evidence() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/agent/query",
        json={"tool": "site_compare", "site_id": "beirut_port_01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "site_compare"
    assert payload["status"] == "ok"
    assert payload["focus_asset_id"] == "beirut_port_01"
    assert payload["focus_alert_id"] == "blk_nd_00001"
    assert payload["compare"]["asset_id"] == "beirut_port_01"
    assert payload["compare"]["current_frame"]["accepted_for_alerting"] is True
    assert "reference event evidence" in payload["summary"]


def test_agent_query_site_compare_returns_reference_event_evidence_for_medical_aid_site() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/agent/query",
        json={"tool": "site_compare", "site_id": "okhmatdyt_01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "site_compare"
    assert payload["status"] == "ok"
    assert payload["focus_asset_id"] == "okhmatdyt_01"
    assert payload["focus_alert_id"] == "blk_nd_00014"
    assert payload["compare"]["asset_id"] == "okhmatdyt_01"
    assert payload["compare"]["current_frame"]["accepted_for_alerting"] is True


def test_agent_query_site_compare_returns_reference_event_evidence_for_roshen_food_site() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/agent/query",
        json={"tool": "site_compare", "site_id": "roshen_yahotyn_01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "site_compare"
    assert payload["status"] == "ok"
    assert payload["focus_asset_id"] == "roshen_yahotyn_01"
    assert payload["focus_alert_id"] == "blk_nd_00015"
    assert payload["compare"]["asset_id"] == "roshen_yahotyn_01"
    assert payload["compare"]["current_frame"]["accepted_for_alerting"] is True


def test_agent_query_site_compare_returns_reference_control_evidence() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/agent/query",
        json={"tool": "site_compare", "site_id": "ras_abu_jarjur_01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "site_compare"
    assert payload["status"] == "ok"
    assert payload["focus_asset_id"] == "ras_abu_jarjur_01"
    assert payload["focus_alert_id"] is None
    assert payload["alerts"] == []
    assert payload["compare"]["asset_id"] == "ras_abu_jarjur_01"
    assert payload["compare"]["current_frame"]["accepted_for_alerting"] is False
    assert "No material change" in payload["summary"]


def test_agent_query_site_compare_returns_reference_control_evidence_for_trostianets() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/agent/query",
        json={"tool": "site_compare", "site_id": "trostianets_hospital_01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "site_compare"
    assert payload["status"] == "ok"
    assert payload["focus_asset_id"] == "trostianets_hospital_01"
    assert payload["focus_alert_id"] is None
    assert payload["alerts"] == []
    assert payload["compare"]["asset_id"] == "trostianets_hospital_01"
    assert payload["compare"]["current_frame"]["accepted_for_alerting"] is False


def test_agent_query_site_compare_returns_reference_control_evidence_for_kramatorsk() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/agent/query",
        json={"tool": "site_compare", "site_id": "kramatorsk_filtration_01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "site_compare"
    assert payload["status"] == "ok"
    assert payload["focus_asset_id"] == "kramatorsk_filtration_01"
    assert payload["focus_alert_id"] is None
    assert payload["alerts"] == []
    assert payload["compare"]["asset_id"] == "kramatorsk_filtration_01"
    assert payload["compare"]["current_frame"]["accepted_for_alerting"] is False


def test_agent_query_site_compare_returns_reference_event_evidence_for_kakhovka() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/agent/query",
        json={"tool": "site_compare", "site_id": "kakhovka_dam_01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "site_compare"
    assert payload["status"] == "ok"
    assert payload["focus_asset_id"] == "kakhovka_dam_01"
    assert payload["focus_alert_id"] == "blk_nd_00018"
    assert payload["compare"]["asset_id"] == "kakhovka_dam_01"
    assert payload["compare"]["current_frame"]["accepted_for_alerting"] is True


def test_agent_query_site_compare_returns_reference_event_evidence_for_mansour() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/agent/query",
        json={"tool": "site_compare", "site_id": "mansour_dam_01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "site_compare"
    assert payload["status"] == "ok"
    assert payload["focus_asset_id"] == "mansour_dam_01"
    assert payload["focus_alert_id"] == "blk_nd_00020"
    assert payload["compare"]["asset_id"] == "mansour_dam_01"
    assert payload["compare"]["current_frame"]["accepted_for_alerting"] is True


def test_agent_query_site_compare_returns_reference_event_evidence_for_mondelez() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/agent/query",
        json={"tool": "site_compare", "site_id": "mondelez_trostianets_01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "site_compare"
    assert payload["status"] == "ok"
    assert payload["focus_asset_id"] == "mondelez_trostianets_01"
    assert payload["focus_alert_id"] == "blk_nd_00021"
    assert payload["compare"]["asset_id"] == "mondelez_trostianets_01"
    assert payload["compare"]["current_frame"]["accepted_for_alerting"] is True


def test_agent_query_site_compare_returns_reference_event_evidence_for_morandi() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/agent/query",
        json={"tool": "site_compare", "site_id": "morandi_bridge_01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "site_compare"
    assert payload["status"] == "ok"
    assert payload["focus_asset_id"] == "morandi_bridge_01"
    assert payload["focus_alert_id"] == "blk_nd_00022"
    assert payload["compare"]["asset_id"] == "morandi_bridge_01"
    assert payload["compare"]["current_frame"]["accepted_for_alerting"] is True


def test_agent_query_explain_alert_uses_selected_asset_context(monkeypatch) -> None:
    client = _client_with_agent_plan(
        monkeypatch,
        {"tool": "explain_alert", "site_id": "demo_port_01"},
    )

    response = client.post(
        "/agent/query",
        json={"query": "why is this high confidence", "selected_asset_id": "demo_port_01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "explain_alert"
    assert payload["planner"]["mode"] == "live"
    assert payload["focus_asset_id"] == "demo_port_01"
    assert payload["focus_alert_id"] == "blk_00017"
    assert "Large terminal footprint change" in payload["summary"]
    assert payload["resolved"]["site_id"] == "demo_port_01"
    assert payload["resolved"]["selected_asset_id"] == "demo_port_01"
    assert payload["resolved"]["selected_lead_id"] is None


def test_agent_query_latest_alerts_can_focus_selected_lead_marker(monkeypatch) -> None:
    client = _client_with_agent_plan(
        monkeypatch,
        {"tool": "search_live_leads", "area": "South Lebanon"},
    )

    response = client.post(
        "/agent/query",
        json={
            "query": "show latest alerts here",
            "selected_lead_id": "lead_qasmiyeh_bridge_202604",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "search_live_leads"
    assert payload["status"] == "ok"
    assert payload["focus_asset_id"] is None
    assert payload["focus_lead_id"] == "lead_qasmiyeh_bridge_202604"
    assert payload["camera"]["mode"] == "focus_lead"
    assert payload["camera"]["lead_id"] == "lead_qasmiyeh_bridge_202604"
    assert payload["leads"][0]["lead_id"] == "lead_qasmiyeh_bridge_202604"
    assert "live source" in payload["summary"]
    assert payload["resolved"]["selected_lead_id"] == "lead_qasmiyeh_bridge_202604"


def test_agent_query_explain_alert_returns_lead_only_context(monkeypatch) -> None:
    client = _client_with_agent_plan(
        monkeypatch,
        {"tool": "search_live_leads", "area": "South Lebanon"},
    )

    response = client.post(
        "/agent/query",
        json={
            "query": "why is this point flagged",
            "selected_lead_id": "lead_qasmiyeh_bridge_202604",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "search_live_leads"
    assert payload["status"] == "ok"
    assert payload["focus_asset_id"] is None
    assert payload["focus_lead_id"] == "lead_qasmiyeh_bridge_202604"
    assert "not confirmed satellite alerts" in payload["summary"]
    assert payload["camera"]["mode"] == "focus_lead"


def test_agent_query_explain_alert_returns_no_result_for_reference_control_site(
    monkeypatch,
) -> None:
    client = _client_with_agent_plan(
        monkeypatch,
        {"tool": "explain_alert", "site_id": "ras_abu_jarjur_01"},
    )

    response = client.post(
        "/agent/query",
        json={"query": "why is this flagged", "selected_asset_id": "ras_abu_jarjur_01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "explain_alert"
    assert payload["status"] == "no_result"
    assert payload["focus_asset_id"] is None
    assert "No confirmed satellite alert" in payload["summary"]


def test_agent_query_latest_alerts_can_return_no_result_for_real_watchlist_area(
    monkeypatch,
) -> None:
    client = _client_with_agent_plan(
        monkeypatch,
        {"tool": "search_live_leads", "area": "Bahrain"},
    )

    response = client.post("/agent/query", json={"query": "show latest alerts near Bahrain"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "search_live_leads"
    assert payload["status"] == "no_result"
    assert payload["focus_asset_id"] is None
    assert payload["alerts"] == []
    assert payload["resolved"]["area"] == "Bahrain"
    assert payload["camera"]["mode"] == "watchlist"
    assert payload["camera"]["highlight_lead_ids"] == []


def test_agent_query_refresh_live_leads_updates_markers(monkeypatch) -> None:
    leads = [
        Lead(
            lead_id="gdeltcloud_ukraine_kramatorsk",
            title="Shelling reported near Kramatorsk",
            region="Kramatorsk, Donetsk, Ukraine",
            latitude=48.738,
            longitude=37.584,
            category_guess="water_infrastructure",
            status="lead_only",
            summary="Live conflict source reports damage near civilian infrastructure.",
            source_url="https://example.test/kramatorsk",
        ),
        Lead(
            lead_id="gdeltcloud_gaza_city",
            title="Strike aftermath reported in Gaza City",
            region="Gaza City, Gaza",
            latitude=31.501,
            longitude=34.466,
            category_guess="aid_shelter_campus",
            status="lead_only",
            summary="Live conflict source reports civilian disruption.",
            source_url="https://example.test/gaza",
        ),
    ]

    def fake_refresh_lead_registry(**kwargs):
        assert kwargs["source_mode"] == "gdelt"
        assert kwargs["gdelt_hours"] == 72
        assert kwargs["gdelt_limit"] == 500
        return leads, 2

    monkeypatch.setattr("app.services.stub.refresh_lead_registry", fake_refresh_lead_registry)
    client = _client_with_agent_plan(
        monkeypatch,
        {"tool": "refresh_live_leads", "area": "Ukraine"},
    )

    response = client.post(
        "/agent/query",
        json={"query": "refresh live conflicts near Ukraine"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "refresh_live_leads"
    assert payload["status"] == "ok"
    assert payload["resolved"]["area"] == "Ukraine"
    assert payload["leads"][0]["lead_id"] == "gdeltcloud_ukraine_kramatorsk"
    assert len(payload["leads"]) == 2
    assert payload["focus_lead_id"] == "gdeltcloud_ukraine_kramatorsk"
    assert payload["camera"]["mode"] == "focus_lead"
    assert "2 markers loaded" in payload["summary"]


def test_agent_query_region_question_searches_live_leads(monkeypatch) -> None:
    client = _client_with_agent_plan(
        monkeypatch,
        {"tool": "search_live_leads", "area": "Lebanon"},
    )

    response = client.post(
        "/agent/query",
        json={"query": "what happened recently in Lebanon?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "search_live_leads"
    assert payload["status"] == "ok"
    assert payload["leads"]
    assert payload["focus_asset_id"] is None
    assert "live source" in payload["summary"]
    assert payload["observations"][0]["tool"] == "search_live_leads"


def test_agent_query_center_command_extracts_country_not_command_verb(monkeypatch) -> None:
    client = _client_with_agent_plan(
        monkeypatch,
        {"tool": "search_live_leads", "area": "Lebanon"},
    )

    response = client.post(
        "/agent/query",
        json={
            "query": (
                "Center on Lebanon and summarize recent civilian infrastructure "
                "disruption reports."
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "search_live_leads"
    assert payload["resolved"]["area"] == "Lebanon"
    assert payload["resolved"]["category"] is None
    assert payload["leads"]
    assert "Center" not in payload["summary"]


def test_agent_query_red_sea_region_extracts_full_geographic_phrase(monkeypatch) -> None:
    client = _client_with_agent_plan(
        monkeypatch,
        {"tool": "search_live_leads", "area": "Red Sea"},
    )

    response = client.post(
        "/agent/query",
        json={"query": "Which active conflict regions near the Red Sea should I inspect first?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "search_live_leads"
    assert payload["resolved"]["area"] == "Red Sea"
    assert payload["resolved"]["category"] is None
    assert payload["leads"] == []
    assert "Red Sea" in payload["summary"]


def test_agent_query_unknown_region_does_not_return_unfiltered_leads(monkeypatch) -> None:
    client = _client_with_agent_plan(
        monkeypatch,
        {"tool": "search_live_leads", "area": "Poland"},
    )

    response = client.post(
        "/agent/query",
        json={"query": "show me conflicts near Poland"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "search_live_leads"
    assert payload["status"] == "no_result"
    assert payload["leads"] == []
    assert payload["resolved"]["area"] == "Poland"
    assert "No live source leads matched near Poland" in payload["summary"]


def test_agent_query_refresh_live_configs_routes_to_refresh_tool(monkeypatch) -> None:
    def fake_refresh_lead_registry(**kwargs):
        assert kwargs["source_mode"] == "gdelt"
        return [], 0

    monkeypatch.setattr("app.services.stub.refresh_lead_registry", fake_refresh_lead_registry)
    client = _client_with_agent_plan(
        monkeypatch,
        {"tool": "refresh_live_leads"},
    )

    response = client.post("/agent/query", json={"query": "Refresh live configs"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "refresh_live_leads"
    assert payload["status"] == "no_result"
    assert payload["leads"] == []


def test_agent_query_refresh_intent_overrides_bad_live_planner_search(monkeypatch) -> None:
    def fake_refresh_lead_registry(**kwargs):
        assert kwargs["source_mode"] == "gdelt"
        return [], 0

    monkeypatch.setattr("app.services.stub.refresh_lead_registry", fake_refresh_lead_registry)
    client = _client_with_agent_plan(
        monkeypatch,
        {"tool": "search_live_leads", "area": None},
    )

    response = client.post(
        "/agent/query",
        json={"query": "Refresh live leads and tell me what changed."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "refresh_live_leads"
    assert payload["planner"]["mode"] == "live"
    assert payload["resolved"]["tool"] == "refresh_live_leads"
