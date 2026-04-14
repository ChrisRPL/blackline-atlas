from __future__ import annotations

from app.schemas.frame import FrameEnvelope, FrameRecord
from app.services.baseline_compare import FixtureBaselineComparator


def test_comparator_preserves_existing_overlay_and_sets_baseline_id() -> None:
    comparator = FixtureBaselineComparator()
    current = FrameEnvelope(
        frame=FrameRecord(
            frame_id="cur_demo_port_01_20260414",
            asset_id="demo_port_01",
            captured_at="2026-04-14T18:40:00Z",
            image_ref=".cache/frames/demo_port_01/hero/current/cur_demo_port_01_20260414/image.png",
            cloud_cover=0.07,
            source="sentinel_current_stub",
        ),
        baseline_frame_id=None,
        overlay_ref=".cache/frames/demo_port_01/hero/overlay/cur_demo_port_01_20260414/image.png",
    )
    baseline = FrameEnvelope(
        frame=FrameRecord(
            frame_id="base_demo_port_01_20250901",
            asset_id="demo_port_01",
            captured_at="2025-09-01T10:00:00Z",
            image_ref=".cache/frames/demo_port_01/hero/baseline/base_demo_port_01_20250901/image.png",
            cloud_cover=0.03,
            source="sentinel_baseline_stub",
        ),
    )

    compared = comparator.compare(current=current, baseline=baseline)

    assert compared.overlay_ref == current.overlay_ref
    assert compared.baseline_frame_id == "base_demo_port_01_20250901"


def test_comparator_derives_overlay_path_from_current_image_ref() -> None:
    comparator = FixtureBaselineComparator()
    current = FrameEnvelope(
        frame=FrameRecord(
            frame_id="cur_demo_bridge_01_20260414",
            asset_id="demo_bridge_01",
            captured_at="2026-04-14T18:42:00Z",
            image_ref=(
                ".cache/frames/demo_bridge_01/bridge_access_obstruction/current/"
                "cur_demo_bridge_01_20260414/image.png"
            ),
            cloud_cover=0.05,
            source="sentinel_current_stub",
        ),
        baseline_frame_id="base_demo_bridge_01_20251012",
        overlay_ref=None,
    )
    baseline = FrameEnvelope(
        frame=FrameRecord(
            frame_id="base_demo_bridge_01_20251012",
            asset_id="demo_bridge_01",
            captured_at="2025-10-12T09:15:00Z",
            image_ref=None,
            cloud_cover=0.02,
            source="sentinel_baseline_stub",
        ),
    )

    compared = comparator.compare(current=current, baseline=baseline)

    assert compared.overlay_ref == (
        ".cache/frames/demo_bridge_01/bridge_access_obstruction/overlay/"
        "cur_demo_bridge_01_20260414/image.png"
    )
