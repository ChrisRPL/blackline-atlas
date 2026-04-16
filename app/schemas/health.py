from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ServiceState = Literal["ready", "not_configured", "degraded"]


class HealthDependency(BaseModel):
    status: ServiceState
    detail: str


class HealthConfig(BaseModel):
    simsat_current_http_enabled: bool
    simsat_baseline_http_enabled: bool
    mapbox_context_enabled: bool
    model_http_enabled: bool
    model_provider: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app_env: str
    model_backend: HealthDependency
    simsat_current: HealthDependency
    simsat_baseline: HealthDependency
    mapbox: HealthDependency
    config: HealthConfig
