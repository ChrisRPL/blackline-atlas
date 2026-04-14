from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.schemas.frame import FrameEnvelope

FrameFilterReason = Literal[
    "accepted",
    "missing_current_image",
    "missing_baseline_image",
    "cloud_cover_too_high",
    "low_value_frame",
]


@dataclass(frozen=True)
class FrameFilterDecision:
    accepted: bool
    reason: FrameFilterReason


@dataclass(frozen=True)
class FrameFilterPolicy:
    cloud_cover_threshold: float = 0.25

    def evaluate(self, *, current: FrameEnvelope, baseline: FrameEnvelope) -> FrameFilterDecision:
        if not current.frame.image_ref:
            return FrameFilterDecision(accepted=False, reason="missing_current_image")

        if not baseline.frame.image_ref:
            return FrameFilterDecision(accepted=False, reason="missing_baseline_image")

        cloud_cover = current.frame.cloud_cover
        if cloud_cover is not None and cloud_cover > self.cloud_cover_threshold:
            return FrameFilterDecision(accepted=False, reason="cloud_cover_too_high")

        if current.frame.image_ref == baseline.frame.image_ref:
            return FrameFilterDecision(accepted=False, reason="low_value_frame")

        return FrameFilterDecision(accepted=True, reason="accepted")
