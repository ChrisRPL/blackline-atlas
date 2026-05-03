from __future__ import annotations

from pydantic import BaseModel

from app.schemas.alert import Alert
from app.schemas.frame import FrameEnvelope
from app.schemas.metrics import Metrics


class ReplayStartRequest(BaseModel):
    asset_id: str | None = None
    scenario_id: str | None = None


class ReplayState(BaseModel):
    running: bool
    asset_id: str | None = None
    scenario_id: str | None = None
    last_transition_at: str
    hero_asset_id: str


class ReplaySnapshot(BaseModel):
    replay: ReplayState
    current_frame: FrameEnvelope
    baseline_frame: FrameEnvelope
    alerts: list[Alert]
    metrics: Metrics
