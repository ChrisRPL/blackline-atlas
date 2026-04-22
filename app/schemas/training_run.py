from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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


class TrainAdapterConfig(BaseModel):
    version: str
    run_name: str
    purpose: str
    dataset: TrainAdapterDatasetConfig
    model: TrainAdapterModelConfig
    eval: TrainAdapterEvalConfig
    runtime: TrainAdapterRuntimeConfig
    hf_job: TrainAdapterHFJobConfig = Field(default_factory=TrainAdapterHFJobConfig)


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
