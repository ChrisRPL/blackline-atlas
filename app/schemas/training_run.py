from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TrainAdapterDatasetConfig(BaseModel):
    historical_endpoint: str | None = None
    replay_dataset: str
    capture_overrides: str | None = None
    capture_output_dir: str
    capture_manifest: str | None = None
    corpus_output_dir: str
    leap_output_dir: str
    dataset_manifest_name: str = "dataset_manifest.json"


class TrainAdapterModelConfig(BaseModel):
    model_id: str
    task_kind: Literal["candidate_json_sft"] = "candidate_json_sft"


class TrainAdapterEvalConfig(BaseModel):
    mode: Literal["smoke", "full_eval"]
    benchmark_on_start: bool = True
    max_eval_cases: int | None = None
    save_full_predictions: bool = False


class TrainAdapterRuntimeConfig(BaseModel):
    execution_environment: Literal["local", "hf_jobs"] = "local"
    editable_extras: str = "dev,vlm,train"
    output_dir: str


class TrainAdapterHFJobConfig(BaseModel):
    flavor: str = "l4x1"
    timeout: str = "4h"


class TrainAdapterTrainerTrainingConfig(BaseModel):
    extends: str = "DEFAULT_VLM_SFT"
    num_train_epochs: int = 1
    per_device_train_batch_size: int = 1
    gradient_accumulation_steps: int = 1
    learning_rate: float = 1e-5
    logging_steps: int = 1
    eval_on_start: bool = True
    eval_strategy: Literal["epoch", "steps", "no"] = "epoch"
    eval_steps: int | None = None
    save_strategy: Literal["epoch", "steps", "no"] = "epoch"
    save_steps: int | None = None
    save_total_limit: int = 1
    warmup_ratio: float | None = 0.03
    lr_scheduler_type: str | None = "cosine"


class TrainAdapterTrainerPeftConfig(BaseModel):
    extends: str = "DEFAULT_VLM_LORA"
    use_peft: bool = True
    r: int | None = None
    lora_alpha: int | None = None
    lora_dropout: float | None = None


class TrainAdapterTrainerConfig(BaseModel):
    backend: Literal["leap_finetune"] = "leap_finetune"
    project_name: str = "blackline-atlas"
    dataset_test_size: float = 0.1
    dataset_limit: int | None = None
    authoritative_eval_note: str = (
        "Frozen Blackline eval stays separate. "
        "The trainer-side test_size split is diagnostics only."
    )
    training_config: TrainAdapterTrainerTrainingConfig = Field(
        default_factory=TrainAdapterTrainerTrainingConfig
    )
    peft_config: TrainAdapterTrainerPeftConfig = Field(
        default_factory=TrainAdapterTrainerPeftConfig
    )

    @field_validator("dataset_test_size")
    @classmethod
    def validate_dataset_test_size(cls, value: float) -> float:
        if not 0 < value < 1:
            raise ValueError("dataset_test_size must be between 0 and 1")
        return value


class TrainAdapterConfig(BaseModel):
    version: str
    run_name: str
    purpose: str
    dataset: TrainAdapterDatasetConfig
    model: TrainAdapterModelConfig
    eval: TrainAdapterEvalConfig
    runtime: TrainAdapterRuntimeConfig
    hf_job: TrainAdapterHFJobConfig = Field(default_factory=TrainAdapterHFJobConfig)
    trainer: TrainAdapterTrainerConfig | None = None


class TrainAdapterPlan(BaseModel):
    config_path: str
    run_name: str
    purpose: str
    historical_endpoint: str | None = None
    replay_dataset: str
    capture_overrides: str | None = None
    capture_output_dir: str
    capture_manifest: str
    corpus_output_dir: str
    leap_output_dir: str
    dataset_manifest_path: str
    model_id: str
    task_kind: Literal["candidate_json_sft"]
    eval_mode: Literal["smoke", "full_eval"]
    benchmark_on_start: bool
    max_eval_cases: int | None = None
    save_full_predictions: bool
    execution_environment: Literal["local", "hf_jobs"]
    editable_extras: str
    output_dir: str
    hf_flavor: str
    hf_timeout: str


class TrainAdapterPreparedArtifacts(BaseModel):
    capture_manifest: str
    capture_dataset: str
    liquid_grounding_dataset: str
    candidate_eval_dataset: str
    splits_manifest: str
    leap_train_dataset: str
    leap_eval_dataset: str
    leap_summary: str
    dataset_manifest: str


class TrainAdapterDatasetManifest(BaseModel):
    version: str
    run_name: str
    purpose: str
    model_id: str
    task_kind: Literal["candidate_json_sft"]
    source_replay_dataset: str
    capture_manifest: str
    liquid_grounding_dataset: str
    candidate_eval_dataset: str
    splits_manifest: str
    image_root: str
    leap_train_dataset: str
    leap_eval_dataset: str
    leap_summary: str
    source_split_counts: dict[str, int]
    eval_mode: Literal["smoke", "full_eval"]
    benchmark_on_start: bool
    max_eval_cases: int | None = None
    save_full_predictions: bool
    execution_environment: Literal["local", "hf_jobs"]
    output_dir: str
    hf_flavor: str
    hf_timeout: str


class TrainBackendPlan(BaseModel):
    version: str
    run_name: str
    backend: Literal["leap_finetune"]
    dataset_manifest: str
    leap_train_dataset: str
    leap_eval_dataset: str
    image_root: str
    generated_config_path: str
    output_dir: str
    command: list[str]
    authoritative_eval_note: str
    bundle_dir: str
    bundle_archive: str


class TrainBundleManifest(BaseModel):
    version: str
    run_name: str
    backend: Literal["leap_finetune"]
    dataset_manifest: str
    train_jsonl: str
    eval_jsonl: str
    summary_json: str
    image_root: str
    bundle_dir: str
    bundle_archive: str
    train_records: int
    eval_records: int
    authoritative_eval_note: str
    uploaded_bundle_repo_id: str | None = None
    uploaded_bundle_path: str | None = None
    last_submit_status: str | None = None
    last_submit_error: str | None = None
