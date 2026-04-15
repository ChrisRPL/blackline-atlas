from __future__ import annotations

import json
from pathlib import Path

from app.core.config import Settings
from app.services.frame_filters import FrameFilterPolicy
from app.services.stub import StubAtlasService


def test_stub_service_marks_cloudy_frame_as_suppressed() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )
    service.frame_filter_policy = FrameFilterPolicy(cloud_cover_threshold=0.01)

    frame = service.get_current_frame()
    metrics = service.get_metrics()
    alerts = service.list_alerts()

    assert frame.accepted_for_alerting is False
    assert frame.filter_reason == "cloud_cover_too_high"
    assert frame.overlay_ref is None
    assert metrics.alerts_emitted == 4
    assert metrics.raw_frames_suppressed == 139
    assert metrics.downlink_rate == 0.028
    assert alerts == []


def test_stub_service_keeps_fixture_only_frames_without_sentinel_endpoints(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    current = service.get_current_frame()
    baseline = service.get_baseline_frame()

    assert current.frame.source == "sentinel_current_stub"
    assert baseline.frame.source == "sentinel_baseline_stub"


def test_stub_service_composes_sentinel_adapters_when_endpoints_are_configured(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="https://example.test/sentinel/current/",
            simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    current = service.get_current_frame()
    baseline = service.get_baseline_frame()

    assert current.frame.source == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=current"
    )
    assert baseline.frame.source == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=baseline"
    )
    assert current.frame.image_ref is not None
    assert baseline.frame.image_ref is not None
    assert tmp_path.joinpath(
        ".cache",
        "frames",
        "demo_port_01",
        "hero_port_disruption",
        "current",
        "cur_demo_port_01_20260414",
        "metadata.json",
    ).exists()
    assert tmp_path.joinpath(
        ".cache",
        "frames",
        "demo_port_01",
        "hero_port_disruption",
        "baseline",
        "base_demo_port_01_20250901",
        "metadata.json",
    ).exists()


def test_stub_service_uses_current_adapter_and_fixture_baseline_with_current_only_endpoint(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="https://example.test/sentinel/current/",
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    current = service.get_current_frame()
    baseline = service.get_baseline_frame()

    assert current.frame.source == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=current"
    )
    assert baseline.frame.source == "sentinel_baseline_stub"
    assert current.frame.image_ref is not None
    assert baseline.frame.image_ref is not None


def test_stub_service_uses_baseline_adapter_and_fixture_current_with_baseline_only_endpoint(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    current = service.get_current_frame()
    baseline = service.get_baseline_frame()

    assert current.frame.source == "sentinel_current_stub"
    assert baseline.frame.source == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=baseline"
    )
    assert current.frame.image_ref is not None
    assert baseline.frame.image_ref is not None


def test_stub_service_loads_assets_from_watchlist_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "watchlist.json"
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "asset_id": "demo_port_01",
                    "asset_name": "Manifest Grain Port",
                    "asset_type": "grain_port",
                    "region": "Manifest Coast",
                    "latitude": 46.501,
                    "longitude": 30.747,
                    "hero": True,
                },
                {
                    "asset_id": "demo_bridge_01",
                    "asset_name": "Manifest Logistics Bridge",
                    "asset_type": "bridge",
                    "region": "Manifest Danube",
                    "latitude": 45.169,
                    "longitude": 28.801,
                    "hero": False,
                },
            ]
        ),
        encoding="utf-8",
    )
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=str(manifest_path),
        )
    )

    assets = service.list_assets()

    assert [asset.asset_id for asset in assets] == ["demo_port_01", "demo_bridge_01"]
    assert assets[0].asset_name == "Manifest Grain Port"
    assert service.hero_asset.asset_name == "Manifest Grain Port"
