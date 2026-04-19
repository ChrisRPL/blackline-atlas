from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.schemas.asset import Asset
from app.services.scenario_fixtures import build_stub_scenarios
from training.scripts.run_candidate_backend_smoke import materialize_case_frames


def test_materialize_case_frames_replaces_pending_refs_with_capture_paths() -> None:
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
    scenarios = build_stub_scenarios(
        settings=settings,
        hero_asset=hero_asset,
        bridge_asset=bridge_asset,
    )
    scenario = scenarios["hero_port_disruption"]
    case = type(
        "Case",
        (),
        {
            "current_frame": scenario.current_frame,
            "baseline_frame": scenario.baseline_frame,
        },
    )

    current_path = str(Path("/tmp/current.png"))
    baseline_path = str(Path("/tmp/baseline.png"))
    current, baseline = materialize_case_frames(
        case=case,
        capture_record={
            "current": {
                "image_path": current_path,
                "request_url": "https://example.test/current",
                "response_metadata": {"cloud_cover": 7.0, "datetime": "2026-04-14T18:40:00Z"},
            },
            "baseline": {
                "image_path": baseline_path,
                "request_url": "https://example.test/baseline",
                "response_metadata": {"cloud_cover": 3.0, "datetime": "2025-09-01T10:00:00Z"},
            },
        },
    )

    assert current.frame.image_ref == current_path
    assert current.overlay_ref is None
    assert current.frame.source == "https://example.test/current"
    assert baseline.frame.image_ref == baseline_path
    assert baseline.frame.source == "https://example.test/baseline"
