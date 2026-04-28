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
    reported_eval_cases: int
    reported_eval_scope: str
    decision: ModelGateDecision
    recommended_runtime: Literal["deterministic_replay"]
    summary: str
    base_eval: ModelEvalScore
    adapter_eval: ModelEvalScore
    acceptance_failures: list[str]
    latest_training_job: str | None = None
    training_eval_loss_start: float | None = None
    training_eval_loss_final: float | None = None
