from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.alert import Action
from app.schemas.asset import Asset
from app.schemas.evidence_candidate import VisualEvidenceTag
from app.schemas.frame import FrameEnvelope

Sam3EvalSplit = Literal["eval", "calibration", "train"]


class Sam3EvalCase(BaseModel):
    case_id: str
    source_case_id: str
    source_dataset: str
    split: Sam3EvalSplit
    asset: Asset
    current_frame: FrameEnvelope
    baseline_frame: FrameEnvelope
    prompts: list[str] = Field(min_length=1)
    expected_action: Action
    expected_visual_evidence_tags: list[VisualEvidenceTag] = Field(default_factory=list)
    expected_bbox_norm: tuple[float, float, float, float] | None = None
    expected_min_iou: float = Field(default=0.2, ge=0.0, le=1.0)
    hard_negative_reason: str | None = None

    @field_validator("expected_bbox_norm")
    @classmethod
    def validate_expected_bbox(
        cls,
        value: tuple[float, float, float, float] | None,
    ) -> tuple[float, float, float, float] | None:
        if value is None:
            return value
        x1, y1, x2, y2 = value
        if not all(0.0 <= component <= 1.0 for component in value):
            raise ValueError("expected_bbox_norm coordinates must be normalized")
        if x1 >= x2 or y1 >= y2:
            raise ValueError("expected_bbox_norm must define a positive rectangle")
        return value
