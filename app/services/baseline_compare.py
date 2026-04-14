from __future__ import annotations

from typing import Protocol

from app.schemas.frame import FrameEnvelope


class BaselineComparator(Protocol):
    def compare(self, *, current: FrameEnvelope, baseline: FrameEnvelope) -> FrameEnvelope: ...


class FixtureBaselineComparator:
    def compare(self, *, current: FrameEnvelope, baseline: FrameEnvelope) -> FrameEnvelope:
        return current.model_copy(
            update={
                "baseline_frame_id": current.baseline_frame_id or baseline.frame.frame_id,
                "overlay_ref": current.overlay_ref or self._derive_overlay_ref(current),
            }
        )

    def _derive_overlay_ref(self, current: FrameEnvelope) -> str | None:
        image_ref = current.frame.image_ref
        if not image_ref:
            return None

        if "/current/" in image_ref:
            return image_ref.replace("/current/", "/overlay/")

        return None
