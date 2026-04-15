from __future__ import annotations

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

    assert frame.accepted_for_alerting is False
    assert frame.filter_reason == "cloud_cover_too_high"
    assert frame.overlay_ref is None
    assert metrics.raw_frames_suppressed == 139
