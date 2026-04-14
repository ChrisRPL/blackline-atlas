from __future__ import annotations

from pydantic import BaseModel


class ReplayStartRequest(BaseModel):
    asset_id: str | None = None
    scenario_id: str | None = None


class ReplayState(BaseModel):
    running: bool
    asset_id: str | None = None
    scenario_id: str | None = None
    last_transition_at: str
    hero_asset_id: str
