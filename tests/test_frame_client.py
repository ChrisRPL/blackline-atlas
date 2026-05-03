from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from app.core.config import Settings
from app.schemas.asset import Asset
from app.schemas.frame import FrameEnvelope, FrameRecord
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

    assert envelope.frame.image_ref == "fixtures/demo_port_01/current-2026-04-14.png"
    assert envelope.overlay_ref == "fixtures/demo_port_01/overlay-2026-04-14.png"
    assert tmp_path.joinpath(
        "demo_port_01",
        "hero_port_disruption",
        "current",
        "cur_demo_port_01_20260414",
        "metadata.json",
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
    cached_image = metadata_path.parent / "image.png"
    cached_image.write_bytes(b"cached-bytes")
    original = metadata_path.read_text(encoding="utf-8")
    metadata_path.write_text(
        original.replace("base_demo_bridge_01_20251012", "base_demo_bridge_01_cached").replace(
            "fixtures/demo_bridge_01/baseline-2025-10-12.png",
            str(cached_image),
        ),
        encoding="utf-8",
    )

    second = client.get_baseline_frame(request)

    assert first.frame.image_ref is not None
    assert second.frame.frame_id == "base_demo_bridge_01_cached"


def test_cached_frame_client_uses_request_alias_before_delegate(tmp_path) -> None:
    source_image = tmp_path / "source.png"
    source_image.write_bytes(b"frame-bytes")
    delegate = _CountingFrameClient(
        FrameEnvelope(
            frame=FrameRecord(
                frame_id="cur-live-001",
                asset_id="live_asset",
                captured_at="2026-04-30T12:00:00Z",
                image_ref=str(source_image),
                source="simsat",
            )
        )
    )
    client = CachedFrameClient(
        delegate=delegate,
        cache_layout=FrameCacheLayout(tmp_path / "cache"),
    )
    request = FrameRequest(
        asset_id="live_asset",
        scenario_id="live_lead_001",
        latitude=50.45,
        longitude=30.52,
        requested_timestamp="2026-04-30T12:00:00Z",
    )

    first = client.get_current_frame(request)
    second = client.get_current_frame(request)

    assert delegate.current_calls == 1
    assert first.frame.frame_id == "cur-live-001"
    assert second.frame.frame_id == "cur-live-001"
    assert second.frame.image_ref is not None
    assert Path(second.frame.image_ref).read_bytes() == b"frame-bytes"


def test_cached_frame_client_scopes_request_aliases_by_namespace(tmp_path) -> None:
    live_image = tmp_path / "live.png"
    fixture_image = tmp_path / "fixture.png"
    live_image.write_bytes(b"live-frame")
    fixture_image.write_bytes(b"fixture-frame")
    live_delegate = _CountingFrameClient(
        FrameEnvelope(
            frame=FrameRecord(
                frame_id="cur-live-001",
                asset_id="shared_asset",
                captured_at="2026-04-30T12:00:00Z",
                image_ref=str(live_image),
                source="simsat",
            )
        )
    )
    fixture_delegate = _CountingFrameClient(
        FrameEnvelope(
            frame=FrameRecord(
                frame_id="cur-fixture-001",
                asset_id="shared_asset",
                captured_at="2026-04-30T12:00:00Z",
                image_ref=str(fixture_image),
                source="fixture",
            )
        )
    )
    cache_layout = FrameCacheLayout(tmp_path / "cache")
    request = FrameRequest(
        asset_id="shared_asset",
        scenario_id="shared_scenario",
        latitude=50.45,
        longitude=30.52,
        requested_timestamp="2026-04-30T12:00:00Z",
    )
    live_client = CachedFrameClient(
        delegate=live_delegate,
        cache_layout=cache_layout,
        cache_namespace="simsat-live",
    )
    fixture_client = CachedFrameClient(
        delegate=fixture_delegate,
        cache_layout=cache_layout,
        cache_namespace="fixture",
    )

    assert live_client.get_current_frame(request).frame.frame_id == "cur-live-001"
    assert fixture_client.get_current_frame(request).frame.frame_id == "cur-fixture-001"
    assert live_client.get_current_frame(request).frame.frame_id == "cur-live-001"
    assert fixture_client.get_current_frame(request).frame.frame_id == "cur-fixture-001"
    assert live_delegate.current_calls == 1
    assert fixture_delegate.current_calls == 1


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
    assert envelope.frame.image_ref == "fixtures/demo_bridge_01/baseline-2025-10-12.png"
    assert tmp_path.joinpath(
        "demo_bridge_01",
        "bridge_access_obstruction",
        "baseline",
        "base_demo_bridge_01_20251012",
        "metadata.json",
    ).exists()


def test_cached_frame_client_copies_real_frame_bytes_into_cache(tmp_path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    current_image = source_dir / "current.png"
    overlay_image = source_dir / "overlay.png"
    baseline_image = source_dir / "baseline.png"
    current_image.write_bytes(b"current-bytes")
    overlay_image.write_bytes(b"overlay-bytes")
    baseline_image.write_bytes(b"baseline-bytes")

    scenarios = _scenarios()
    scenario = scenarios["hero_port_disruption"]
    scenarios["hero_port_disruption"] = replace(
        scenario,
        current_frame=scenario.current_frame.model_copy(
            update={
                "frame": scenario.current_frame.frame.model_copy(
                    update={"image_ref": str(current_image)}
                ),
                "overlay_ref": str(overlay_image),
            }
        ),
        baseline_frame=scenario.baseline_frame.model_copy(
            update={
                "frame": scenario.baseline_frame.frame.model_copy(
                    update={"image_ref": str(baseline_image)}
                )
            }
        ),
    )
    client = CachedFrameClient(
        delegate=FixtureFrameClient(scenarios),
        cache_layout=FrameCacheLayout(tmp_path / "cache"),
    )
    request = FrameRequest(asset_id="demo_port_01", scenario_id="hero_port_disruption")

    current = client.get_current_frame(request)
    baseline = client.get_baseline_frame(request)

    assert current.frame.image_ref is not None
    assert baseline.frame.image_ref is not None
    assert current.overlay_ref is not None
    assert Path(current.frame.image_ref).read_bytes() == b"current-bytes"
    assert Path(current.overlay_ref).read_bytes() == b"overlay-bytes"
    assert Path(baseline.frame.image_ref).read_bytes() == b"baseline-bytes"


def test_cached_frame_client_refreshes_zero_byte_cached_refs(tmp_path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    current_image = source_dir / "current.png"
    current_image.write_bytes(b"fresh-bytes")

    scenarios = _scenarios()
    scenario = scenarios["hero_port_disruption"]
    scenarios["hero_port_disruption"] = replace(
        scenario,
        current_frame=scenario.current_frame.model_copy(
            update={
                "frame": scenario.current_frame.frame.model_copy(
                    update={"image_ref": str(current_image)}
                ),
                "overlay_ref": None,
            }
        ),
    )
    cache_root = tmp_path / "cache"
    client = CachedFrameClient(
        delegate=FixtureFrameClient(scenarios),
        cache_layout=FrameCacheLayout(cache_root),
    )
    request = FrameRequest(asset_id="demo_port_01", scenario_id="hero_port_disruption")

    stale_dir = (
        cache_root
        / "demo_port_01"
        / "hero_port_disruption"
        / "current"
        / "cur_demo_port_01_20260414"
    )
    stale_dir.mkdir(parents=True)
    stale_image = stale_dir / "image.png"
    stale_image.write_bytes(b"")
    stale_metadata = stale_dir / "metadata.json"
    stale_metadata.write_text(
        scenario.current_frame.model_copy(
            update={
                "frame": scenario.current_frame.frame.model_copy(
                    update={"image_ref": str(stale_image)}
                ),
                "overlay_ref": None,
            }
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )

    refreshed = client.get_current_frame(request)

    assert refreshed.frame.image_ref is not None
    assert Path(refreshed.frame.image_ref).read_bytes() == b"fresh-bytes"


def test_cached_frame_client_refreshes_invalid_cached_metadata(tmp_path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    current_image = source_dir / "current.png"
    current_image.write_bytes(b"fresh-bytes")

    scenarios = _scenarios()
    scenario = scenarios["hero_port_disruption"]
    scenarios["hero_port_disruption"] = replace(
        scenario,
        current_frame=scenario.current_frame.model_copy(
            update={
                "frame": scenario.current_frame.frame.model_copy(
                    update={"image_ref": str(current_image)}
                ),
                "overlay_ref": None,
            }
        ),
    )
    cache_root = tmp_path / "cache"
    client = CachedFrameClient(
        delegate=FixtureFrameClient(scenarios),
        cache_layout=FrameCacheLayout(cache_root),
    )
    request = FrameRequest(asset_id="demo_port_01", scenario_id="hero_port_disruption")

    stale_dir = (
        cache_root
        / "demo_port_01"
        / "hero_port_disruption"
        / "current"
        / "cur_demo_port_01_20260414"
    )
    stale_dir.mkdir(parents=True)
    stale_metadata = stale_dir / "metadata.json"
    stale_metadata.write_text("", encoding="utf-8")

    refreshed = client.get_current_frame(request)

    assert refreshed.frame.image_ref is not None
    assert Path(refreshed.frame.image_ref).read_bytes() == b"fresh-bytes"


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


class _CountingFrameClient:
    def __init__(self, current: FrameEnvelope) -> None:
        self.current = current
        self.current_calls = 0

    def get_current_frame(self, request: FrameRequest) -> FrameEnvelope:
        _ = request
        self.current_calls += 1
        if self.current_calls > 1:
            raise AssertionError("cache should satisfy repeated request before delegate")
        return self.current

    def get_baseline_frame(self, request: FrameRequest) -> FrameEnvelope:
        _ = request
        raise NotImplementedError
