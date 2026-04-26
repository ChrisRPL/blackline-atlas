from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ModelGateDecision = Literal["replay_safe_adapter_rejected"]


class ModelEvalScore(BaseModel):
    action_match: int
    schema_valid: int
    downlink_recall: int
    downlink_total: int
    false_positives: int


class ModelStatus(BaseModel):
    base_model: str
    candidate_adapter: str
    training_dataset: str
    frozen_gold_cases: int
    decision: ModelGateDecision
    recommended_runtime: Literal["deterministic_replay"]
    summary: str
    base_eval: ModelEvalScore
    adapter_eval: ModelEvalScore
    acceptance_failures: list[str]
