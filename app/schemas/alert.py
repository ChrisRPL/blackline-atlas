from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

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


class AlertCandidate(BaseModel):
    event_type: EventType
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: tuple[float, float, float, float]
    civilian_impact: CivilianImpact
    why: str
    action: Action

    @field_validator("bbox")
    @classmethod
    def validate_bbox(
        cls,
        value: tuple[float, float, float, float],
    ) -> tuple[float, float, float, float]:
        x1, y1, x2, y2 = value
        if not all(0.0 <= component <= 1.0 for component in value):
            raise ValueError("bbox coordinates must be normalized between 0 and 1")
        if x1 >= x2 or y1 >= y2:
            raise ValueError("bbox coordinates must define a positive rectangle")
        return value


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
