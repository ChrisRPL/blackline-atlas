from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["model_backend"]["status"] == "ready"


def test_assets_endpoint_returns_seeded_assets() -> None:
    response = client.get("/assets")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 2
    assert payload[0]["asset_id"] == "demo_port_01"


def test_replay_cycle() -> None:
    start_response = client.post("/replay/start", json={"asset_id": "demo_bridge_01"})
    assert start_response.status_code == 200
    assert start_response.json()["running"] is True
    assert start_response.json()["asset_id"] == "demo_bridge_01"

    status_response = client.get("/replay/status")
    assert status_response.status_code == 200
    assert status_response.json()["running"] is True

    stop_response = client.post("/replay/stop")
    assert stop_response.status_code == 200
    assert stop_response.json()["running"] is False


def test_default_frames_alerts_and_metrics_use_hero_scenario() -> None:
    client.post("/replay/stop")

    current_frame = client.get("/frames/current")
    baseline_frame = client.get("/frames/baseline")
    alerts = client.get("/alerts")
    metrics = client.get("/metrics")

    assert current_frame.status_code == 200
    assert current_frame.json()["frame"]["asset_id"] == "demo_port_01"
    assert current_frame.json()["frame"]["image_ref"].endswith(
        "/demo_port_01/hero_port_disruption/current/cur_demo_port_01_20260414/image.png"
    )
    assert current_frame.json()["accepted_for_alerting"] is True
    assert current_frame.json()["filter_reason"] == "accepted"
    assert current_frame.json()["overlay_ref"].endswith(
        "/demo_port_01/hero_port_disruption/overlay/cur_demo_port_01_20260414/image.png"
    )

    assert baseline_frame.status_code == 200
    assert baseline_frame.json()["frame"]["frame_id"] == "base_demo_port_01_20250901"

    assert alerts.status_code == 200
    assert alerts.json()[0]["alert_id"] == "blk_00017"
    assert alerts.json()[0]["action"] == "downlink_now"

    assert metrics.status_code == 200
    assert metrics.json()["frames_scanned"] == 143
    assert metrics.json()["alerts_emitted"] == 5
    assert metrics.json()["raw_frames_suppressed"] == 138
    assert metrics.json()["downlink_rate"] == 0.035


def test_replay_switches_frames_alerts_and_metrics_to_selected_asset() -> None:
    start_response = client.post("/replay/start", json={"asset_id": "demo_bridge_01"})
    assert start_response.status_code == 200
    assert start_response.json()["scenario_id"] == "bridge_access_obstruction"

    current_frame = client.get("/frames/current")
    baseline_frame = client.get("/frames/baseline")
    alerts = client.get("/alerts")
    metrics = client.get("/metrics")

    assert current_frame.status_code == 200
    assert current_frame.json()["frame"]["asset_id"] == "demo_bridge_01"
    assert current_frame.json()["frame"]["image_ref"].endswith(
        "/demo_bridge_01/bridge_access_obstruction/current/cur_demo_bridge_01_20260414/image.png"
    )
    assert current_frame.json()["accepted_for_alerting"] is True
    assert current_frame.json()["filter_reason"] == "accepted"
    assert current_frame.json()["overlay_ref"].endswith(
        "/demo_bridge_01/bridge_access_obstruction/overlay/cur_demo_bridge_01_20260414/image.png"
    )

    assert baseline_frame.status_code == 200
    assert baseline_frame.json()["frame"]["frame_id"] == "base_demo_bridge_01_20251012"

    assert alerts.status_code == 200
    assert alerts.json()[0]["alert_id"] == "blk_00018"
    assert alerts.json()[0]["action"] == "defer"
    assert alerts.json()[0]["asset_id"] == "demo_bridge_01"

    assert metrics.status_code == 200
    assert metrics.json()["frames_scanned"] == 88
    assert metrics.json()["alerts_emitted"] == 2
    assert metrics.json()["raw_frames_suppressed"] == 86
    assert metrics.json()["downlink_rate"] == 0.023


def test_replay_prefers_explicit_scenario_id_over_asset_hint() -> None:
    start_response = client.post(
        "/replay/start",
        json={
            "asset_id": "demo_port_01",
            "scenario_id": "bridge_access_obstruction",
        },
    )
    assert start_response.status_code == 200
    assert start_response.json()["scenario_id"] == "bridge_access_obstruction"
    assert start_response.json()["asset_id"] == "demo_bridge_01"

    current_frame = client.get("/frames/current")
    alerts = client.get("/alerts")
    metrics = client.get("/metrics")

    assert current_frame.status_code == 200
    assert current_frame.json()["frame"]["asset_id"] == "demo_bridge_01"
    assert alerts.status_code == 200
    assert alerts.json()[0]["alert_id"] == "blk_00018"
    assert metrics.status_code == 200
    assert metrics.json()["frames_scanned"] == 88
    assert metrics.json()["alerts_emitted"] == 2
    assert metrics.json()["raw_frames_suppressed"] == 86
    assert metrics.json()["downlink_rate"] == 0.023
