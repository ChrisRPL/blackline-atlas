from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_agent_tools_contract() -> None:
    client = TestClient(create_app())

    response = client.get("/agent/tools")

    assert response.status_code == 200
    payload = response.json()
    assert [item["name"] for item in payload] == [
        "latest_alerts",
        "biggest_disruptions",
        "site_compare",
        "explain_alert",
    ]


def test_agent_query_latest_alerts_returns_watchlist_latest() -> None:
    client = TestClient(create_app())

    response = client.post("/agent/query", json={"query": "show latest alerts"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "latest_alerts"
    assert payload["status"] == "ok"
    assert payload["focus_asset_id"] == "demo_bridge_01"
    assert payload["alerts"][0]["alert_id"] == "blk_00018"
    assert payload["compare"]["asset_id"] == "demo_bridge_01"
    assert payload["resolved"] == {
        "tool": "latest_alerts",
        "area": None,
        "category": None,
        "site_id": None,
        "alert_id": None,
        "selected_asset_id": None,
        "limit": 3,
    }
    assert payload["planner"]["mode"] == "deterministic"
    assert payload["planner"]["reason"] == "fixture_planner"
    assert payload["trust"]["mode"] == "replay_safe"


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


def test_agent_query_explain_alert_uses_selected_asset_context() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/agent/query",
        json={"query": "why is this high confidence", "selected_asset_id": "demo_port_01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "explain_alert"
    assert payload["planner"]["mode"] == "deterministic"
    assert payload["planner"]["reason"] == "fixture_planner"
    assert payload["focus_asset_id"] == "demo_port_01"
    assert payload["focus_alert_id"] == "blk_00017"
    assert "Large terminal footprint change" in payload["summary"]
    assert payload["resolved"]["site_id"] == "demo_port_01"
    assert payload["resolved"]["selected_asset_id"] == "demo_port_01"


def test_agent_query_explain_alert_returns_no_result_for_reference_control_site() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/agent/query",
        json={"query": "why is this flagged", "selected_asset_id": "ras_abu_jarjur_01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "explain_alert"
    assert payload["status"] == "no_result"
    assert payload["focus_asset_id"] is None
    assert "No accepted alert" in payload["summary"]


def test_agent_query_latest_alerts_can_return_no_result_for_real_watchlist_area() -> None:
    client = TestClient(create_app())

    response = client.post("/agent/query", json={"query": "show latest alerts near Bahrain"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "latest_alerts"
    assert payload["status"] == "no_result"
    assert payload["focus_asset_id"] is None
    assert payload["alerts"] == []
    assert payload["resolved"]["area"] == "Bahrain"
