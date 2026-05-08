from __future__ import annotations

import json
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app, create_app
from app.schemas.lead import Lead
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
    simsat_required: bool = False,
    mapbox_context_enabled: bool | None = None,
    model_endpoint: str | None = None,
    model_http_enabled: bool = False,
    model_provider: str | None = None,
    agent_endpoint: str | None = None,
    agent_http_enabled: bool = False,
    agent_provider: str | None = None,
    agent_model_version: str | None = None,
    sam3_endpoint: str | None = None,
    sam3_http_enabled: bool | None = None,
    sam3_required: bool | None = None,
    analyst_endpoint: str | None = None,
    analyst_http_enabled: bool = False,
    analyst_provider: str | None = None,
    analyst_model_version: str | None = None,
) -> TestClient:
    if simsat_current_endpoint is None:
        monkeypatch.setenv("SIMSAT_CURRENT_ENDPOINT", "")
    else:
        monkeypatch.setenv("SIMSAT_CURRENT_ENDPOINT", simsat_current_endpoint)

    if simsat_baseline_endpoint is None:
        monkeypatch.setenv("SIMSAT_BASELINE_ENDPOINT", "")
    else:
        monkeypatch.setenv("SIMSAT_BASELINE_ENDPOINT", simsat_baseline_endpoint)

    if simsat_current_http_enabled:
        monkeypatch.setenv("SIMSAT_CURRENT_HTTP_ENABLED", "true")
    else:
        monkeypatch.setenv("SIMSAT_CURRENT_HTTP_ENABLED", "")

    if simsat_baseline_http_enabled:
        monkeypatch.setenv("SIMSAT_BASELINE_HTTP_ENABLED", "true")
    else:
        monkeypatch.setenv("SIMSAT_BASELINE_HTTP_ENABLED", "")

    if simsat_required:
        monkeypatch.setenv("SIMSAT_REQUIRED", "true")
    else:
        monkeypatch.setenv("SIMSAT_REQUIRED", "")

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

    if agent_endpoint is None:
        monkeypatch.delenv("AGENT_ENDPOINT", raising=False)
    else:
        monkeypatch.setenv("AGENT_ENDPOINT", agent_endpoint)

    if agent_http_enabled:
        monkeypatch.setenv("AGENT_HTTP_ENABLED", "true")
    else:
        monkeypatch.delenv("AGENT_HTTP_ENABLED", raising=False)

    if agent_provider is None:
        monkeypatch.delenv("AGENT_PROVIDER", raising=False)
    else:
        monkeypatch.setenv("AGENT_PROVIDER", agent_provider)

    if agent_model_version is None:
        monkeypatch.delenv("AGENT_MODEL_VERSION", raising=False)
    else:
        monkeypatch.setenv("AGENT_MODEL_VERSION", agent_model_version)

    if sam3_endpoint is None:
        monkeypatch.delenv("SAM3_ENDPOINT", raising=False)
    else:
        monkeypatch.setenv("SAM3_ENDPOINT", sam3_endpoint)

    if sam3_http_enabled is None:
        monkeypatch.delenv("SAM3_HTTP_ENABLED", raising=False)
    elif sam3_http_enabled:
        monkeypatch.setenv("SAM3_HTTP_ENABLED", "true")
    else:
        monkeypatch.setenv("SAM3_HTTP_ENABLED", "false")

    if sam3_required is None:
        monkeypatch.delenv("SAM3_REQUIRED", raising=False)
    elif sam3_required:
        monkeypatch.setenv("SAM3_REQUIRED", "true")
    else:
        monkeypatch.setenv("SAM3_REQUIRED", "false")

    if analyst_endpoint is None:
        monkeypatch.delenv("ANALYST_ENDPOINT", raising=False)
    else:
        monkeypatch.setenv("ANALYST_ENDPOINT", analyst_endpoint)

    if analyst_http_enabled:
        monkeypatch.setenv("ANALYST_HTTP_ENABLED", "true")
    else:
        monkeypatch.delenv("ANALYST_HTTP_ENABLED", raising=False)

    if analyst_provider is None:
        monkeypatch.delenv("ANALYST_PROVIDER", raising=False)
    else:
        monkeypatch.setenv("ANALYST_PROVIDER", analyst_provider)

    if analyst_model_version is None:
        monkeypatch.delenv("ANALYST_MODEL_VERSION", raising=False)
    else:
        monkeypatch.setenv("ANALYST_MODEL_VERSION", analyst_model_version)

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
        query = parse_qs(urlparse(url).query)
        mode = query.get("mode", [None])[0]
        if mode == "current":
            assert current_status is not None
            return _FakeHTTPResponse(body=b'{"ok":true}', status=current_status)
        if mode == "baseline":
            assert baseline_status is not None
            return _FakeHTTPResponse(body=b'{"ok":true}', status=baseline_status)
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)


def stub_http_dependency_probe(monkeypatch, *, status: int = 200) -> None:
    def fake_urlopen(request, timeout: float):
        assert timeout == 0.25
        _ = request
        return _FakeHTTPResponse(body=b'{"ok":true}', status=status)

    monkeypatch.setattr("app.services.stub.urlopen", fake_urlopen)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["model_backend"]["status"] == "ready"
    assert payload["model_backend"]["detail"] == "lfm2.5-vl-450m-prompted (fixture backend)"
    assert payload["agent_backend"]["status"] == "ready"
    assert payload["agent_backend"]["detail"] == "lfm2.5-1.2b-instruct (fixture planner)"
    assert payload["sam3_backend"]["status"] == "degraded"
    assert "real SAM3 HTTP segmentation is required" in payload["sam3_backend"]["detail"]


def test_model_status_endpoint_exposes_adapter_gate() -> None:
    response = client.get("/model/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["base_model"] == "LiquidAI/LFM2.5-VL-450M"
    assert (
        payload["candidate_adapter"]
        == "ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter"
    )
    assert payload["training_dataset"] == "ChrisRPL/blackline-atlas-training-corpus-v1"
    assert payload["adapter_signal_role"] == "optional_non_authoritative"
    assert payload["runtime_authority"] == "source_led_sam3_liquid_guarded"
    assert payload["can_affect_alerts"] is False
    assert payload["decision"] == "evidence_adapter_guarded_runtime"
    assert payload["recommended_runtime"] == "source_led_sam3_liquid_guarded"
    assert payload["frozen_gold_cases"] == 22
    assert payload["reported_eval_cases"] == 22
    assert payload["reported_eval_scope"] == "hf_corpus_simsat_gold_eval_full_22"
    assert payload["base_eval"]["action_match"] == 0
    assert payload["base_eval"]["schema_valid"] == 0
    assert payload["adapter_eval"]["action_match"] == 9
    assert payload["adapter_eval"]["schema_valid"] == 19
    assert payload["adapter_eval"]["false_positives"] == 3
    assert payload["latest_training_job"] == "69f66f889d85bec4d76f0be0"
    assert payload["training_eval_loss_start"] == 3.0021
    assert payload["training_eval_loss_final"] == 0.3273
    assert payload["acceptance_failures"] == [
        "full-v1b action match is 9/22 on corpus-native SimSat gold eval",
        "full-v1b downlink recall is 3/12 on positive SimSat gold cases",
        "full-v1b produced 3 false-positive downlink_now predictions on negative cases",
        "runtime must keep parser repair, source-led context, and SAM3 guardrails active",
    ]
    assert [item["status"] for item in payload["evaluated_adapters"]] == [
        "superseded_rejected",
        "superseded_rejected",
        "published_rejected",
        "published_guarded_runtime",
    ]


def test_ui_shell_is_served_same_origin() -> None:
    response = client.get("/ui")
    static_response = client.get("/ui-static/shell.js")

    assert response.status_code == 200
    assert static_response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Blackline Atlas" in response.text
    assert "/health" in static_response.text
    assert "/model/status" in static_response.text
    assert "/replay/snapshot" in static_response.text
    assert "/evidence/current" in static_response.text
    assert "/replay/status" in static_response.text
    assert "/assets" in static_response.text


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


def test_health_endpoint_marks_missing_simsat_degraded_when_required(monkeypatch) -> None:
    required_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
        simsat_required=True,
    )
    response = required_client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["simsat_required"] is True
    assert payload["simsat_current"]["status"] == "degraded"
    assert payload["simsat_baseline"]["status"] == "degraded"
    assert "live SimSat required" in payload["simsat_current"]["detail"]
    assert "live SimSat required" in payload["simsat_baseline"]["detail"]
    get_settings.cache_clear()


def test_frame_image_serves_cached_simsat_frame() -> None:
    image_path = Path(".cache/frames/test_route/current/frame/image.png")
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    )

    response = client.get("/frame-image", params={"ref": str(image_path)})

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_frame_image_serves_mapbox_context_frame() -> None:
    image_path = Path("var/mapbox_context/live_test_marker/current_1.00000_2.00000.png")
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    )

    response = client.get("/frame-image", params={"ref": str(image_path)})

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_frame_image_rejects_path_outside_frame_cache() -> None:
    response = client.get("/frame-image", params={"ref": "app/api/routes.py"})

    assert response.status_code == 404


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
        "simsat_required": False,
        "mapbox_context_enabled": False,
        "model_http_enabled": False,
        "model_provider": "atlas_json_http",
        "agent_model_version": "lfm2.5-1.2b-instruct",
        "agent_http_enabled": False,
        "agent_provider": "atlas_json_http",
        "sam3_model_version": "facebook/sam3",
        "sam3_http_enabled": True,
        "sam3_required": True,
        "analyst_model_version": "LiquidAI/LFM2.5-VL-450M",
        "analyst_adapter_ref": (
            "ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter"
        ),
        "analyst_http_enabled": False,
        "analyst_provider": "atlas_json_http",
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
        "simsat_required": False,
        "mapbox_context_enabled": True,
        "model_http_enabled": False,
        "model_provider": "atlas_json_http",
        "agent_model_version": "lfm2.5-1.2b-instruct",
        "agent_http_enabled": False,
        "agent_provider": "atlas_json_http",
        "sam3_model_version": "facebook/sam3",
        "sam3_http_enabled": True,
        "sam3_required": True,
        "analyst_model_version": "LiquidAI/LFM2.5-VL-450M",
        "analyst_adapter_ref": (
            "ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter"
        ),
        "analyst_http_enabled": False,
        "analyst_provider": "atlas_json_http",
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
        "simsat_required": False,
        "mapbox_context_enabled": False,
        "model_http_enabled": False,
        "model_provider": "atlas_json_http",
        "agent_model_version": "lfm2.5-1.2b-instruct",
        "agent_http_enabled": False,
        "agent_provider": "atlas_json_http",
        "sam3_model_version": "facebook/sam3",
        "sam3_http_enabled": True,
        "sam3_required": True,
        "analyst_model_version": "LiquidAI/LFM2.5-VL-450M",
        "analyst_adapter_ref": (
            "ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter"
        ),
        "analyst_http_enabled": False,
        "analyst_provider": "atlas_json_http",
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
        "simsat_required": False,
        "mapbox_context_enabled": True,
        "model_http_enabled": False,
        "model_provider": "atlas_json_http",
        "agent_model_version": "lfm2.5-1.2b-instruct",
        "agent_http_enabled": False,
        "agent_provider": "atlas_json_http",
        "sam3_model_version": "facebook/sam3",
        "sam3_http_enabled": True,
        "sam3_required": True,
        "analyst_model_version": "LiquidAI/LFM2.5-VL-450M",
        "analyst_adapter_ref": (
            "ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter"
        ),
        "analyst_http_enabled": False,
        "analyst_provider": "atlas_json_http",
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
        "simsat_required": False,
        "mapbox_context_enabled": True,
        "model_http_enabled": False,
        "model_provider": "atlas_json_http",
        "agent_model_version": "lfm2.5-1.2b-instruct",
        "agent_http_enabled": False,
        "agent_provider": "atlas_json_http",
        "sam3_model_version": "facebook/sam3",
        "sam3_http_enabled": True,
        "sam3_required": True,
        "analyst_model_version": "LiquidAI/LFM2.5-VL-450M",
        "analyst_adapter_ref": (
            "ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter"
        ),
        "analyst_http_enabled": False,
        "analyst_provider": "atlas_json_http",
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
    stub_http_dependency_probe(monkeypatch)
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


def test_health_endpoint_exposes_agent_http_config_and_backend_mode(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    stub_http_dependency_probe(monkeypatch)
    agent_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
        agent_endpoint="https://example.test/agent",
        agent_http_enabled=True,
        agent_provider="atlas_json_http",
        agent_model_version="lfm2.5-1.2b-instruct",
    )
    agent_response = agent_client.get("/health")

    assert agent_response.status_code == 200
    assert agent_response.json()["agent_backend"]["status"] == "ready"
    assert agent_response.json()["agent_backend"]["detail"] == (
        "lfm2.5-1.2b-instruct (atlas_json_http http planner)"
    )
    assert agent_response.json()["config"]["agent_model_version"] == "lfm2.5-1.2b-instruct"
    assert agent_response.json()["config"]["agent_http_enabled"] is True
    assert agent_response.json()["config"]["agent_provider"] == "atlas_json_http"
    get_settings.cache_clear()


def test_health_endpoint_marks_unreachable_http_planner_degraded(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    agent_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
        agent_endpoint="http://127.0.0.1:9/v1/chat/completions",
        agent_http_enabled=True,
        agent_provider="openai_chat_completions_http",
    )
    agent_response = agent_client.get("/health")

    assert agent_response.status_code == 200
    assert agent_response.json()["agent_backend"]["status"] == "degraded"
    assert "configured but unreachable" in agent_response.json()["agent_backend"]["detail"]
    get_settings.cache_clear()


def test_health_endpoint_exposes_sam3_http_config_and_backend_mode(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    stub_http_dependency_probe(monkeypatch)
    sam3_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
        sam3_endpoint="https://example.test/sam3",
        sam3_http_enabled=True,
    )
    sam3_response = sam3_client.get("/health")

    assert sam3_response.status_code == 200
    assert sam3_response.json()["sam3_backend"]["status"] == "ready"
    assert sam3_response.json()["sam3_backend"]["detail"] == (
        "facebook/sam3 (sam3_http segmentation)"
    )
    assert sam3_response.json()["config"]["sam3_model_version"] == "facebook/sam3"
    assert sam3_response.json()["config"]["sam3_http_enabled"] is True
    get_settings.cache_clear()


def test_health_endpoint_marks_missing_sam3_endpoint_not_configured(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    sam3_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
        sam3_http_enabled=True,
    )
    sam3_response = sam3_client.get("/health")

    assert sam3_response.status_code == 200
    assert sam3_response.json()["sam3_backend"]["status"] == "degraded"
    assert (
        "real SAM3 HTTP segmentation is required" in sam3_response.json()["sam3_backend"]["detail"]
    )
    assert sam3_response.json()["config"]["sam3_http_enabled"] is True
    assert sam3_response.json()["config"]["sam3_required"] is True
    get_settings.cache_clear()


def test_health_endpoint_allows_explicit_offline_sam3_fixture_mode(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    sam3_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
        sam3_http_enabled=False,
        sam3_required=False,
    )
    sam3_response = sam3_client.get("/health")

    assert sam3_response.status_code == 200
    assert sam3_response.json()["sam3_backend"]["status"] == "ready"
    assert "reference-only fixture" in sam3_response.json()["sam3_backend"]["detail"]
    assert sam3_response.json()["config"]["sam3_http_enabled"] is False
    assert sam3_response.json()["config"]["sam3_required"] is False
    get_settings.cache_clear()


def test_health_endpoint_marks_missing_agent_endpoint_not_configured(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    agent_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
        agent_http_enabled=True,
        agent_provider="atlas_json_http",
    )
    agent_response = agent_client.get("/health")

    assert agent_response.status_code == 200
    assert agent_response.json()["agent_backend"]["status"] == "not_configured"
    assert agent_response.json()["agent_backend"]["detail"] == (
        "agent planner endpoint not configured yet"
    )
    assert agent_response.json()["config"]["agent_http_enabled"] is True
    get_settings.cache_clear()


def test_health_endpoint_exposes_openai_chat_planner_backend_mode(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    stub_http_dependency_probe(monkeypatch)
    agent_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
        agent_endpoint="https://liquid.example/v1/chat/completions",
        agent_http_enabled=True,
        agent_provider="openai_chat_completions_http",
    )
    agent_response = agent_client.get("/health")

    assert agent_response.status_code == 200
    assert agent_response.json()["agent_backend"]["status"] == "ready"
    assert agent_response.json()["agent_backend"]["detail"] == (
        "lfm2.5-1.2b-instruct (openai_chat_completions_http http planner)"
    )
    assert agent_response.json()["config"]["agent_provider"] == "openai_chat_completions_http"
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
    stub_http_dependency_probe(monkeypatch)
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


def test_health_endpoint_exposes_openai_chat_candidate_backend_mode(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    stub_http_dependency_probe(monkeypatch)
    model_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
        model_endpoint="https://liquid.example/v1/chat/completions",
        model_http_enabled=True,
        model_provider="openai_chat_completions_http",
    )
    model_response = model_client.get("/health")

    assert model_response.status_code == 200
    assert model_response.json()["model_backend"]["status"] == "ready"
    assert model_response.json()["model_backend"]["detail"] == (
        "lfm2.5-vl-450m-prompted (openai_chat_completions_http http backend)"
    )
    assert model_response.json()["config"]["model_provider"] == "openai_chat_completions_http"
    assert model_response.json()["debug"] is None
    get_settings.cache_clear()


def test_health_endpoint_exposes_gateway_debug_after_model_and_agent_calls(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        _ = timeout
        if request.full_url == "https://liquid.example/v1/chat/completions":
            return _FakeHTTPResponse(
                body=json.dumps(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": (
                                        '{"event_type":"probable_large_scale_disruption","severity":"high",'
                                        '"confidence":0.9,"bbox":[0.19,0.26,0.73,0.84],'
                                        '"civilian_impact":"shipping_or_aid_disruption",'
                                        '"why":"Gateway model lane ok.","action":"downlink_now"}'
                                    )
                                }
                            }
                        ]
                    }
                ).encode("utf-8")
            )
        if request.full_url == "https://agent.example/v1/chat/completions":
            return _FakeHTTPResponse(
                body=json.dumps(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(
                                        {
                                            "tool": "latest_alerts",
                                            "area": "Black Sea",
                                            "category": None,
                                            "site_id": None,
                                            "alert_id": None,
                                        }
                                    )
                                }
                            }
                        ]
                    }
                ).encode("utf-8")
            )
        raise AssertionError(f"unexpected url: {request.full_url}")

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    api_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
        model_endpoint="https://liquid.example/v1/chat/completions",
        model_http_enabled=True,
        model_provider="openai_chat_completions_http",
        agent_endpoint="https://agent.example/v1/chat/completions",
        agent_http_enabled=True,
        agent_provider="openai_chat_completions_http",
    )

    alerts = api_client.get("/alerts")
    agent = api_client.post("/agent/query", json={"query": "show latest alerts"})
    health = api_client.get("/health")

    assert alerts.status_code == 200
    assert agent.status_code == 200
    assert health.status_code == 200
    assert health.json()["debug"]["model_recent"]["provider_id"] == "openai_chat_completions_http"
    assert health.json()["debug"]["model_recent"]["parse_ok"] is True
    assert health.json()["debug"]["agent_recent"]["provider_id"] == "openai_chat_completions_http"
    assert health.json()["debug"]["agent_recent"]["parse_ok"] is True
    assert health.json()["debug"]["model_recent"]["seen_at"]
    assert health.json()["debug"]["agent_recent"]["seen_at"]
    get_settings.cache_clear()


def test_assets_endpoint_returns_seeded_assets() -> None:
    response = client.get("/assets")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 19
    assert payload[0]["asset_id"] == "demo_port_01"
    asset_ids = {item["asset_id"] for item in payload}
    assert {
        "beirut_port_01",
        "port_sudan_01",
        "ras_abu_jarjur_01",
        "bahri_water_01",
        "arbaat_dam_01",
        "silpo_kvitneve_01",
        "unhcr_baghdad_01",
        "mosul_medical_city_01",
        "gedaref_silos_01",
        "manbij_silos_01",
        "okhmatdyt_01",
        "roshen_yahotyn_01",
        "trostianets_hospital_01",
        "kramatorsk_filtration_01",
        "kakhovka_dam_01",
        "mansour_dam_01",
        "mondelez_trostianets_01",
        "morandi_bridge_01",
    } <= asset_ids


def test_leads_endpoint_returns_seeded_lead_registry() -> None:
    response = client.get("/leads")

    assert response.status_code == 200
    payload = response.json()
    lead_ids = {item["lead_id"] for item in payload}
    assert {
        "lead_mansour_dam_202309",
        "lead_kakhovka_dam_202306",
        "lead_okhmatdyt_202407",
        "lead_kytc_202403",
        "lead_qasmiyeh_bridge_202604",
        "lead_nasser_medical_complex_202506",
        "lead_al_ahli_arab_hospital_202505",
        "lead_bahri_water_station_202502",
    } <= lead_ids


def test_lead_refresh_endpoint_updates_runtime_registry(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_refresh_lead_registry(**kwargs):
        assert kwargs["source_mode"] == "gdelt"
        assert kwargs["output_path"] == "var/live_leads.json"
        assert kwargs["gdelt_limit"] == 12
        return (
            [
                Lead(
                    lead_id="gdelt_api_1",
                    title="Dnipro armed conflict",
                    region="Dnipro, Ukraine",
                    latitude=48.4647,
                    longitude=35.0462,
                    category_guess="civilian_building_cluster",
                    status="lead_only",
                    source_date="2026-04-28",
                )
            ],
            3,
        )

    monkeypatch.setattr("app.services.stub.refresh_lead_registry", fake_refresh_lead_registry)
    refresh_client = build_api_client(
        monkeypatch,
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
    )

    response = refresh_client.post(
        "/leads/refresh",
        json={
            "source_mode": "gdelt",
            "hours": 2,
            "max_files": 4,
            "limit": 12,
            "min_articles": 1,
            "country_allowlist": "default",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["lead_count"] == 1
    assert payload["reachable_source_count"] == 3
    assert payload["leads"][0]["lead_id"] == "gdelt_api_1"
    assert refresh_client.get("/leads").json()[0]["lead_id"] == "gdelt_api_1"
    get_settings.cache_clear()


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
    assert current_frame.json()["frame"]["image_ref"] is not None
    assert current_frame.json()["accepted_for_alerting"] is True
    assert current_frame.json()["filter_reason"] == "accepted"
    assert current_frame.json()["overlay_ref"] is not None

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


def test_current_evidence_endpoint_returns_sam3_fixture_report() -> None:
    client.post("/replay/stop")

    response = client.get("/evidence/current")

    assert response.status_code == 200
    payload = response.json()
    assert payload["asset_id"] == "demo_port_01"
    assert payload["model_version"] == "facebook/sam3"
    assert payload["backend"] == "fixture"
    assert payload["decision"] == "segmentation_ready"
    assert payload["triage_action"] == "downlink_now"
    assert payload["masks"][0]["bbox_norm"] == [0.19, 0.26, 0.73, 0.84]
    assert payload["visual_evidence_tags"] == ["damaged_port_or_logistics_apron"]


def test_asset_evidence_endpoint_returns_reference_event_report() -> None:
    response = client.get("/evidence/assets/beirut_port_01")

    assert response.status_code == 200
    payload = response.json()
    assert payload["asset_id"] == "beirut_port_01"
    assert payload["decision"] == "segmentation_ready"
    assert payload["triage_action"] != "discard"
    assert payload["masks"]


def test_asset_evidence_endpoint_returns_null_for_unknown_asset() -> None:
    response = client.get("/evidence/assets/unknown_asset")

    assert response.status_code == 200
    assert response.json() is None


def test_replay_snapshot_returns_aligned_hero_payload() -> None:
    client.post("/replay/stop")

    snapshot = client.get("/replay/snapshot")

    assert snapshot.status_code == 200
    payload = snapshot.json()
    assert payload["replay"]["running"] is False
    assert payload["current_frame"]["frame"]["asset_id"] == "demo_port_01"
    assert payload["current_frame"]["baseline_frame_id"] == (
        payload["baseline_frame"]["frame"]["frame_id"]
    )
    assert payload["alerts"][0]["alert_id"] == "blk_00017"
    assert payload["alerts"][0]["source"]["current_frame_id"] == (
        payload["current_frame"]["frame"]["frame_id"]
    )
    assert payload["metrics"]["frames_scanned"] == 143
    assert payload["metrics"]["alerts_emitted"] == len(payload["alerts"]) + 4


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
    assert current_frame.json()["frame"]["image_ref"] is not None
    assert current_frame.json()["accepted_for_alerting"] is True
    assert current_frame.json()["filter_reason"] == "accepted"
    assert current_frame.json()["overlay_ref"] is not None

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


def test_replay_snapshot_returns_aligned_selected_asset_payload() -> None:
    start_response = client.post("/replay/start", json={"asset_id": "demo_bridge_01"})
    snapshot = client.get("/replay/snapshot")

    assert start_response.status_code == 200
    assert snapshot.status_code == 200
    payload = snapshot.json()
    assert payload["replay"]["running"] is True
    assert payload["replay"]["asset_id"] == "demo_bridge_01"
    assert payload["replay"]["scenario_id"] == "bridge_access_obstruction"
    assert payload["current_frame"]["frame"]["asset_id"] == "demo_bridge_01"
    assert payload["baseline_frame"]["frame"]["asset_id"] == "demo_bridge_01"
    assert payload["alerts"][0]["alert_id"] == "blk_00018"
    assert payload["alerts"][0]["source"]["baseline_frame_id"] == (
        payload["baseline_frame"]["frame"]["frame_id"]
    )
    assert payload["metrics"]["frames_scanned"] == 88
    assert payload["metrics"]["alerts_emitted"] == 2


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
    assert current_frame.json()["overlay_ref"] == ("fixtures/demo_bridge_01/overlay-2026-04-14.png")
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
    assert baseline_frame.json()["frame"]["image_ref"] == "live/demo_port_01/baseline.png"
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
    assert current_frame.json()["overlay_ref"] == ("fixtures/demo_bridge_01/overlay-2026-04-14.png")


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
    assert baseline_frame.json()["frame"]["image_ref"] == (
        "fixtures/demo_bridge_01/baseline-2025-10-12.png"
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
    assert current_frame.json()["frame"]["image_ref"] == "live/demo_bridge_01/current.png"
    assert current_frame.json()["overlay_ref"] == "live/demo_bridge_01/overlay.png"
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
    assert baseline_frame.json()["frame"]["image_ref"] == "live/demo_bridge_01/baseline.png"


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
    assert current_frame.json()["frame"]["image_ref"] == "live/demo_bridge_01/current.png"
    assert current_frame.json()["overlay_ref"] == "live/demo_bridge_01/overlay.png"
    assert baseline_frame.json()["frame"]["frame_id"] == "live_base_demo_bridge_01_20251014"
    assert baseline_frame.json()["frame"]["source"] == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=baseline"
    )
    assert baseline_frame.json()["frame"]["image_ref"] == "live/demo_bridge_01/baseline.png"
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
    assert current_frame.json()["overlay_ref"] == ("fixtures/demo_bridge_01/overlay-2026-04-14.png")
    assert baseline_frame.json()["frame"]["frame_id"] == "base_demo_bridge_01_20251012"
    assert baseline_frame.json()["frame"]["source"] == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=baseline"
    )
    assert baseline_frame.json()["frame"]["image_ref"] == (
        "fixtures/demo_bridge_01/baseline-2025-10-12.png"
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
    assert current_frame.json()["overlay_ref"] == ("fixtures/demo_bridge_01/overlay-2026-04-14.png")
    assert baseline_frame.json()["frame"]["frame_id"] == "base_demo_bridge_01_20251012"
    assert baseline_frame.json()["frame"]["source"] == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=baseline"
    )
    assert baseline_frame.json()["frame"]["image_ref"] == (
        "fixtures/demo_bridge_01/baseline-2025-10-12.png"
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

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
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

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
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
