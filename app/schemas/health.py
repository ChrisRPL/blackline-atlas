from __future__ import annotations

from datetime import datetime
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
    agent_model_version: str
    agent_http_enabled: bool
    agent_provider: str


class HealthGatewayRecent(BaseModel):
    model_version: str
    provider_id: str
    latency_ms: int
    cache_hit: bool
    parse_ok: bool
    seen_at: datetime
    fallback_reason: str | None = None


class HealthDebug(BaseModel):
    model_recent: HealthGatewayRecent | None = None
    agent_recent: HealthGatewayRecent | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app_env: str
    model_backend: HealthDependency
    agent_backend: HealthDependency
    simsat_current: HealthDependency
    simsat_baseline: HealthDependency
    mapbox: HealthDependency
    config: HealthConfig
    debug: HealthDebug | None = None
