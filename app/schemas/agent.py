from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.alert import Alert
from app.schemas.asset import AssetType
from app.schemas.frame import FrameEnvelope
from app.schemas.lead import Lead
from app.schemas.liquid_analyst import LiquidAnalystReport
from app.schemas.replay import ReplayState
from app.schemas.satellite_evidence import SatelliteEvidenceBundle

AtlasAgentTool = Literal[
    "answer",
    "scope_refusal",
    "search_live_leads",
    "latest_alerts",
    "biggest_disruptions",
    "site_compare",
    "explain_alert",
    "refresh_live_leads",
]

AtlasAgentObservationStatus = Literal["ok", "no_result", "skipped", "error"]
AtlasAgentTrustMode = Literal["live", "replay_safe", "degraded"]
AtlasAgentPlannerMode = Literal["deterministic", "live", "fallback"]
AtlasAgentPlannerReason = Literal[
    "explicit_tool",
    "fixture_planner",
    "planner_not_configured",
    "planner_unsupported_provider",
    "planner_http_failed",
    "planner_invalid_json",
]
AtlasAgentCameraMode = Literal["watchlist", "focus_asset", "focus_lead"]


class AtlasAgentToolArgument(BaseModel):
    name: str
    description: str
    required: bool = False


class AtlasAgentToolSpec(BaseModel):
    name: AtlasAgentTool
    description: str
    arguments: list[AtlasAgentToolArgument]


class AtlasAgentToolObservation(BaseModel):
    tool: AtlasAgentTool
    status: AtlasAgentObservationStatus
    summary: str
    count: int = 0


class AtlasAgentTrust(BaseModel):
    mode: AtlasAgentTrustMode
    detail: str


class AtlasAgentPlannerTelemetry(BaseModel):
    mode: AtlasAgentPlannerMode
    detail: str
    reason: AtlasAgentPlannerReason | None = None


class AtlasAgentCameraIntent(BaseModel):
    mode: AtlasAgentCameraMode
    asset_id: str | None = None
    lead_id: str | None = None
    highlight_asset_ids: list[str] = Field(default_factory=list)
    highlight_lead_ids: list[str] = Field(default_factory=list)


class AtlasAgentResolvedRequest(BaseModel):
    tool: AtlasAgentTool
    area: str | None = None
    category: AssetType | None = None
    site_id: str | None = None
    alert_id: str | None = None
    selected_asset_id: str | None = None
    selected_lead_id: str | None = None
    user_latitude: float | None = Field(default=None, ge=-90, le=90)
    user_longitude: float | None = Field(default=None, ge=-180, le=180)
    limit: int = Field(default=3, ge=1, le=10)


class AtlasAgentCompare(BaseModel):
    asset_id: str
    asset_name: str
    current_frame: FrameEnvelope
    baseline_frame: FrameEnvelope
    satellite_evidence: SatelliteEvidenceBundle | None = None


class AtlasAgentQueryRequest(BaseModel):
    query: str | None = None
    tool: AtlasAgentTool | None = None
    area: str | None = None
    category: AssetType | None = None
    site_id: str | None = None
    alert_id: str | None = None
    selected_asset_id: str | None = None
    selected_lead_id: str | None = None
    user_latitude: float | None = Field(default=None, ge=-90, le=90)
    user_longitude: float | None = Field(default=None, ge=-180, le=180)
    limit: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def validate_query_or_tool(self) -> "AtlasAgentQueryRequest":
        if not self.query and not self.tool:
            raise ValueError("agent query requires either query text or an explicit tool")
        return self


class AtlasAgentPlan(BaseModel):
    tool: AtlasAgentTool
    area: str | None = None
    category: AssetType | None = None
    site_id: str | None = None
    alert_id: str | None = None
    camera: AtlasAgentCameraIntent | None = None


class AtlasAgentQueryResponse(BaseModel):
    status: Literal["ok", "no_result"]
    tool: AtlasAgentTool
    summary: str
    resolved: AtlasAgentResolvedRequest
    camera: AtlasAgentCameraIntent | None = None
    focus_asset_id: str | None = None
    focus_lead_id: str | None = None
    focus_alert_id: str | None = None
    alerts: list[Alert] = Field(default_factory=list)
    leads: list[Lead] = Field(default_factory=list)
    observations: list[AtlasAgentToolObservation] = Field(default_factory=list)
    compare: AtlasAgentCompare | None = None
    analyst_report: LiquidAnalystReport | None = None
    planner: AtlasAgentPlannerTelemetry
    trust: AtlasAgentTrust
    replay: ReplayState
