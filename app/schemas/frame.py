from __future__ import annotations

from pydantic import BaseModel


class FrameRecord(BaseModel):
    frame_id: str
    asset_id: str
    captured_at: str
    image_ref: str | None = None
    cloud_cover: float | None = None
    source: str


class FrameEnvelope(BaseModel):
    frame: FrameRecord
    baseline_frame_id: str | None = None
    overlay_ref: str | None = None
    accepted_for_alerting: bool | None = None
    filter_reason: str | None = None
