from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from app.core.config import Settings
from app.schemas.asset import Asset
from app.services.frame_types import FrameRequest
from app.services.scenario_fixtures import build_stub_scenarios
from app.services.sentinel_client import (
    BaselineSentinelAdapter,
    ConfiguredSentinelEndpointSource,
    CurrentSentinelAdapter,
    FixtureSentinelPayloadTransport,
    FixtureSentinelSource,
    HttpSentinelPayloadTransport,
    SentinelRequestPlan,
)


def test_fixture_sentinel_source_serves_scenario_frames() -> None:
    source = FixtureSentinelSource(_scenarios())
    request = FrameRequest(asset_id="demo_bridge_01", scenario_id="bridge_access_obstruction")

    current = source.get_current_frame(request)
    baseline = source.get_baseline_frame(request)

    assert current.frame.frame_id == "cur_demo_bridge_01_20260414"
    assert current.overlay_ref == "fixtures/demo_bridge_01/overlay-2026-04-14.png"
    assert baseline.frame.frame_id == "base_demo_bridge_01_20251012"


def test_fixture_sentinel_payload_transport_returns_current_payload_for_plan() -> None:
    transport = FixtureSentinelPayloadTransport(_scenarios())
    plan = SentinelRequestPlan(
        endpoint="https://example.test/sentinel/current",
        params={
            "asset_id": "demo_bridge_01",
            "scenario_id": "bridge_access_obstruction",
            "mode": "current",
        },
    )

    payload = transport.fetch(plan)

    assert payload is not None
    assert payload["frame_id"] == "cur_demo_bridge_01_20260414"
    assert payload["asset_id"] == "demo_bridge_01"
    assert payload["captured_at"] == "2026-04-14T18:42:00Z"
    assert payload["image_ref"] == "fixtures/demo_bridge_01/current-2026-04-14.png"
    assert payload["baseline_frame_id"] == "base_demo_bridge_01_20251012"
    assert payload["overlay_ref"] == "fixtures/demo_bridge_01/overlay-2026-04-14.png"


@pytest.mark.parametrize(
    ("plan", "payload"),
    [
        (
            SentinelRequestPlan(
                endpoint="https://example.test/sentinel/current",
                params={
                    "asset_id": "demo_bridge_01",
                    "scenario_id": "bridge_access_obstruction",
                    "mode": "current",
                },
            ),
            {"frame_id": "live_cur_demo_bridge_01_20260415"},
        ),
        (
            SentinelRequestPlan(
                endpoint="https://example.test/sentinel/baseline",
                params={
                    "asset_id": "demo_bridge_01",
                    "scenario_id": "bridge_access_obstruction",
                    "mode": "baseline",
                },
            ),
            {"frame_id": "live_base_demo_bridge_01_20251012"},
        ),
    ],
)
def test_http_sentinel_payload_transport_returns_decoded_json(
    monkeypatch, plan: SentinelRequestPlan, payload: dict[str, object]
) -> None:
    captured: list[tuple[str, float]] = []

    def fake_urlopen(url: str, timeout: float):
        captured.append((url, timeout))
        return _FakeHTTPResponse(status=200, body=json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)
    transport = HttpSentinelPayloadTransport(timeout_seconds=7.5)

    result = transport.fetch(plan)

    assert result == payload
    assert captured == [(plan.url, 7.5)]


def test_http_sentinel_payload_transport_returns_none_for_invalid_response(monkeypatch) -> None:
    plan = SentinelRequestPlan(
        endpoint="https://example.test/sentinel/current",
        params={
            "asset_id": "demo_port_01",
            "scenario_id": "hero_port_disruption",
            "mode": "current",
        },
    )

    def fake_urlopen(url: str, timeout: float):
        assert url == plan.url
        assert timeout == 5.0
        return _FakeHTTPResponse(status=200, body=b"{not-json}")

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)
    transport = HttpSentinelPayloadTransport()

    assert transport.fetch(plan) is None


def test_http_sentinel_payload_transport_materializes_simsat_png(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan = SentinelRequestPlan(
        endpoint="http://localhost:9005/data/current/image/sentinel",
        params={
            "asset_id": "live_gdelt_1",
            "scenario_id": "live_lead_gdelt_1",
            "mode": "current",
            "lon": "36.230400",
            "lat": "49.993500",
            "return_type": "png",
        },
    )
    metadata = {
        "image_available": True,
        "source": "sentinel",
        "spectral_bands": ["red", "green", "blue"],
        "footprint": [],
        "size_km": 5.0,
        "cloud_cover": 0.18,
        "datetime": "2026-04-28T12:00:00Z",
        "timestamp": "2026-04-28T12:00:00Z",
    }

    def fake_urlopen(url: str, timeout: float):
        assert url == plan.url
        assert timeout == 5.0
        return _FakeHTTPResponse(
            status=200,
            body=b"png-bytes",
            headers={"sentinel_metadata": json.dumps(metadata)},
        )

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)
    transport = HttpSentinelPayloadTransport(output_dir=tmp_path / "frames")

    payload = transport.fetch(plan)

    assert payload is not None
    assert payload["asset_id"] == "live_gdelt_1"
    assert payload["captured_at"] == "2026-04-28T12:00:00Z"
    assert payload["cloud_cover"] == 0.18
    assert payload["filter_reason"] == "simsat_live_frame"
    assert Path(str(payload["image_ref"])).read_bytes() == b"png-bytes"


def test_configured_sentinel_source_builds_current_and_baseline_plans() -> None:
    source = ConfiguredSentinelEndpointSource(
        current_endpoint="https://example.test/sentinel/current/",
        baseline_endpoint="https://example.test/sentinel/baseline/",
    )
    request = FrameRequest(asset_id="demo_bridge_01", scenario_id="bridge_access_obstruction")

    current = source.build_current_plan(request)
    baseline = source.build_baseline_plan(request)

    assert current is not None
    assert baseline is not None
    assert current.endpoint == "https://example.test/sentinel/current"
    assert baseline.endpoint == "https://example.test/sentinel/baseline"
    assert current.url == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=current"
    )
    assert baseline.url == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=baseline"
    )


def test_configured_sentinel_source_builds_coordinate_simsat_plans() -> None:
    source = ConfiguredSentinelEndpointSource(
        current_endpoint="http://localhost:9005/data/current/image/sentinel/",
        baseline_endpoint="http://localhost:9005/data/image/sentinel/",
    )
    request = FrameRequest(
        asset_id="live_gdelt_1",
        scenario_id="live_lead_gdelt_1",
        latitude=49.9935,
        longitude=36.2304,
        requested_timestamp="2026-04-28T12:00:00Z",
        baseline_timestamp="2023-04-29T12:00:00Z",
    )

    current = source.build_current_plan(request)
    baseline = source.build_baseline_plan(request)

    assert current is not None
    assert baseline is not None
    assert current.url == (
        "http://localhost:9005/data/current/image/sentinel"
        "?asset_id=live_gdelt_1&scenario_id=live_lead_gdelt_1&mode=current"
        "&lon=36.230400&lat=49.993500&spectral_bands=red&spectral_bands=green"
        "&spectral_bands=blue&size_km=5.0&window_seconds=864000&return_type=png"
        "&timestamp=2026-04-28T12%3A00%3A00Z"
    )
    assert baseline.url == (
        "http://localhost:9005/data/image/sentinel"
        "?asset_id=live_gdelt_1&scenario_id=live_lead_gdelt_1&mode=baseline"
        "&lon=36.230400&lat=49.993500&spectral_bands=red&spectral_bands=green"
        "&spectral_bands=blue&size_km=5.0&window_seconds=864000&return_type=png"
        "&timestamp=2023-04-29T12%3A00%3A00Z"
    )


def test_configured_sentinel_source_returns_none_without_current_endpoint() -> None:
    source = ConfiguredSentinelEndpointSource(
        current_endpoint=None,
        baseline_endpoint="https://example.test/sentinel/baseline",
    )
    request = FrameRequest(asset_id="demo_port_01", scenario_id="hero_port_disruption")

    assert source.build_current_plan(request) is None


def test_configured_sentinel_source_returns_none_without_baseline_endpoint() -> None:
    source = ConfiguredSentinelEndpointSource(
        current_endpoint="https://example.test/sentinel/current",
        baseline_endpoint=None,
    )
    request = FrameRequest(asset_id="demo_port_01", scenario_id="hero_port_disruption")

    assert source.build_baseline_plan(request) is None


def test_configured_sentinel_source_maps_current_payload_into_frame_envelope() -> None:
    source = ConfiguredSentinelEndpointSource(
        current_endpoint="https://example.test/sentinel/current/",
        baseline_endpoint=None,
    )
    request = FrameRequest(asset_id="demo_bridge_01", scenario_id="bridge_access_obstruction")

    envelope = source.build_current_envelope(
        request,
        {
            "frame_id": "live_cur_demo_bridge_01_20260415",
            "captured_at": "2026-04-15T07:10:00Z",
            "image_ref": "live/demo_bridge_01/current.png",
            "cloud_cover": 0.12,
            "baseline_frame_id": "base_demo_bridge_01_20251012",
            "overlay_ref": "live/demo_bridge_01/overlay.png",
            "accepted_for_alerting": True,
            "filter_reason": "accepted",
        },
    )

    assert envelope.frame.frame_id == "live_cur_demo_bridge_01_20260415"
    assert envelope.frame.asset_id == "demo_bridge_01"
    assert envelope.frame.captured_at == "2026-04-15T07:10:00Z"
    assert envelope.frame.image_ref == "live/demo_bridge_01/current.png"
    assert envelope.frame.cloud_cover == 0.12
    assert envelope.frame.source == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=current"
    )
    assert envelope.baseline_frame_id == "base_demo_bridge_01_20251012"
    assert envelope.overlay_ref == "live/demo_bridge_01/overlay.png"
    assert envelope.accepted_for_alerting is True
    assert envelope.filter_reason == "accepted"


def test_configured_sentinel_source_maps_baseline_payload_into_frame_envelope() -> None:
    source = ConfiguredSentinelEndpointSource(
        current_endpoint=None,
        baseline_endpoint="https://example.test/sentinel/baseline/",
    )
    request = FrameRequest(asset_id="demo_port_01", scenario_id="hero_port_disruption")

    envelope = source.build_baseline_envelope(
        request,
        {
            "frame_id": "live_base_demo_port_01_20250901",
            "asset_id": "demo_port_01",
            "captured_at": "2025-09-01T10:00:00Z",
            "image_ref": "live/demo_port_01/baseline.png",
            "cloud_cover": 0,
        },
    )

    assert envelope.frame.frame_id == "live_base_demo_port_01_20250901"
    assert envelope.frame.asset_id == "demo_port_01"
    assert envelope.frame.captured_at == "2025-09-01T10:00:00Z"
    assert envelope.frame.image_ref == "live/demo_port_01/baseline.png"
    assert envelope.frame.cloud_cover == 0.0
    assert envelope.frame.source == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=baseline"
    )
    assert envelope.baseline_frame_id is None
    assert envelope.overlay_ref is None
    assert envelope.accepted_for_alerting is None
    assert envelope.filter_reason is None


def test_current_sentinel_adapter_uses_configured_plan_and_fixture_fallback() -> None:
    adapter = CurrentSentinelAdapter(
        planner=ConfiguredSentinelEndpointSource(
            current_endpoint="https://example.test/sentinel/current/",
            baseline_endpoint=None,
        ),
        fallback=FixtureSentinelSource(_scenarios()),
    )
    request = FrameRequest(asset_id="demo_port_01", scenario_id="hero_port_disruption")

    current = adapter.get_current_frame(request)
    baseline = adapter.get_baseline_frame(request)

    assert current.frame.frame_id == "cur_demo_port_01_20260414"
    assert current.frame.source == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=current"
    )
    assert baseline.frame.frame_id == "base_demo_port_01_20250901"
    assert baseline.frame.source == "sentinel_baseline_stub"


def test_current_sentinel_adapter_returns_fixture_frame_without_current_endpoint() -> None:
    adapter = CurrentSentinelAdapter(
        planner=ConfiguredSentinelEndpointSource(
            current_endpoint=None,
            baseline_endpoint=None,
        ),
        fallback=FixtureSentinelSource(_scenarios()),
    )
    request = FrameRequest(asset_id="demo_bridge_01", scenario_id="bridge_access_obstruction")

    current = adapter.get_current_frame(request)

    assert current.frame.frame_id == "cur_demo_bridge_01_20260414"
    assert current.frame.source == "sentinel_current_stub"


def test_current_sentinel_adapter_uses_transport_payload_when_available() -> None:
    transport = _FakeTransport(
        payload={
            "frame_id": "live_cur_demo_port_01_20260415",
            "captured_at": "2026-04-15T07:10:00Z",
            "image_ref": "live/demo_port_01/current.png",
            "cloud_cover": 0.11,
            "baseline_frame_id": "base_demo_port_01_20250901",
            "overlay_ref": "live/demo_port_01/overlay.png",
            "accepted_for_alerting": True,
            "filter_reason": "accepted",
        }
    )
    adapter = CurrentSentinelAdapter(
        planner=ConfiguredSentinelEndpointSource(
            current_endpoint="https://example.test/sentinel/current/",
            baseline_endpoint=None,
        ),
        fallback=FixtureSentinelSource(_scenarios()),
        transport=transport,
    )
    request = FrameRequest(asset_id="demo_port_01", scenario_id="hero_port_disruption")

    current = adapter.get_current_frame(request)
    baseline = adapter.get_baseline_frame(request)

    assert len(transport.plans) == 1
    assert transport.plans[0].url == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=current"
    )
    assert current.frame.frame_id == "live_cur_demo_port_01_20260415"
    assert current.frame.asset_id == "demo_port_01"
    assert current.frame.source == transport.plans[0].url
    assert current.baseline_frame_id == "base_demo_port_01_20250901"
    assert current.overlay_ref == "live/demo_port_01/overlay.png"
    assert current.accepted_for_alerting is True
    assert current.filter_reason == "accepted"
    assert baseline.frame.frame_id == "base_demo_port_01_20250901"


def test_current_sentinel_adapter_falls_back_when_transport_returns_none() -> None:
    transport = _FakeTransport(payload=None)
    adapter = CurrentSentinelAdapter(
        planner=ConfiguredSentinelEndpointSource(
            current_endpoint="https://example.test/sentinel/current/",
            baseline_endpoint=None,
        ),
        fallback=FixtureSentinelSource(_scenarios()),
        transport=transport,
    )
    request = FrameRequest(asset_id="demo_bridge_01", scenario_id="bridge_access_obstruction")

    current = adapter.get_current_frame(request)

    assert len(transport.plans) == 1
    assert current.frame.frame_id == "cur_demo_bridge_01_20260414"
    assert current.frame.source == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=current"
    )


def test_current_sentinel_adapter_falls_back_when_transport_payload_is_malformed() -> None:
    transport = _FakeTransport(
        payload={
            "captured_at": "2026-04-15T07:10:00Z",
            "image_ref": "live/demo_bridge_01/current.png",
        }
    )
    adapter = CurrentSentinelAdapter(
        planner=ConfiguredSentinelEndpointSource(
            current_endpoint="https://example.test/sentinel/current/",
            baseline_endpoint=None,
        ),
        fallback=FixtureSentinelSource(_scenarios()),
        transport=transport,
    )
    request = FrameRequest(asset_id="demo_bridge_01", scenario_id="bridge_access_obstruction")

    current = adapter.get_current_frame(request)

    assert len(transport.plans) == 1
    assert current.frame.frame_id == "cur_demo_bridge_01_20260414"
    assert current.frame.source == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=current"
    )


def test_baseline_sentinel_adapter_uses_configured_plan_and_fixture_fallback() -> None:
    adapter = BaselineSentinelAdapter(
        planner=ConfiguredSentinelEndpointSource(
            current_endpoint=None,
            baseline_endpoint="https://example.test/sentinel/baseline/",
        ),
        fallback=FixtureSentinelSource(_scenarios()),
    )
    request = FrameRequest(asset_id="demo_bridge_01", scenario_id="bridge_access_obstruction")

    current = adapter.get_current_frame(request)
    baseline = adapter.get_baseline_frame(request)

    assert current.frame.frame_id == "cur_demo_bridge_01_20260414"
    assert current.frame.source == "sentinel_current_stub"
    assert baseline.frame.frame_id == "base_demo_bridge_01_20251012"
    assert baseline.frame.source == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=baseline"
    )


def test_baseline_sentinel_adapter_returns_fixture_frame_without_baseline_endpoint() -> None:
    adapter = BaselineSentinelAdapter(
        planner=ConfiguredSentinelEndpointSource(
            current_endpoint=None,
            baseline_endpoint=None,
        ),
        fallback=FixtureSentinelSource(_scenarios()),
    )
    request = FrameRequest(asset_id="demo_port_01", scenario_id="hero_port_disruption")

    baseline = adapter.get_baseline_frame(request)

    assert baseline.frame.frame_id == "base_demo_port_01_20250901"
    assert baseline.frame.source == "sentinel_baseline_stub"


def test_baseline_sentinel_adapter_uses_transport_payload_when_available() -> None:
    transport = _FakeTransport(
        payload={
            "frame_id": "live_base_demo_bridge_01_20251012",
            "captured_at": "2025-10-12T09:15:00Z",
            "image_ref": "live/demo_bridge_01/baseline.png",
            "cloud_cover": 0.02,
        }
    )
    adapter = BaselineSentinelAdapter(
        planner=ConfiguredSentinelEndpointSource(
            current_endpoint=None,
            baseline_endpoint="https://example.test/sentinel/baseline/",
        ),
        fallback=FixtureSentinelSource(_scenarios()),
        transport=transport,
    )
    request = FrameRequest(asset_id="demo_bridge_01", scenario_id="bridge_access_obstruction")

    current = adapter.get_current_frame(request)
    baseline = adapter.get_baseline_frame(request)

    assert len(transport.plans) == 1
    assert transport.plans[0].url == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=baseline"
    )
    assert current.frame.frame_id == "cur_demo_bridge_01_20260414"
    assert baseline.frame.frame_id == "live_base_demo_bridge_01_20251012"
    assert baseline.frame.asset_id == "demo_bridge_01"
    assert baseline.frame.source == transport.plans[0].url
    assert baseline.frame.image_ref == "live/demo_bridge_01/baseline.png"
    assert baseline.frame.cloud_cover == 0.02


def test_baseline_sentinel_adapter_falls_back_when_transport_returns_none() -> None:
    transport = _FakeTransport(payload=None)
    adapter = BaselineSentinelAdapter(
        planner=ConfiguredSentinelEndpointSource(
            current_endpoint=None,
            baseline_endpoint="https://example.test/sentinel/baseline/",
        ),
        fallback=FixtureSentinelSource(_scenarios()),
        transport=transport,
    )
    request = FrameRequest(asset_id="demo_port_01", scenario_id="hero_port_disruption")

    baseline = adapter.get_baseline_frame(request)

    assert len(transport.plans) == 1
    assert baseline.frame.frame_id == "base_demo_port_01_20250901"
    assert baseline.frame.source == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=baseline"
    )


def test_baseline_sentinel_adapter_falls_back_when_transport_payload_is_malformed() -> None:
    transport = _FakeTransport(
        payload={
            "captured_at": "2025-10-12T09:15:00Z",
            "image_ref": "live/demo_bridge_01/baseline.png",
        }
    )
    adapter = BaselineSentinelAdapter(
        planner=ConfiguredSentinelEndpointSource(
            current_endpoint=None,
            baseline_endpoint="https://example.test/sentinel/baseline/",
        ),
        fallback=FixtureSentinelSource(_scenarios()),
        transport=transport,
    )
    request = FrameRequest(asset_id="demo_bridge_01", scenario_id="bridge_access_obstruction")

    baseline = adapter.get_baseline_frame(request)

    assert len(transport.plans) == 1
    assert baseline.frame.frame_id == "base_demo_bridge_01_20251012"
    assert baseline.frame.source == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=baseline"
    )


def _scenarios():
    settings = Settings(
        app_env="test",
        app_port=8000,
        model_version="lfm2.5-vl-450m-prompted",
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
        mapbox_token_present=False,
        watchlist_path=None,
    )
    hero_asset = Asset(
        asset_id="demo_port_01",
        asset_name="Demo Grain Port",
        asset_type="grain_port",
        region="Black Sea",
        latitude=46.501,
        longitude=30.747,
        hero=True,
    )
    bridge_asset = Asset(
        asset_id="demo_bridge_01",
        asset_name="Demo Logistics Bridge",
        asset_type="bridge",
        region="Lower Danube",
        latitude=45.169,
        longitude=28.801,
    )
    return build_stub_scenarios(
        settings=settings,
        hero_asset=hero_asset,
        bridge_asset=bridge_asset,
    )


@dataclass
class _FakeTransport:
    payload: dict[str, object] | None
    plans: list[SentinelRequestPlan] = field(default_factory=list)

    def fetch(self, plan: SentinelRequestPlan) -> dict[str, object] | None:
        self.plans.append(plan)
        return self.payload


class _FakeHTTPResponse:
    def __init__(
        self,
        *,
        status: int,
        body: bytes,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self._body = body
        self.headers = headers or {}

    def __enter__(self) -> _FakeHTTPResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self.status
