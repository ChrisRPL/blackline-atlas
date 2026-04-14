from __future__ import annotations

from app.services.frame_cache import FrameCacheKey, FrameCacheLayout, slug_token


def test_cache_layout_builds_stable_paths(tmp_path) -> None:
    layout = FrameCacheLayout(tmp_path)
    key = FrameCacheKey(
        asset_id="demo_port_01",
        scenario_id="hero_port_disruption",
        frame_id="cur_demo_port_01_20260414",
        variant="current",
    )

    assert layout.frame_dir(key) == (
        tmp_path / "demo_port_01" / "hero_port_disruption" / "current" / "cur_demo_port_01_20260414"
    )
    assert layout.image_path(key) == (
        tmp_path
        / "demo_port_01"
        / "hero_port_disruption"
        / "current"
        / "cur_demo_port_01_20260414"
        / "image.png"
    )
    assert layout.metadata_path(key) == (
        tmp_path
        / "demo_port_01"
        / "hero_port_disruption"
        / "current"
        / "cur_demo_port_01_20260414"
        / "metadata.json"
    )


def test_prepare_frame_dir_creates_slugged_directory(tmp_path) -> None:
    layout = FrameCacheLayout(tmp_path)
    key = FrameCacheKey(
        asset_id="demo port/01",
        scenario_id="hero port disruption",
        frame_id="cur:2026/04/14",
        variant="overlay",
    )

    created = layout.prepare_frame_dir(key)

    assert created.exists()
    assert (
        created == tmp_path / "demo-port-01" / "hero-port-disruption" / "overlay" / "cur-2026-04-14"
    )
    assert slug_token("  ") == "unknown"
