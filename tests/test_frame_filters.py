from __future__ import annotations

from app.schemas.frame import FrameEnvelope, FrameRecord
from app.services.frame_filters import FrameFilterPolicy


def test_filter_accepts_clear_frame_with_distinct_baseline() -> None:
    policy = FrameFilterPolicy(cloud_cover_threshold=0.2)

    decision = policy.evaluate(
        current=_frame(
            frame_id="cur_demo_port_01_20260414",
            image_ref=".cache/frames/demo_port_01/current/image.png",
            cloud_cover=0.08,
        ),
        baseline=_frame(
            frame_id="base_demo_port_01_20250901",
            image_ref=".cache/frames/demo_port_01/baseline/image.png",
            cloud_cover=0.03,
        ),
    )

    assert decision.accepted is True
    assert decision.reason == "accepted"


def test_filter_rejects_cloudy_frame() -> None:
    policy = FrameFilterPolicy(cloud_cover_threshold=0.2)

    decision = policy.evaluate(
        current=_frame(
            frame_id="cur_demo_bridge_01_20260414",
            image_ref=".cache/frames/demo_bridge_01/current/image.png",
            cloud_cover=0.41,
        ),
        baseline=_frame(
            frame_id="base_demo_bridge_01_20251012",
            image_ref=".cache/frames/demo_bridge_01/baseline/image.png",
            cloud_cover=0.02,
        ),
    )

    assert decision.accepted is False
    assert decision.reason == "cloud_cover_too_high"


def test_filter_rejects_missing_or_low_value_frames() -> None:
    policy = FrameFilterPolicy()

    missing_current = policy.evaluate(
        current=_frame(frame_id="cur_missing", image_ref=None, cloud_cover=0.05),
        baseline=_frame(frame_id="base_ok", image_ref=".cache/frames/base.png", cloud_cover=0.01),
    )
    low_value = policy.evaluate(
        current=_frame(
            frame_id="cur_same",
            image_ref=".cache/frames/demo_port_01/current/image.png",
            cloud_cover=0.05,
        ),
        baseline=_frame(
            frame_id="base_same",
            image_ref=".cache/frames/demo_port_01/current/image.png",
            cloud_cover=0.01,
        ),
    )

    assert missing_current.accepted is False
    assert missing_current.reason == "missing_current_image"
    assert low_value.accepted is False
    assert low_value.reason == "low_value_frame"


def _frame(*, frame_id: str, image_ref: str | None, cloud_cover: float) -> FrameEnvelope:
    return FrameEnvelope(
        frame=FrameRecord(
            frame_id=frame_id,
            asset_id="demo_asset",
            captured_at="2026-04-14T18:40:00Z",
            image_ref=image_ref,
            cloud_cover=cloud_cover,
            source="sentinel_stub",
        ),
        baseline_frame_id=None,
        overlay_ref=None,
    )
