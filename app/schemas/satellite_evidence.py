from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.frame import FrameEnvelope

SatelliteEvidenceStatus = Literal["ready", "unavailable"]
SatelliteEvidenceScope = Literal[
    "exact_aoi",
    "nearby_aoi",
    "regional_aoi",
    "satellite_context_only",
]
SatelliteEvidenceUsability = Literal[
    "direct_clear",
    "cloud_limited",
    "context_only",
    "unavailable",
]


class SatelliteEvidenceAttempt(BaseModel):
    scope: SatelliteEvidenceScope
    latitude: float
    longitude: float
    size_km: float = Field(gt=0.0)
    window_seconds: float = Field(gt=0.0)
    current_status: str
    baseline_status: str
    current_cloud_cover: float | None = Field(default=None, ge=0.0, le=1.0)
    baseline_cloud_cover: float | None = Field(default=None, ge=0.0, le=1.0)
    reason: str


class SatelliteEvidenceBundle(BaseModel):
    asset_id: str
    lead_id: str | None = None
    status: SatelliteEvidenceStatus
    scope: SatelliteEvidenceScope
    usable_for_evidence: bool
    usability: SatelliteEvidenceUsability = "unavailable"
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    quality_summary: str = ""
    reason: str
    target_latitude: float
    target_longitude: float
    resolved_latitude: float
    resolved_longitude: float
    offset_km: float = Field(ge=0.0)
    size_km: float = Field(gt=0.0)
    requested_timestamp: str | None = None
    baseline_timestamp: str | None = None
    current_frame: FrameEnvelope | None = None
    baseline_frame: FrameEnvelope | None = None
    contact_sheet_image_ref: str | None = None
    contact_sheet_summary: str | None = None
    attempts: list[SatelliteEvidenceAttempt] = Field(default_factory=list)
    quality_warnings: list[str] = Field(default_factory=list)
