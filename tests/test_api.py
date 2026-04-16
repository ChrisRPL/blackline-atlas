from __future__ import annotations

import json
from urllib.error import URLError

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app, create_app
from app.services.frame_filters import FrameFilterPolicy
from app.services.sentinel_client import FixtureSentinelPayloadTransport

client = TestClient(app)


def build_api_client(
    monkeypatch,
    *,
    simsat_current_endpoint: str | None,
    simsat_baseline_endpoint: str | None,
    simsat_current_http_enabled: bool = False,
    simsat_baseline_http_enabled: bool = False,
    mapbox_context_enabled: bool | None = None,
    model_endpoint: str | None = None,
    model_http_enabled: bool = False,
    model_provider: str | None = None,
) -> TestClient:
    if simsat_current_endpoint is None:
        monkeypatch.delenv("SIMSAT_CURRENT_ENDPOINT", raising=False)
    else:
        monkeypatch.setenv("SIMSAT_CURRENT_ENDPOINT", simsat_current_endpoint)

    if simsat_baseline_endpoint is None:
        monkeypatch.delenv("SIMSAT_BASELINE_ENDPOINT", raising=False)
    else:
        monkeypatch.setenv("SIMSAT_BASELINE_ENDPOINT", simsat_baseline_endpoint)

    if simsat_current_http_enabled:
        monkeypatch.setenv("SIMSAT_CURRENT_HTTP_ENABLED", "true")
    else:
        monkeypatch.delenv("SIMSAT_CURRENT_HTTP_ENABLED", raising=False)

    if simsat_baseline_http_enabled:
        monkeypatch.setenv("SIMSAT_BASELINE_HTTP_ENABLED", "true")
    else:
        monkeypatch.delenv("SIMSAT_BASELINE_HTTP_ENABLED", raising=False)

    if mapbox_context_enabled is None:
        monkeypatch.delenv("MAPBOX_CONTEXT_ENABLED", raising=False)
    elif mapbox_context_enabled:
        monkeypatch.setenv("MAPBOX_CONTEXT_ENABLED", "true")
    else:
        monkeypatch.setenv("MAPBOX_CONTEXT_ENABLED", "false")

    if model_endpoint is None:
        monkeypatch.delenv("MODEL_ENDPOINT", raising=False)
    else:
        monkeypatch.setenv("MODEL_ENDPOINT", model_endpoint)

    if model_http_enabled:
        monkeypatch.setenv("MODEL_HTTP_ENABLED", "true")
    else:
        monkeypatch.delenv("MODEL_HTTP_ENABLED", raising=False)

    if model_provider is None:
        monkeypatch.delenv("MODEL_PROVIDER", raising=False)
    else:
        monkeypatch.setenv("MODEL_PROVIDER", model_provider)

    get_settings.cache_clear()
    return TestClient(create_app())


def stub_sentinel_health_probe(
    monkeypatch,
    *,
    current_status: int | None = None,
    baseline_status: int | None = None,
) -> None:
    def fake_urlopen(url: str, timeout: float):
        assert timeout == 5.0
        if url.endswith("mode=current"):
            assert current_status is not None
            return _FakeHTTPResponse(body=b'{"ok":true}', status=current_status)
        if url.endswith("mode=baseline"):
            assert baseline_status is not None
            return _FakeHTTPResponse(body=b'{"ok":true}', status=baseline_status)
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["model_backend"]["status"] == "ready"
    assert payload["model_backend"]["detail"] == "lfm2.5-vl-450m-prompted (fixture backend)"


def test_ui_shell_is_served_same_origin() -> None:
    response = client.get("/ui")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Blackline Atlas" in response.text
    assert "/health.config" in response.text


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
        "https://example.test/sentinel/current/ (fixture transport)"
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
        "https://example.test/sentinel/baseline/ (fixture transport)"
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
        "https://example.test/sentinel/current/ (fixture transport)"
    )
    assert configured_response.json()["simsat_baseline"]["status"] == "ready"
    assert configured_response.json()["simsat_baseline"]["detail"] == (
        "https://example.test/sentinel/baseline/ (fixture transport)"
    )
    get_settings.cache_clear()


def test_health_endpoint_reflects_current_http_transport_opt_in(monkeypatch) -> None:
    stub_sentinel_health_probe(monkeypatch, current_status=200)
    current_http_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint="https://example.test/sentinel/current/",
        simsat_baseline_endpoint=None,
        simsat_current_http_enabled=True,
    )
    current_http_response = current_http_client.get("/health")

    assert current_http_response.status_code == 200
    assert current_http_response.json()["simsat_current"]["status"] == "ready"
    assert current_http_response.json()["simsat_current"]["detail"] == (
        "https://example.test/sentinel/current/ (http transport enabled)"
    )
    assert current_http_response.json()["simsat_baseline"]["status"] == "not_configured"
    assert current_http_response.json()["simsat_baseline"]["detail"] == (
        "historical baseline endpoint not configured yet"
    )
    get_settings.cache_clear()


def test_health_endpoint_reflects_baseline_http_transport_opt_in(monkeypatch) -> None:
    stub_sentinel_health_probe(monkeypatch, baseline_status=200)
    baseline_http_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
        simsat_baseline_http_enabled=True,
    )
    baseline_http_response = baseline_http_client.get("/health")

    assert baseline_http_response.status_code == 200
    assert baseline_http_response.json()["simsat_current"]["status"] == "not_configured"
    assert baseline_http_response.json()["simsat_current"]["detail"] == (
        "current Sentinel endpoint not configured yet"
    )
    assert baseline_http_response.json()["simsat_baseline"]["status"] == "ready"
    assert baseline_http_response.json()["simsat_baseline"]["detail"] == (
        "https://example.test/sentinel/baseline/ (http transport enabled)"
    )
    get_settings.cache_clear()


def test_health_endpoint_reflects_fully_http_opted_in_sentinel_state(monkeypatch) -> None:
    stub_sentinel_health_probe(monkeypatch, current_status=200, baseline_status=200)
    fully_http_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint="https://example.test/sentinel/current/",
        simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
        simsat_current_http_enabled=True,
        simsat_baseline_http_enabled=True,
    )
    fully_http_response = fully_http_client.get("/health")

    assert fully_http_response.status_code == 200
    assert fully_http_response.json()["simsat_current"]["status"] == "ready"
    assert fully_http_response.json()["simsat_current"]["detail"] == (
        "https://example.test/sentinel/current/ (http transport enabled)"
    )
    assert fully_http_response.json()["simsat_baseline"]["status"] == "ready"
    assert fully_http_response.json()["simsat_baseline"]["detail"] == (
        "https://example.test/sentinel/baseline/ (http transport enabled)"
    )
    get_settings.cache_clear()


def test_health_endpoint_reflects_degraded_current_http_transport(monkeypatch) -> None:
    stub_sentinel_health_probe(monkeypatch, current_status=503)
    degraded_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint="https://example.test/sentinel/current/",
        simsat_baseline_endpoint=None,
        simsat_current_http_enabled=True,
    )
    degraded_response = degraded_client.get("/health")

    assert degraded_response.status_code == 200
    assert degraded_response.json()["simsat_current"]["status"] == "degraded"
    assert degraded_response.json()["simsat_current"]["detail"] == (
        "https://example.test/sentinel/current/ (http transport failed; fixture fallback active)"
    )
    assert degraded_response.json()["simsat_baseline"]["status"] == "not_configured"
    get_settings.cache_clear()


def test_health_endpoint_reflects_degraded_baseline_http_transport(monkeypatch) -> None:
    stub_sentinel_health_probe(monkeypatch, baseline_status=503)
    degraded_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
        simsat_baseline_http_enabled=True,
    )
    degraded_response = degraded_client.get("/health")

    assert degraded_response.status_code == 200
    assert degraded_response.json()["simsat_baseline"]["status"] == "degraded"
    assert degraded_response.json()["simsat_baseline"]["detail"] == (
        "https://example.test/sentinel/baseline/ (http transport failed; fixture fallback active)"
    )
    assert degraded_response.json()["simsat_current"]["status"] == "not_configured"
    get_settings.cache_clear()


def test_health_endpoint_reflects_fully_degraded_http_sentinel_state(monkeypatch) -> None:
    stub_sentinel_health_probe(monkeypatch, current_status=503, baseline_status=503)
    degraded_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint="https://example.test/sentinel/current/",
        simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
        simsat_current_http_enabled=True,
        simsat_baseline_http_enabled=True,
    )
    degraded_response = degraded_client.get("/health")

    assert degraded_response.status_code == 200
    assert degraded_response.json()["simsat_current"]["status"] == "degraded"
    assert degraded_response.json()["simsat_current"]["detail"] == (
        "https://example.test/sentinel/current/ (http transport failed; fixture fallback active)"
    )
    assert degraded_response.json()["simsat_baseline"]["status"] == "degraded"
    assert degraded_response.json()["simsat_baseline"]["detail"] == (
        "https://example.test/sentinel/baseline/ (http transport failed; fixture fallback active)"
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
    assert unconfigured_response.json()["mapbox"]["detail"] == (
        "token missing; inspection context disabled"
    )
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
    assert configured_response.json()["mapbox"]["detail"] == (
        "token present; inspection context enabled"
    )
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
    assert ready_response.json()["mapbox"]["detail"] == (
        "token present; inspection context enabled"
    )
    get_settings.cache_clear()


def test_health_endpoint_reflects_disabled_mapbox_context_config(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MAPBOX_TOKEN", "test-mapbox-token")
    disabled_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
        mapbox_context_enabled=False,
    )
    disabled_response = disabled_client.get("/health")

    assert disabled_response.status_code == 200
    assert disabled_response.json()["mapbox"]["status"] == "ready"
    assert disabled_response.json()["mapbox"]["detail"] == (
        "token present; inspection context disabled by config"
    )
    get_settings.cache_clear()


def test_health_endpoint_exposes_machine_readable_config_flags(monkeypatch) -> None:
    stub_sentinel_health_probe(monkeypatch, current_status=200, baseline_status=200)
    configured_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint="https://example.test/sentinel/current/",
        simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
        simsat_current_http_enabled=True,
        simsat_baseline_http_enabled=True,
        mapbox_context_enabled=False,
    )
    configured_response = configured_client.get("/health")

    assert configured_response.status_code == 200
    assert configured_response.json()["config"] == {
        "simsat_current_http_enabled": True,
        "simsat_baseline_http_enabled": True,
        "mapbox_context_enabled": False,
        "model_http_enabled": False,
        "model_provider": "atlas_json_http",
    }
    get_settings.cache_clear()


def test_health_endpoint_exposes_default_config_flags(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    default_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
    )
    default_response = default_client.get("/health")

    assert default_response.status_code == 200
    assert default_response.json()["config"] == {
        "simsat_current_http_enabled": False,
        "simsat_baseline_http_enabled": False,
        "mapbox_context_enabled": True,
        "model_http_enabled": False,
        "model_provider": "atlas_json_http",
    }
    get_settings.cache_clear()


def test_health_endpoint_exposes_disabled_mapbox_config_flags(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MAPBOX_TOKEN", "test-mapbox-token")
    configured_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
        mapbox_context_enabled=False,
    )
    configured_response = configured_client.get("/health")

    assert configured_response.status_code == 200
    assert configured_response.json()["status"] == "ok"
    assert configured_response.json()["config"] == {
        "simsat_current_http_enabled": False,
        "simsat_baseline_http_enabled": False,
        "mapbox_context_enabled": False,
        "model_http_enabled": False,
        "model_provider": "atlas_json_http",
    }
    assert configured_response.json()["mapbox"]["status"] == "ready"
    assert configured_response.json()["mapbox"]["detail"] == (
        "token present; inspection context disabled by config"
    )
    get_settings.cache_clear()


def test_health_endpoint_exposes_mixed_transport_config_flags(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    stub_sentinel_health_probe(monkeypatch, current_status=200)
    configured_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint="https://example.test/sentinel/current/",
        simsat_baseline_endpoint=None,
        simsat_current_http_enabled=True,
    )
    configured_response = configured_client.get("/health")

    assert configured_response.status_code == 200
    assert configured_response.json()["config"] == {
        "simsat_current_http_enabled": True,
        "simsat_baseline_http_enabled": False,
        "mapbox_context_enabled": True,
        "model_http_enabled": False,
        "model_provider": "atlas_json_http",
    }
    get_settings.cache_clear()


def test_health_endpoint_exposes_baseline_only_transport_config_flags(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MAPBOX_TOKEN", "test-mapbox-token")
    stub_sentinel_health_probe(monkeypatch, baseline_status=200)
    configured_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
        simsat_baseline_http_enabled=True,
        mapbox_context_enabled=True,
    )
    configured_response = configured_client.get("/health")

    assert configured_response.status_code == 200
    assert configured_response.json()["status"] == "ok"
    assert configured_response.json()["config"] == {
        "simsat_current_http_enabled": False,
        "simsat_baseline_http_enabled": True,
        "mapbox_context_enabled": True,
        "model_http_enabled": False,
        "model_provider": "atlas_json_http",
    }
    assert configured_response.json()["simsat_current"]["status"] == "not_configured"
    assert configured_response.json()["simsat_baseline"]["status"] == "ready"
    assert configured_response.json()["mapbox"]["status"] == "ready"
    assert configured_response.json()["mapbox"]["detail"] == (
        "token present; inspection context enabled"
    )
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
    assert default_response.json()["model_backend"]["detail"] == (
        "lfm2.5-vl-450m-prompted (fixture backend)"
    )
    get_settings.cache_clear()


def test_health_endpoint_exposes_model_http_config_and_backend_mode(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    model_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
        model_endpoint="https://example.test/model",
        model_http_enabled=True,
        model_provider="atlas_json_http",
    )
    model_response = model_client.get("/health")

    assert model_response.status_code == 200
    assert model_response.json()["model_backend"]["status"] == "ready"
    assert model_response.json()["model_backend"]["detail"] == (
        "lfm2.5-vl-450m-prompted (atlas_json_http http backend)"
    )
    assert model_response.json()["config"]["model_http_enabled"] is True
    assert model_response.json()["config"]["model_provider"] == "atlas_json_http"
    get_settings.cache_clear()


def test_health_endpoint_marks_missing_model_endpoint_not_configured(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    model_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
        model_http_enabled=True,
        model_provider="atlas_json_http",
    )
    model_response = model_client.get("/health")

    assert model_response.status_code == 200
    assert model_response.json()["model_backend"]["status"] == "not_configured"
    assert model_response.json()["model_backend"]["detail"] == "model endpoint not configured yet"
    assert model_response.json()["config"]["model_http_enabled"] is True
    get_settings.cache_clear()


def test_health_endpoint_exposes_openai_provider_backend_mode(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    model_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
        model_endpoint="https://api.openai.com/v1/responses",
        model_http_enabled=True,
        model_provider="openai_responses_http",
    )
    model_response = model_client.get("/health")

    assert model_response.status_code == 200
    assert model_response.json()["model_backend"]["status"] == "ready"
    assert model_response.json()["model_backend"]["detail"] == (
        "lfm2.5-vl-450m-prompted (openai_responses_http http backend)"
    )
    assert model_response.json()["config"]["model_provider"] == "openai_responses_http"
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
    assert alerts.json()[0]["mapbox_context_ref"] is None

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
    assert alerts.json()[0]["mapbox_context_ref"] is None

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
    assert alerts.json()[0]["mapbox_context_ref"] is None
    assert metrics.status_code == 200
    assert metrics.json()["frames_scanned"] == 88
    assert metrics.json()["alerts_emitted"] == 2
    assert metrics.json()["raw_frames_suppressed"] == 86
    assert metrics.json()["downlink_rate"] == 0.023


def test_alerts_endpoint_attaches_mapbox_context_when_token_present(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MAPBOX_TOKEN", "test-mapbox-token")
    api_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
    )

    alerts = api_client.get("/alerts")

    assert alerts.status_code == 200
    assert alerts.json()[0]["alert_id"] == "blk_00017"
    assert alerts.json()[0]["mapbox_context_ref"] == (
        ".cache/mapbox/demo_port_01/blk_00017/context.png"
    )
    assert tmp_path.joinpath(
        ".cache",
        "mapbox",
        "demo_port_01",
        "blk_00017",
        "context.png",
    ).exists()
    get_settings.cache_clear()


def test_alerts_endpoint_skips_mapbox_context_when_disabled_by_env(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MAPBOX_TOKEN", "test-mapbox-token")
    api_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
        mapbox_context_enabled=False,
    )

    alerts = api_client.get("/alerts")
    health = api_client.get("/health")

    assert alerts.status_code == 200
    assert alerts.json()[0]["alert_id"] == "blk_00017"
    assert alerts.json()[0]["mapbox_context_ref"] is None
    assert not tmp_path.joinpath(
        ".cache",
        "mapbox",
        "demo_port_01",
        "blk_00017",
        "context.png",
    ).exists()
    assert health.status_code == 200
    assert health.json()["mapbox"]["detail"] == (
        "token present; inspection context disabled by config"
    )
    get_settings.cache_clear()


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
    alerts = api_client.get("/alerts")
    metrics = api_client.get("/metrics")

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
    assert current_frame.json()["accepted_for_alerting"] is True
    assert current_frame.json()["filter_reason"] == "accepted"
    assert current_frame.json()["overlay_ref"].endswith(
        "/demo_bridge_01/bridge_access_obstruction/overlay/cur_demo_bridge_01_20260414/image.png"
    )
    assert current_frame.json()["frame"]["image_ref"] is not None
    assert baseline_frame.json()["frame"]["image_ref"] is not None
    assert alerts.status_code == 200
    assert alerts.json()[0]["alert_id"] == "blk_00018"
    assert alerts.json()[0]["action"] == "defer"
    assert alerts.json()[0]["asset_id"] == "demo_bridge_01"
    assert metrics.status_code == 200
    assert metrics.json()["frames_scanned"] == 88
    assert metrics.json()["alerts_emitted"] == 2
    assert metrics.json()["raw_frames_suppressed"] == 86
    assert metrics.json()["downlink_rate"] == 0.023
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


def test_configured_sentinel_alerts_attach_mapbox_context_when_token_present(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MAPBOX_TOKEN", "test-mapbox-token")
    api_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint="https://example.test/sentinel/current/",
        simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
    )

    start_response = api_client.post(
        "/replay/start",
        json={
            "asset_id": "demo_bridge_01",
            "scenario_id": "bridge_access_obstruction",
        },
    )
    alerts = api_client.get("/alerts")

    assert start_response.status_code == 200
    assert alerts.status_code == 200
    assert alerts.json()[0]["alert_id"] == "blk_00018"
    assert alerts.json()[0]["asset_id"] == "demo_bridge_01"
    assert alerts.json()[0]["mapbox_context_ref"] == (
        ".cache/mapbox/demo_bridge_01/blk_00018/context.png"
    )
    assert tmp_path.joinpath(
        ".cache",
        "mapbox",
        "demo_bridge_01",
        "blk_00018",
        "context.png",
    ).exists()
    get_settings.cache_clear()


def test_configured_sentinel_suppressed_alerts_skip_mapbox_context(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MAPBOX_TOKEN", "test-mapbox-token")
    api_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint="https://example.test/sentinel/current/",
        simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
    )
    api_client.app.state.atlas_service.frame_filter_policy = FrameFilterPolicy(
        cloud_cover_threshold=0.01
    )

    start_response = api_client.post(
        "/replay/start",
        json={
            "asset_id": "demo_bridge_01",
            "scenario_id": "bridge_access_obstruction",
        },
    )
    alerts = api_client.get("/alerts")

    assert start_response.status_code == 200
    assert alerts.status_code == 200
    assert alerts.json() == []
    assert not tmp_path.joinpath(
        ".cache",
        "mapbox",
        "demo_bridge_01",
        "blk_00018",
        "context.png",
    ).exists()
    get_settings.cache_clear()


def test_api_uses_baseline_transport_payload_with_baseline_only_endpoint(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_fetch(self, plan):
        if plan.params["mode"] != "baseline":
            return None
        return {
            "frame_id": "live_base_demo_port_01_20250901",
            "captured_at": "2025-09-01T10:00:00Z",
            "image_ref": "live/demo_port_01/baseline.png",
            "cloud_cover": 0.03,
        }

    monkeypatch.setattr(FixtureSentinelPayloadTransport, "fetch", fake_fetch)
    api_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
    )

    baseline_frame = api_client.get("/frames/baseline")

    assert baseline_frame.status_code == 200
    assert baseline_frame.json()["frame"]["frame_id"] == "live_base_demo_port_01_20250901"
    assert baseline_frame.json()["frame"]["image_ref"].endswith(
        "/demo_port_01/hero_port_disruption/baseline/live_base_demo_port_01_20250901/image.png"
    )
    assert baseline_frame.json()["frame"]["source"] == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=baseline"
    )


def test_api_falls_back_from_malformed_current_transport_payload(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_fetch(self, plan):
        if plan.params["mode"] != "current":
            return None
        return {
            "captured_at": "2026-04-14T18:42:00Z",
        }

    monkeypatch.setattr(FixtureSentinelPayloadTransport, "fetch", fake_fetch)
    api_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint="https://example.test/sentinel/current/",
        simsat_baseline_endpoint=None,
    )

    start_response = api_client.post(
        "/replay/start",
        json={
            "asset_id": "demo_bridge_01",
            "scenario_id": "bridge_access_obstruction",
        },
    )
    current_frame = api_client.get("/frames/current")

    assert start_response.status_code == 200
    assert current_frame.status_code == 200
    assert current_frame.json()["frame"]["frame_id"] == "cur_demo_bridge_01_20260414"
    assert current_frame.json()["frame"]["source"] == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=current"
    )
    assert current_frame.json()["accepted_for_alerting"] is True
    assert current_frame.json()["filter_reason"] == "accepted"
    assert current_frame.json()["overlay_ref"].endswith(
        "/demo_bridge_01/bridge_access_obstruction/overlay/cur_demo_bridge_01_20260414/image.png"
    )


def test_api_falls_back_from_malformed_baseline_transport_payload(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_fetch(self, plan):
        if plan.params["mode"] != "baseline":
            return None
        return {
            "captured_at": "2025-10-12T09:15:00Z",
        }

    monkeypatch.setattr(FixtureSentinelPayloadTransport, "fetch", fake_fetch)
    api_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
    )

    start_response = api_client.post(
        "/replay/start",
        json={
            "asset_id": "demo_bridge_01",
            "scenario_id": "bridge_access_obstruction",
        },
    )
    baseline_frame = api_client.get("/frames/baseline")

    assert start_response.status_code == 200
    assert baseline_frame.status_code == 200
    assert baseline_frame.json()["frame"]["frame_id"] == "base_demo_bridge_01_20251012"
    assert baseline_frame.json()["frame"]["source"] == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=baseline"
    )
    assert baseline_frame.json()["frame"]["image_ref"].endswith(
        "/demo_bridge_01/bridge_access_obstruction/baseline/base_demo_bridge_01_20251012/image.png"
    )


def test_api_can_opt_in_current_http_transport(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(url: str, timeout: float):
        assert url == (
            "https://example.test/sentinel/current"
            "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=current"
        )
        assert timeout == 5.0
        return _FakeHTTPResponse(
            body=(
                b'{"frame_id":"live_cur_demo_bridge_01_20260415",'
                b'"captured_at":"2026-04-15T07:10:00Z",'
                b'"image_ref":"live/demo_bridge_01/current.png",'
                b'"cloud_cover":0.11,'
                b'"baseline_frame_id":"base_demo_bridge_01_20251012",'
                b'"overlay_ref":"live/demo_bridge_01/overlay.png",'
                b'"accepted_for_alerting":true,'
                b'"filter_reason":"accepted"}'
            )
        )

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)
    api_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint="https://example.test/sentinel/current/",
        simsat_baseline_endpoint=None,
        simsat_current_http_enabled=True,
    )

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
    assert current_frame.status_code == 200
    assert current_frame.json()["frame"]["frame_id"] == "live_cur_demo_bridge_01_20260415"
    assert current_frame.json()["frame"]["source"] == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=current"
    )
    assert current_frame.json()["frame"]["image_ref"].endswith(
        "/demo_bridge_01/bridge_access_obstruction/current/live_cur_demo_bridge_01_20260415/image.png"
    )
    assert current_frame.json()["overlay_ref"].endswith(
        "/demo_bridge_01/bridge_access_obstruction/overlay/live_cur_demo_bridge_01_20260415/image.png"
    )
    assert baseline_frame.status_code == 200
    assert baseline_frame.json()["frame"]["frame_id"] == "base_demo_bridge_01_20251012"
    assert baseline_frame.json()["frame"]["source"] == "sentinel_baseline_stub"


def test_api_can_opt_in_baseline_http_transport(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(url: str, timeout: float):
        assert url == (
            "https://example.test/sentinel/baseline"
            "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=baseline"
        )
        assert timeout == 5.0
        return _FakeHTTPResponse(
            body=(
                b'{"frame_id":"live_base_demo_bridge_01_20251013",'
                b'"captured_at":"2025-10-13T09:15:00Z",'
                b'"image_ref":"live/demo_bridge_01/baseline.png",'
                b'"cloud_cover":0.02}'
            )
        )

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)
    api_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
        simsat_baseline_http_enabled=True,
    )

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
    assert current_frame.status_code == 200
    assert current_frame.json()["frame"]["frame_id"] == "cur_demo_bridge_01_20260414"
    assert current_frame.json()["frame"]["source"] == "sentinel_current_stub"
    assert baseline_frame.status_code == 200
    assert baseline_frame.json()["frame"]["frame_id"] == "live_base_demo_bridge_01_20251013"
    assert baseline_frame.json()["frame"]["source"] == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=baseline"
    )
    assert baseline_frame.json()["frame"]["image_ref"].endswith(
        "/demo_bridge_01/bridge_access_obstruction/baseline/live_base_demo_bridge_01_20251013/image.png"
    )


def test_api_can_opt_in_both_http_transports_together(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(url: str, timeout: float):
        assert timeout == 5.0
        if url.endswith("mode=current"):
            return _FakeHTTPResponse(
                body=(
                    b'{"frame_id":"live_cur_demo_bridge_01_20260416",'
                    b'"captured_at":"2026-04-16T06:20:00Z",'
                    b'"image_ref":"live/demo_bridge_01/current.png",'
                    b'"cloud_cover":0.09,'
                    b'"baseline_frame_id":"live_base_demo_bridge_01_20251014",'
                    b'"overlay_ref":"live/demo_bridge_01/overlay.png",'
                    b'"accepted_for_alerting":true,'
                    b'"filter_reason":"accepted"}'
                )
            )
        if url.endswith("mode=baseline"):
            return _FakeHTTPResponse(
                body=(
                    b'{"frame_id":"live_base_demo_bridge_01_20251014",'
                    b'"captured_at":"2025-10-14T09:15:00Z",'
                    b'"image_ref":"live/demo_bridge_01/baseline.png",'
                    b'"cloud_cover":0.02}'
                )
            )
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)
    api_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint="https://example.test/sentinel/current/",
        simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
        simsat_current_http_enabled=True,
        simsat_baseline_http_enabled=True,
    )

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
    assert current_frame.status_code == 200
    assert baseline_frame.status_code == 200
    assert current_frame.json()["frame"]["frame_id"] == "live_cur_demo_bridge_01_20260416"
    assert current_frame.json()["frame"]["source"] == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=current"
    )
    assert current_frame.json()["frame"]["image_ref"].endswith(
        "/demo_bridge_01/bridge_access_obstruction/current/live_cur_demo_bridge_01_20260416/image.png"
    )
    assert current_frame.json()["overlay_ref"].endswith(
        "/demo_bridge_01/bridge_access_obstruction/overlay/live_cur_demo_bridge_01_20260416/image.png"
    )
    assert baseline_frame.json()["frame"]["frame_id"] == "live_base_demo_bridge_01_20251014"
    assert baseline_frame.json()["frame"]["source"] == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=baseline"
    )
    assert baseline_frame.json()["frame"]["image_ref"].endswith(
        "/demo_bridge_01/bridge_access_obstruction/baseline/live_base_demo_bridge_01_20251014/image.png"
    )
    assert tmp_path.joinpath(
        ".cache",
        "frames",
        "demo_bridge_01",
        "bridge_access_obstruction",
        "current",
        "live_cur_demo_bridge_01_20260416",
        "metadata.json",
    ).exists()
    assert tmp_path.joinpath(
        ".cache",
        "frames",
        "demo_bridge_01",
        "bridge_access_obstruction",
        "baseline",
        "live_base_demo_bridge_01_20251014",
        "metadata.json",
    ).exists()


def test_api_keeps_mapbox_context_disabled_with_both_http_transports_enabled(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MAPBOX_TOKEN", "test-mapbox-token")

    def fake_urlopen(url: str, timeout: float):
        assert timeout == 5.0
        if url.endswith("mode=current"):
            return _FakeHTTPResponse(
                body=(
                    b'{"frame_id":"live_cur_demo_bridge_01_20260416",'
                    b'"captured_at":"2026-04-16T06:20:00Z",'
                    b'"image_ref":"live/demo_bridge_01/current.png",'
                    b'"cloud_cover":0.09,'
                    b'"baseline_frame_id":"live_base_demo_bridge_01_20251014",'
                    b'"overlay_ref":"live/demo_bridge_01/overlay.png",'
                    b'"accepted_for_alerting":true,'
                    b'"filter_reason":"accepted"}'
                )
            )
        if url.endswith("mode=baseline"):
            return _FakeHTTPResponse(
                body=(
                    b'{"frame_id":"live_base_demo_bridge_01_20251014",'
                    b'"captured_at":"2025-10-14T09:15:00Z",'
                    b'"image_ref":"live/demo_bridge_01/baseline.png",'
                    b'"cloud_cover":0.02}'
                )
            )
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)
    api_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint="https://example.test/sentinel/current/",
        simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
        simsat_current_http_enabled=True,
        simsat_baseline_http_enabled=True,
        mapbox_context_enabled=False,
    )

    start_response = api_client.post(
        "/replay/start",
        json={
            "asset_id": "demo_bridge_01",
            "scenario_id": "bridge_access_obstruction",
        },
    )
    current_frame = api_client.get("/frames/current")
    baseline_frame = api_client.get("/frames/baseline")
    alerts = api_client.get("/alerts")
    health = api_client.get("/health")

    assert start_response.status_code == 200
    assert current_frame.status_code == 200
    assert baseline_frame.status_code == 200
    assert current_frame.json()["frame"]["frame_id"] == "live_cur_demo_bridge_01_20260416"
    assert baseline_frame.json()["frame"]["frame_id"] == "live_base_demo_bridge_01_20251014"
    assert alerts.status_code == 200
    assert alerts.json()[0]["alert_id"] == "blk_00018"
    assert alerts.json()[0]["mapbox_context_ref"] is None
    assert not tmp_path.joinpath(
        ".cache",
        "mapbox",
        "demo_bridge_01",
        "blk_00018",
        "context.png",
    ).exists()
    assert health.status_code == 200
    assert health.json()["mapbox"]["detail"] == (
        "token present; inspection context disabled by config"
    )
    get_settings.cache_clear()


def test_api_falls_back_when_both_http_transports_return_non_200(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(url: str, timeout: float):
        assert timeout == 5.0
        assert url.endswith("mode=current") or url.endswith("mode=baseline")
        return _FakeHTTPResponse(body=b"", status=503)

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)
    api_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint="https://example.test/sentinel/current/",
        simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
        simsat_current_http_enabled=True,
        simsat_baseline_http_enabled=True,
    )

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
    assert current_frame.status_code == 200
    assert baseline_frame.status_code == 200
    assert current_frame.json()["frame"]["frame_id"] == "cur_demo_bridge_01_20260414"
    assert current_frame.json()["frame"]["source"] == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=current"
    )
    assert current_frame.json()["overlay_ref"].endswith(
        "/demo_bridge_01/bridge_access_obstruction/overlay/cur_demo_bridge_01_20260414/image.png"
    )
    assert baseline_frame.json()["frame"]["frame_id"] == "base_demo_bridge_01_20251012"
    assert baseline_frame.json()["frame"]["source"] == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=baseline"
    )
    assert baseline_frame.json()["frame"]["image_ref"].endswith(
        "/demo_bridge_01/bridge_access_obstruction/baseline/base_demo_bridge_01_20251012/image.png"
    )
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


def test_api_falls_back_when_both_http_transports_raise_url_error(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(url: str, timeout: float):
        assert timeout == 5.0
        assert url.endswith("mode=current") or url.endswith("mode=baseline")
        raise URLError("network down")

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)
    api_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint="https://example.test/sentinel/current/",
        simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
        simsat_current_http_enabled=True,
        simsat_baseline_http_enabled=True,
    )

    start_response = api_client.post(
        "/replay/start",
        json={
            "asset_id": "demo_bridge_01",
            "scenario_id": "bridge_access_obstruction",
        },
    )
    health_response = api_client.get("/health")
    current_frame = api_client.get("/frames/current")
    baseline_frame = api_client.get("/frames/baseline")

    assert start_response.status_code == 200
    assert health_response.status_code == 200
    assert health_response.json()["simsat_current"]["status"] == "degraded"
    assert health_response.json()["simsat_current"]["detail"] == (
        "https://example.test/sentinel/current/ (http transport failed; fixture fallback active)"
    )
    assert health_response.json()["simsat_baseline"]["status"] == "degraded"
    assert health_response.json()["simsat_baseline"]["detail"] == (
        "https://example.test/sentinel/baseline/ (http transport failed; fixture fallback active)"
    )
    assert current_frame.status_code == 200
    assert baseline_frame.status_code == 200
    assert current_frame.json()["frame"]["frame_id"] == "cur_demo_bridge_01_20260414"
    assert current_frame.json()["frame"]["source"] == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=current"
    )
    assert current_frame.json()["overlay_ref"].endswith(
        "/demo_bridge_01/bridge_access_obstruction/overlay/cur_demo_bridge_01_20260414/image.png"
    )
    assert baseline_frame.json()["frame"]["frame_id"] == "base_demo_bridge_01_20251012"
    assert baseline_frame.json()["frame"]["source"] == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=baseline"
    )
    assert baseline_frame.json()["frame"]["image_ref"].endswith(
        "/demo_bridge_01/bridge_access_obstruction/baseline/base_demo_bridge_01_20251012/image.png"
    )
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


def test_api_uses_configured_sentinel_adapters_for_suppressed_replay_switch(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    api_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint="https://example.test/sentinel/current/",
        simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
    )
    api_client.app.state.atlas_service.frame_filter_policy = FrameFilterPolicy(
        cloud_cover_threshold=0.01
    )

    start_response = api_client.post(
        "/replay/start",
        json={
            "asset_id": "demo_bridge_01",
            "scenario_id": "bridge_access_obstruction",
        },
    )
    current_frame = api_client.get("/frames/current")
    baseline_frame = api_client.get("/frames/baseline")
    alerts = api_client.get("/alerts")
    metrics = api_client.get("/metrics")

    assert start_response.status_code == 200
    assert current_frame.status_code == 200
    assert baseline_frame.status_code == 200
    assert current_frame.json()["frame"]["source"] == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=current"
    )
    assert baseline_frame.json()["frame"]["source"] == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=baseline"
    )
    assert current_frame.json()["accepted_for_alerting"] is False
    assert current_frame.json()["filter_reason"] == "cloud_cover_too_high"
    assert current_frame.json()["overlay_ref"] is None
    assert alerts.status_code == 200
    assert alerts.json() == []
    assert metrics.status_code == 200
    assert metrics.json()["frames_scanned"] == 88
    assert metrics.json()["alerts_emitted"] == 1
    assert metrics.json()["raw_frames_suppressed"] == 87
    assert metrics.json()["downlink_rate"] == 0.011
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


def test_api_uses_openai_provider_model_backend_smoke_path(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MODEL_VERSION", "gpt-4.1-mini")

    def fake_urlopen(request, timeout: float):
        assert request.full_url == "https://api.openai.com/v1/responses"
        assert timeout == 10.0
        body = json.loads(request.data.decode("utf-8"))
        assert body["model"] == "gpt-4.1-mini"
        assert body["input"][0]["role"] == "system"
        assert body["input"][1]["role"] == "user"
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "output": [
                        {
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": (
                                        '{"event_type":"probable_large_scale_disruption",'
                                        '"severity":"high","confidence":0.91,'
                                        '"bbox":[0.19,0.26,0.73,0.84],'
                                        '"civilian_impact":"trade_disruption",'
                                        '"why":"OpenAI provider confirmed macro disruption.",'
                                        '"action":"downlink_now"}'
                                    ),
                                }
                            ]
                        }
                    ]
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_wrapper.urlopen", fake_urlopen)
    model_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
        model_endpoint="https://api.openai.com/v1/responses",
        model_http_enabled=True,
        model_provider="openai_responses_http",
    )

    frame = model_client.get("/frames/current")
    alerts = model_client.get("/alerts")
    metrics = model_client.get("/metrics")

    assert frame.status_code == 200
    assert frame.json()["accepted_for_alerting"] is True
    assert frame.json()["filter_reason"] == "accepted"
    assert alerts.status_code == 200
    assert alerts.json()[0]["confidence"] == 0.91
    assert alerts.json()[0]["civilian_impact"] == "trade_disruption"
    assert alerts.json()[0]["why"] == "OpenAI provider confirmed macro disruption."
    assert alerts.json()[0]["source"]["model_version"] == "gpt-4.1-mini"
    assert metrics.status_code == 200
    assert metrics.json()["alerts_emitted"] == 5
    get_settings.cache_clear()


def test_api_openai_provider_model_backend_falls_back_to_fixture_output(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MODEL_VERSION", "gpt-4.1-mini")

    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        raise URLError("offline")

    monkeypatch.setattr("app.services.model_wrapper.urlopen", fake_urlopen)
    model_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
        model_endpoint="https://api.openai.com/v1/responses",
        model_http_enabled=True,
        model_provider="openai_responses_http",
    )

    alerts = model_client.get("/alerts")

    assert alerts.status_code == 200
    assert alerts.json()[0]["confidence"] == 0.89
    assert alerts.json()[0]["civilian_impact"] == "shipping_or_aid_disruption"
    assert (
        alerts.json()[0]["why"]
        == "Large terminal footprint change versus baseline near bulk loading berths."
    )
    assert alerts.json()[0]["source"]["model_version"] == "gpt-4.1-mini"
    get_settings.cache_clear()


class _FakeHTTPResponse:
    def __init__(self, *, body: bytes, status: int = 200) -> None:
        self.status = status
        self._body = body

    def __enter__(self) -> _FakeHTTPResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self.status
