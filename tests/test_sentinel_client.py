from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import Settings
from app.schemas.asset import Asset
from app.services.frame_types import FrameRequest
from app.services.scenario_fixtures import build_stub_scenarios
from app.services.sentinel_client import (
    BaselineSentinelAdapter,
    ConfiguredSentinelEndpointSource,
    CurrentSentinelAdapter,
    FixtureSentinelSource,
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
