from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ServiceState = Literal["ready", "not_configured", "degraded"]


class HealthDependency(BaseModel):
    status: ServiceState
    detail: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app_env: str
    model_backend: HealthDependency
    simsat_current: HealthDependency
    simsat_baseline: HealthDependency
    mapbox: HealthDependency
