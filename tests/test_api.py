from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app, create_app
from app.services.frame_filters import FrameFilterPolicy

client = TestClient(app)


def build_api_client(
    monkeypatch,
    *,
    simsat_current_endpoint: str | None,
    simsat_baseline_endpoint: str | None,
) -> TestClient:
    if simsat_current_endpoint is None:
        monkeypatch.delenv("SIMSAT_CURRENT_ENDPOINT", raising=False)
    else:
        monkeypatch.setenv("SIMSAT_CURRENT_ENDPOINT", simsat_current_endpoint)

    if simsat_baseline_endpoint is None:
        monkeypatch.delenv("SIMSAT_BASELINE_ENDPOINT", raising=False)
    else:
        monkeypatch.setenv("SIMSAT_BASELINE_ENDPOINT", simsat_baseline_endpoint)

    get_settings.cache_clear()
    return TestClient(create_app())


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["model_backend"]["status"] == "ready"


def test_health_endpoint_reflects_current_only_sentinel_config(monkeypatch) -> None:
    current_only_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint="https://example.test/sentinel/current/",
        simsat_baseline_endpoint=None,
    )
    current_response = current_only_client.get("/health")

    assert current_response.status_code == 200
    assert current_response.json()["simsat_current"]["status"] == "ready"
    assert current_response.json()["simsat_current"]["detail"] == (
        "https://example.test/sentinel/current/"
    )
    assert current_response.json()["simsat_baseline"]["status"] == "not_configured"
    assert current_response.json()["simsat_baseline"]["detail"] == (
        "historical baseline endpoint not configured yet"
    )
    get_settings.cache_clear()


def test_health_endpoint_reflects_baseline_only_sentinel_config(monkeypatch) -> None:
    baseline_only_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
    )
    baseline_response = baseline_only_client.get("/health")

    assert baseline_response.status_code == 200
    assert baseline_response.json()["simsat_current"]["status"] == "not_configured"
    assert baseline_response.json()["simsat_current"]["detail"] == (
        "current Sentinel endpoint not configured yet"
    )
    assert baseline_response.json()["simsat_baseline"]["status"] == "ready"
    assert baseline_response.json()["simsat_baseline"]["detail"] == (
        "https://example.test/sentinel/baseline/"
    )
    get_settings.cache_clear()


def test_health_endpoint_reflects_fully_configured_sentinel_state(monkeypatch) -> None:
    configured_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint="https://example.test/sentinel/current/",
        simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
    )
    configured_response = configured_client.get("/health")

    assert configured_response.status_code == 200
    assert configured_response.json()["simsat_current"]["status"] == "ready"
    assert configured_response.json()["simsat_current"]["detail"] == (
        "https://example.test/sentinel/current/"
    )
    assert configured_response.json()["simsat_baseline"]["status"] == "ready"
    assert configured_response.json()["simsat_baseline"]["detail"] == (
        "https://example.test/sentinel/baseline/"
    )
    get_settings.cache_clear()


def test_health_endpoint_reflects_unconfigured_dependencies(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MAPBOX_TOKEN", raising=False)
    unconfigured_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
    )
    unconfigured_response = unconfigured_client.get("/health")

    assert unconfigured_response.status_code == 200
    assert unconfigured_response.json()["simsat_current"]["status"] == "not_configured"
    assert unconfigured_response.json()["simsat_current"]["detail"] == (
        "current Sentinel endpoint not configured yet"
    )
    assert unconfigured_response.json()["simsat_baseline"]["status"] == "not_configured"
    assert unconfigured_response.json()["simsat_baseline"]["detail"] == (
        "historical baseline endpoint not configured yet"
    )
    assert unconfigured_response.json()["mapbox"]["status"] == "not_configured"
    assert unconfigured_response.json()["mapbox"]["detail"] == "token missing"
    get_settings.cache_clear()


def test_health_endpoint_reflects_configured_mapbox_token(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MAPBOX_TOKEN", "test-mapbox-token")
    configured_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
    )
    configured_response = configured_client.get("/health")

    assert configured_response.status_code == 200
    assert configured_response.json()["mapbox"]["status"] == "ready"
    assert configured_response.json()["mapbox"]["detail"] == "token present"
    get_settings.cache_clear()


def test_health_endpoint_reflects_fully_ready_dependencies(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MAPBOX_TOKEN", "test-mapbox-token")
    ready_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint="https://example.test/sentinel/current/",
        simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
    )
    ready_response = ready_client.get("/health")

    assert ready_response.status_code == 200
    assert ready_response.json()["simsat_current"]["status"] == "ready"
    assert ready_response.json()["simsat_baseline"]["status"] == "ready"
    assert ready_response.json()["mapbox"]["status"] == "ready"
    assert ready_response.json()["mapbox"]["detail"] == "token present"
    get_settings.cache_clear()


def test_health_endpoint_reflects_default_identity(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("MODEL_VERSION", raising=False)
    default_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
    )
    default_response = default_client.get("/health")

    assert default_response.status_code == 200
    assert default_response.json()["app_env"] == "development"
    assert default_response.json()["model_backend"]["status"] == "ready"
    assert default_response.json()["model_backend"]["detail"] == "lfm2.5-vl-450m-prompted"
    get_settings.cache_clear()


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


def test_replay_status_reflects_default_identity(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    replay_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
    )
    status_response = replay_client.get("/replay/status")

    assert status_response.status_code == 200
    assert status_response.json()["running"] is False
    assert status_response.json()["asset_id"] is None
    assert status_response.json()["scenario_id"] is None
    assert status_response.json()["hero_asset_id"] == "demo_port_01"
    get_settings.cache_clear()


def test_replay_status_reflects_started_identity(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    replay_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
    )
    start_response = replay_client.post(
        "/replay/start",
        json={
            "asset_id": "demo_bridge_01",
            "scenario_id": "bridge_access_obstruction",
        },
    )
    status_response = replay_client.get("/replay/status")

    assert start_response.status_code == 200
    assert status_response.status_code == 200
    assert status_response.json()["running"] is True
    assert status_response.json()["asset_id"] == "demo_bridge_01"
    assert status_response.json()["scenario_id"] == "bridge_access_obstruction"
    assert status_response.json()["hero_asset_id"] == "demo_port_01"
    get_settings.cache_clear()


def test_replay_start_response_reflects_started_identity(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    replay_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
    )
    start_response = replay_client.post(
        "/replay/start",
        json={
            "asset_id": "demo_bridge_01",
            "scenario_id": "bridge_access_obstruction",
        },
    )

    assert start_response.status_code == 200
    assert start_response.json()["running"] is True
    assert start_response.json()["asset_id"] == "demo_bridge_01"
    assert start_response.json()["scenario_id"] == "bridge_access_obstruction"
    assert start_response.json()["hero_asset_id"] == "demo_port_01"
    get_settings.cache_clear()


def test_replay_stop_response_reflects_reset_identity(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    replay_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
    )
    start_response = replay_client.post(
        "/replay/start",
        json={
            "asset_id": "demo_bridge_01",
            "scenario_id": "bridge_access_obstruction",
        },
    )
    stop_response = replay_client.post("/replay/stop")

    assert start_response.status_code == 200
    assert stop_response.status_code == 200
    assert stop_response.json()["running"] is False
    assert stop_response.json()["asset_id"] is None
    assert stop_response.json()["scenario_id"] is None
    assert stop_response.json()["hero_asset_id"] == "demo_port_01"
    get_settings.cache_clear()


def test_suppressed_frame_outputs_remain_aligned(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    api_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
    )
    api_client.app.state.atlas_service.frame_filter_policy = FrameFilterPolicy(
        cloud_cover_threshold=0.01
    )
    current_frame_response = api_client.get("/frames/current")
    alerts_response = api_client.get("/alerts")
    metrics_response = api_client.get("/metrics")

    assert current_frame_response.status_code == 200
    assert current_frame_response.json()["accepted_for_alerting"] is False
    assert current_frame_response.json()["filter_reason"] == "cloud_cover_too_high"
    assert current_frame_response.json()["overlay_ref"] is None
    assert alerts_response.status_code == 200
    assert alerts_response.json() == []
    assert metrics_response.status_code == 200
    assert metrics_response.json()["alerts_emitted"] == 4
    assert metrics_response.json()["raw_frames_suppressed"] == 139
    assert metrics_response.json()["downlink_rate"] == 0.028
    get_settings.cache_clear()


def test_replay_status_resets_identity_after_stop(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    replay_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
    )
    start_response = replay_client.post(
        "/replay/start",
        json={
            "asset_id": "demo_bridge_01",
            "scenario_id": "bridge_access_obstruction",
        },
    )
    stop_response = replay_client.post("/replay/stop")
    status_response = replay_client.get("/replay/status")

    assert start_response.status_code == 200
    assert stop_response.status_code == 200
    assert status_response.status_code == 200
    assert status_response.json()["running"] is False
    assert status_response.json()["asset_id"] is None
    assert status_response.json()["scenario_id"] is None
    assert status_response.json()["hero_asset_id"] == "demo_port_01"
    get_settings.cache_clear()


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


def test_api_uses_configured_sentinel_adapters_through_replay_switch(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SIMSAT_CURRENT_ENDPOINT", "https://example.test/sentinel/current/")
    monkeypatch.setenv("SIMSAT_BASELINE_ENDPOINT", "https://example.test/sentinel/baseline/")
    get_settings.cache_clear()
    api_client = TestClient(create_app())

    start_response = api_client.post(
        "/replay/start",
        json={
            "asset_id": "demo_bridge_01",
            "scenario_id": "bridge_access_obstruction",
        },
    )
    current_frame = api_client.get("/frames/current")
    baseline_frame = api_client.get("/frames/baseline")

    assert start_response.status_code == 200
    assert start_response.json()["scenario_id"] == "bridge_access_obstruction"
    assert start_response.json()["asset_id"] == "demo_bridge_01"
    assert current_frame.status_code == 200
    assert current_frame.json()["frame"]["source"] == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=current"
    )
    assert baseline_frame.status_code == 200
    assert baseline_frame.json()["frame"]["source"] == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=baseline"
    )
    assert current_frame.json()["frame"]["image_ref"] is not None
    assert baseline_frame.json()["frame"]["image_ref"] is not None
    assert tmp_path.joinpath(
        ".cache",
        "frames",
        "demo_bridge_01",
        "bridge_access_obstruction",
        "current",
        "cur_demo_bridge_01_20260414",
        "metadata.json",
    ).exists()
    assert tmp_path.joinpath(
        ".cache",
        "frames",
        "demo_bridge_01",
        "bridge_access_obstruction",
        "baseline",
        "base_demo_bridge_01_20251012",
        "metadata.json",
    ).exists()
