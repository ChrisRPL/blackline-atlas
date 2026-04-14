from __future__ import annotations

from pydantic import BaseModel


class Metrics(BaseModel):
    frames_scanned: int
    alerts_emitted: int
    raw_frames_suppressed: int
    downlink_rate: float
