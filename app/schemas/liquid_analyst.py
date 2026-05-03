from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.alert import Action
from app.schemas.evidence_candidate import VisualEvidenceTag

LiquidAnalystBackendMode = Literal["fixture", "liquid_vlm_http"]
LiquidAnalystStatus = Literal["ready", "unavailable", "rejected"]
LiquidAnalystSeverityHint = Literal["none", "low", "moderate", "severe"]

FORBIDDEN_ANALYST_TERMS = {
    "air defense",
    "ammo",
    "ammunition",
    "artillery position",
    "base",
    "battalion",
    "convoy",
    "drone launch",
    "missile launcher",
    "munition",
    "radar site",
    "strike package",
    "strike planning",
    "target",
    "targeting",
    "troop",
    "weapon",
}
FORBIDDEN_ANALYST_PATTERNS = tuple(
    re.compile(r"(?<![a-z0-9])" + re.escape(term).replace(r"\ ", r"\s+") + r"(?![a-z0-9])")
    for term in FORBIDDEN_ANALYST_TERMS
)


class LiquidAnalystReport(BaseModel):
    asset_id: str
    current_frame_id: str
    baseline_frame_id: str | None = None
    current_image_ref: str | None = None
    baseline_image_ref: str | None = None
    model_version: str
    backend: LiquidAnalystBackendMode
    status: LiquidAnalystStatus
    visible_change_summary: str
    civilian_disruption_evidence: list[VisualEvidenceTag] = Field(default_factory=list)
    negative_evidence: list[VisualEvidenceTag] = Field(default_factory=list)
    uncertainty_factors: list[str] = Field(default_factory=list)
    severity_hint: LiquidAnalystSeverityHint
    recommended_action: Action
    confidence: float = Field(ge=0.0, le=1.0)
    short_rationale: str

    @field_validator("recommended_action", mode="before")
    @classmethod
    def normalize_recommended_action(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return {
            "downlink": "downlink_now",
            "downlink now": "downlink_now",
            "review": "defer",
            "hold": "defer",
            "ignore": "discard",
        }.get(value.strip().lower(), value)

    @field_validator("severity_hint", mode="before")
    @classmethod
    def normalize_severity_hint(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return {
            "medium": "moderate",
            "material": "moderate",
            "high": "severe",
            "critical": "severe",
            "no_change": "none",
            "no change": "none",
        }.get(value.strip().lower(), value)

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if "summary" in normalized and "visible_change_summary" not in normalized:
            normalized["visible_change_summary"] = normalized["summary"]
        if "rationale" in normalized and "short_rationale" not in normalized:
            normalized["short_rationale"] = normalized["rationale"]
        if "evidence" in normalized and "civilian_disruption_evidence" not in normalized:
            normalized["civilian_disruption_evidence"] = normalized["evidence"]
        if "action" in normalized and "recommended_action" not in normalized:
            normalized["recommended_action"] = normalized["action"]
        return normalized

    @model_validator(mode="after")
    def reject_tactical_language(self) -> "LiquidAnalystReport":
        text = " ".join(
            [
                self.visible_change_summary,
                self.short_rationale,
                *self.uncertainty_factors,
            ]
        ).lower()
        if any(pattern.search(text) for pattern in FORBIDDEN_ANALYST_PATTERNS):
            raise ValueError("analyst report contains tactical or military-scoped language")
        return self
