from __future__ import annotations

from app.core.config import Settings
from app.schemas.asset import Asset
from app.services.frame_types import FrameRequest
from app.services.scenario_fixtures import build_stub_scenarios
from app.services.sentinel_client import ConfiguredSentinelEndpointSource, FixtureSentinelSource


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
        current_endpoint="https://example.test/sentinel/current",
        baseline_endpoint="https://example.test/sentinel/baseline",
    )
    request = FrameRequest(asset_id="demo_bridge_01", scenario_id="bridge_access_obstruction")

    current = source.build_current_plan(request)
    baseline = source.build_baseline_plan(request)

    assert current.url == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=current"
    )
    assert baseline.url == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=baseline"
    )


def test_configured_sentinel_source_requires_configured_endpoint() -> None:
    source = ConfiguredSentinelEndpointSource(
        current_endpoint=None,
        baseline_endpoint="https://example.test/sentinel/baseline",
    )
    request = FrameRequest(asset_id="demo_port_01", scenario_id="hero_port_disruption")

    try:
        source.build_current_plan(request)
    except ValueError as exc:
        assert str(exc) == "current Sentinel endpoint is not configured"
    else:
        raise AssertionError("expected build_current_plan to require a configured endpoint")


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
