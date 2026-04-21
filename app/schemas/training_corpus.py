from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.alert import Action, Alert, AlertCandidate
from app.schemas.asset import Asset
from app.schemas.metrics import Metrics

CorpusSplit = Literal["train", "dev", "holdout_geo", "holdout_stress"]


class GroundingTarget(BaseModel):
    label: str
    bbox: tuple[float, float, float, float]

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


class LiquidGroundingRecord(BaseModel):
    record_id: str
    case_id: str
    asset_id: str
    split: CorpusSplit
    image_path: str
    task_text: str
    targets: list[GroundingTarget]
    sidecar_id: str
    messages: list[dict[str, object]]


class SimSatCorpusFrameSidecar(BaseModel):
    requested_timestamp: str
    request_url: str
    image_available: bool
    datetime: str | None = None
    cloud_cover: float | None = None
    footprint: list[float] = Field(default_factory=list)
    spectral_bands: list[str] = Field(default_factory=list)
    size_km: float | None = None
    window_seconds: float | None = None


class SimSatCorpusSidecar(BaseModel):
    current: SimSatCorpusFrameSidecar
    baseline: SimSatCorpusFrameSidecar


class BlacklineCandidateEvalRecord(BaseModel):
    case_id: str
    split: CorpusSplit
    benchmark_source: str | None = None
    benchmark_case_id: str | None = None
    asset: Asset
    current_image_path: str
    baseline_image_path: str
    prompt: dict[str, str]
    model_output_text: str
    expected_candidate: AlertCandidate
    expected_action: Action
    expected_alert: Alert
    expected_metrics: Metrics
    simsat: SimSatCorpusSidecar


class LeapVLMSFTRecord(BaseModel):
    record_id: str
    case_id: str
    asset_id: str
    source_split: CorpusSplit
    target_split: Literal["train", "eval"]
    task_kind: Literal["candidate_json_sft"] = "candidate_json_sft"
    messages: list[dict[str, object]]


class CorpusSplitCase(BaseModel):
    case_id: str
    asset_id: str
    aoi_key: str
    requested_date: str
    split: CorpusSplit
    holdout_reason: str | None = None
    is_hero: bool


class CorpusSplits(BaseModel):
    version: str
    policy: str
    split_counts: dict[str, int]
    cases: list[CorpusSplitCase]
