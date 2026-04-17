from __future__ import annotations

from pydantic import BaseModel

from app.schemas.alert import Action, Alert, AlertCandidate
from app.schemas.asset import Asset
from app.schemas.frame import FrameEnvelope
from app.schemas.metrics import Metrics
from app.schemas.training_corpus import CorpusSplit


class AnnotatedCaseRecord(BaseModel):
    case_id: str
    asset: Asset
    hero: bool = False
    current_frame: FrameEnvelope
    baseline_frame: FrameEnvelope
    model_output_text: str
    expected_candidate: AlertCandidate
    expected_alert: Alert
    expected_action: Action
    expected_metrics: Metrics
    split: CorpusSplit | None = None
    holdout_reason: str | None = None
    annotation_source: str | None = None
