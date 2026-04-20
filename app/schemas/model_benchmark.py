from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

BenchmarkTier = Literal["internal", "external_task_fit", "external_sanity"]
BenchmarkSliceStatus = Literal["ready", "planned"]
BenchmarkRunnerKind = Literal["transformers_local", "openai_chat_completions_http"]


class BenchmarkModelConfig(BaseModel):
    model_key: str
    title: str
    model_id: str
    runner_kind: BenchmarkRunnerKind
    enabled: bool = True
    provider_id: str | None = None
    endpoint_env: str | None = None
    api_key_env: str | None = None
    notes: str | None = None


class BenchmarkSliceConfig(BaseModel):
    slice_id: str
    title: str
    tier: BenchmarkTier
    status: BenchmarkSliceStatus
    dataset_path: str | None = None
    source_label: str | None = None
    source_url: str | None = None
    notes: str | None = None


class BenchmarkManifest(BaseModel):
    version: str
    default_output_dir: str
    models: list[BenchmarkModelConfig]
    slices: list[BenchmarkSliceConfig]
