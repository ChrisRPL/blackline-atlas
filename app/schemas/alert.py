from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.asset import AssetType

EventType = Literal[
    "probable_large_scale_disruption",
    "probable_surface_change",
    "probable_access_obstruction",
    "no_event",
]
Severity = Literal["low", "medium", "high"]
CivilianImpact = Literal[
    "shipping_or_aid_disruption",
    "logistics_delay",
    "trade_disruption",
    "public_mobility_disruption",
    "no_material_impact",
]
Action = Literal["discard", "defer", "downlink_now"]


class AlertSource(BaseModel):
    current_frame_id: str
    baseline_frame_id: str
    model_version: str


class Alert(BaseModel):
    alert_id: str
    timestamp: str
    asset_id: str
    asset_name: str
    asset_type: AssetType
    event_type: EventType
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: tuple[float, float, float, float]
    civilian_impact: CivilianImpact
    why: str
    action: Action
    source: AlertSource
    mapbox_context_ref: str | None = None
