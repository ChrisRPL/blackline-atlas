from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.alert import Action
from app.schemas.evidence_candidate import VisualEvidenceTag

Sam3EvidenceBackendMode = Literal["fixture", "sam3_http", "sam3_transformers", "sam3_official"]
Sam3EvidenceDecision = Literal["segmentation_ready", "no_evidence", "unavailable"]
Sam3EvidenceFrameRole = Literal["current", "baseline"]
Sam3SatelliteRelevance = Literal["none", "low", "medium", "high"]


class Sam3SourceContext(BaseModel):
    title: str
    summary: str | None = None
    region: str | None = None
    satellite_relevance: Sam3SatelliteRelevance = "medium"
    target_prompts: list[str] = Field(default_factory=list)
    ignore_terms: list[str] = Field(default_factory=list)
    rationale: str = ""


class Sam3EvidenceMask(BaseModel):
    label: str
    prompt: str
    score: float = Field(ge=0.0, le=1.0)
    bbox_norm: tuple[float, float, float, float]
    area_ratio: float = Field(ge=0.0, le=1.0)
    frame_role: Sam3EvidenceFrameRole = "current"
    matched_baseline_iou: float | None = Field(default=None, ge=0.0, le=1.0)
    temporal_change_score: float | None = Field(default=None, ge=0.0, le=1.0)


class Sam3EvidenceReport(BaseModel):
    asset_id: str
    current_frame_id: str
    baseline_frame_id: str | None = None
    current_image_ref: str | None = None
    baseline_image_ref: str | None = None
    overlay_ref: str | None = None
    model_version: str
    backend: Sam3EvidenceBackendMode
    decision: Sam3EvidenceDecision
    source_context: Sam3SourceContext | None = None
    prompts: list[str] = Field(default_factory=list)
    masks: list[Sam3EvidenceMask] = Field(default_factory=list)
    visual_evidence_tags: list[VisualEvidenceTag] = Field(default_factory=list)
    triage_action: Action
    summary: str
