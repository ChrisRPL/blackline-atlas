from __future__ import annotations

from app.core.config import Settings
from app.schemas.asset import Asset
from app.services.frame_cache import FrameCacheLayout
from app.services.frame_client import CachedFrameClient, FixtureFrameClient
from app.services.frame_types import FrameRequest
from app.services.scenario_fixtures import build_stub_scenarios
from app.services.sentinel_client import (
    BaselineSentinelAdapter,
    ConfiguredSentinelEndpointSource,
    FixtureSentinelSource,
)


def test_cached_frame_client_persists_current_frame_metadata_and_paths(tmp_path) -> None:
    client = CachedFrameClient(
        delegate=FixtureFrameClient(_scenarios()),
        cache_layout=FrameCacheLayout(tmp_path),
    )
    request = FrameRequest(asset_id="demo_port_01", scenario_id="hero_port_disruption")

    envelope = client.get_current_frame(request)

    assert envelope.frame.image_ref is not None
    assert envelope.overlay_ref is not None
    assert tmp_path.joinpath(
        "demo_port_01",
        "hero_port_disruption",
        "current",
        "cur_demo_port_01_20260414",
        "metadata.json",
    ).exists()
    assert tmp_path.joinpath(
        "demo_port_01",
        "hero_port_disruption",
        "current",
        "cur_demo_port_01_20260414",
        "image.png",
    ).exists()
    assert tmp_path.joinpath(
        "demo_port_01",
        "hero_port_disruption",
        "overlay",
        "cur_demo_port_01_20260414",
        "image.png",
    ).exists()


def test_cached_frame_client_reuses_cached_baseline_payload(tmp_path) -> None:
    client = CachedFrameClient(
        delegate=FixtureFrameClient(_scenarios()),
        cache_layout=FrameCacheLayout(tmp_path),
    )
    request = FrameRequest(asset_id="demo_bridge_01", scenario_id="bridge_access_obstruction")

    first = client.get_baseline_frame(request)
    metadata_path = tmp_path.joinpath(
        "demo_bridge_01",
        "bridge_access_obstruction",
        "baseline",
        "base_demo_bridge_01_20251012",
        "metadata.json",
    )
    original = metadata_path.read_text(encoding="utf-8")
    metadata_path.write_text(
        original.replace("base_demo_bridge_01_20251012", "base_demo_bridge_01_cached"),
        encoding="utf-8",
    )

    second = client.get_baseline_frame(request)

    assert first.frame.image_ref is not None
    assert second.frame.frame_id == "base_demo_bridge_01_cached"


def test_cached_frame_client_materializes_baseline_adapter_output(tmp_path) -> None:
    client = CachedFrameClient(
        delegate=BaselineSentinelAdapter(
            planner=ConfiguredSentinelEndpointSource(
                current_endpoint=None,
                baseline_endpoint="https://example.test/sentinel/baseline/",
            ),
            fallback=FixtureSentinelSource(_scenarios()),
        ),
        cache_layout=FrameCacheLayout(tmp_path),
    )
    request = FrameRequest(asset_id="demo_bridge_01", scenario_id="bridge_access_obstruction")

    envelope = client.get_baseline_frame(request)

    assert envelope.frame.source == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=baseline"
    )
    assert envelope.frame.image_ref is not None
    assert tmp_path.joinpath(
        "demo_bridge_01",
        "bridge_access_obstruction",
        "baseline",
        "base_demo_bridge_01_20251012",
        "metadata.json",
    ).exists()
    assert tmp_path.joinpath(
        "demo_bridge_01",
        "bridge_access_obstruction",
        "baseline",
        "base_demo_bridge_01_20251012",
        "image.png",
    ).exists()


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
