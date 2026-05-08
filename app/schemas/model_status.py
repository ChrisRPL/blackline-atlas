from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ModelGateDecision = Literal[
    "replay_safe_adapter_rejected",
    "evidence_adapter_guarded_runtime",
]
AdapterSignalRole = Literal["optional_non_authoritative"]
RuntimeAuthority = Literal[
    "deterministic_replay",
    "source_led_sam3_liquid_guarded",
    "source_led_sentinel_liquid_guarded",
]
AdapterPublicationStatus = Literal[
    "published_rejected",
    "published_guarded_runtime",
    "published_research_only",
    "superseded_rejected",
]


class ModelEvalScore(BaseModel):
    action_match: int
    schema_valid: int
    downlink_recall: int
    downlink_total: int
    false_positives: int


class EvaluatedAdapter(BaseModel):
    adapter: str
    training_dataset: str
    training_job: str | None = None
    status: AdapterPublicationStatus
    eval_scope: str
    eval_cases: int
    train_rows: int | None = None
    eval_rows: int | None = None
    eval_loss_start: float | None = None
    eval_loss_final: float | None = None
    score: ModelEvalScore
    failure_summary: str


class ModelStatus(BaseModel):
    base_model: str
    candidate_adapter: str
    training_dataset: str
    adapter_signal_role: AdapterSignalRole = "optional_non_authoritative"
    runtime_authority: RuntimeAuthority = "deterministic_replay"
    can_affect_alerts: bool = False
    frozen_gold_cases: int
    reported_eval_cases: int
    reported_eval_scope: str
    decision: ModelGateDecision
    recommended_runtime: RuntimeAuthority
    summary: str
    base_eval: ModelEvalScore
    adapter_eval: ModelEvalScore
    acceptance_failures: list[str]
    evaluated_adapters: list[EvaluatedAdapter] = Field(default_factory=list)
    latest_training_job: str | None = None
    training_eval_loss_start: float | None = None
    training_eval_loss_final: float | None = None
