from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse

from app.schemas.agent import AtlasAgentQueryRequest, AtlasAgentQueryResponse, AtlasAgentToolSpec
from app.schemas.alert import Alert
from app.schemas.asset import Asset
from app.schemas.frame import FrameEnvelope
from app.schemas.health import HealthResponse
from app.schemas.lead import Lead, LeadRefreshRequest, LeadRefreshResponse
from app.schemas.liquid_analyst import LiquidAnalystReport
from app.schemas.metrics import Metrics
from app.schemas.model_status import ModelStatus
from app.schemas.replay import ReplaySnapshot, ReplayStartRequest, ReplayState
from app.schemas.sam3_evidence import Sam3EvidenceReport
from app.services.contracts import AtlasService

router = APIRouter()
REPO_ROOT = Path(__file__).resolve().parents[2]
FRAME_IMAGE_ROOTS = (
    REPO_ROOT / ".cache" / "frames",
    REPO_ROOT / "var" / "simsat_frames",
    REPO_ROOT / "var" / "contact_sheets",
    REPO_ROOT / "var" / "mapbox_context",
    REPO_ROOT / "ui" / "assets",
)


def get_service(request: Request) -> AtlasService:
    return request.app.state.atlas_service


@router.get("/health", response_model=HealthResponse)
def health(service: Annotated[AtlasService, Depends(get_service)]) -> HealthResponse:
    return service.get_health()


@router.get("/model/status", response_model=ModelStatus)
def model_status(service: Annotated[AtlasService, Depends(get_service)]) -> ModelStatus:
    return service.get_model_status()


@router.get("/assets", response_model=list[Asset])
def assets(service: Annotated[AtlasService, Depends(get_service)]) -> list[Asset]:
    return service.list_assets()


@router.get("/leads", response_model=list[Lead])
def leads(service: Annotated[AtlasService, Depends(get_service)]) -> list[Lead]:
    return service.list_leads()


@router.post("/leads/refresh", response_model=LeadRefreshResponse)
def refresh_leads(
    payload: LeadRefreshRequest,
    service: Annotated[AtlasService, Depends(get_service)],
) -> LeadRefreshResponse:
    return service.refresh_leads(payload)


@router.get("/agent/tools", response_model=list[AtlasAgentToolSpec])
def agent_tools(service: Annotated[AtlasService, Depends(get_service)]) -> list[AtlasAgentToolSpec]:
    return service.list_agent_tools()


@router.post("/agent/query", response_model=AtlasAgentQueryResponse)
def agent_query(
    payload: AtlasAgentQueryRequest,
    service: Annotated[AtlasService, Depends(get_service)],
) -> AtlasAgentQueryResponse:
    return service.run_agent_query(payload)


@router.post("/replay/start", response_model=ReplayState)
def replay_start(
    payload: ReplayStartRequest,
    service: Annotated[AtlasService, Depends(get_service)],
) -> ReplayState:
    return service.start_replay(payload)


@router.post("/replay/stop", response_model=ReplayState)
def replay_stop(service: Annotated[AtlasService, Depends(get_service)]) -> ReplayState:
    return service.stop_replay()


@router.get("/replay/status", response_model=ReplayState)
def replay_status(service: Annotated[AtlasService, Depends(get_service)]) -> ReplayState:
    return service.get_replay_state()


@router.get("/replay/snapshot", response_model=ReplaySnapshot)
def replay_snapshot(service: Annotated[AtlasService, Depends(get_service)]) -> ReplaySnapshot:
    return service.get_replay_snapshot()


@router.get("/evidence/current", response_model=Sam3EvidenceReport)
def current_evidence(service: Annotated[AtlasService, Depends(get_service)]) -> Sam3EvidenceReport:
    return service.get_current_evidence()


@router.get("/evidence/assets/{asset_id}", response_model=Sam3EvidenceReport | None)
def asset_evidence(
    asset_id: str,
    service: Annotated[AtlasService, Depends(get_service)],
) -> Sam3EvidenceReport | None:
    return service.get_asset_evidence(asset_id)


@router.get("/frame-image", include_in_schema=False)
def frame_image(ref: Annotated[str, Query(min_length=1)]) -> FileResponse:
    image_path = _resolve_frame_image_ref(ref)
    if image_path is None:
        raise HTTPException(status_code=404, detail="frame image unavailable")
    return FileResponse(image_path)


@router.get("/analyst/assets/{asset_id}", response_model=LiquidAnalystReport | None)
def asset_analyst_report(
    asset_id: str,
    service: Annotated[AtlasService, Depends(get_service)],
) -> LiquidAnalystReport | None:
    return service.get_asset_analyst_report(asset_id)


@router.get("/frames/current", response_model=FrameEnvelope)
def current_frame(service: Annotated[AtlasService, Depends(get_service)]) -> FrameEnvelope:
    return service.get_current_frame()


@router.get("/frames/baseline", response_model=FrameEnvelope)
def baseline_frame(service: Annotated[AtlasService, Depends(get_service)]) -> FrameEnvelope:
    return service.get_baseline_frame()


@router.get("/alerts", response_model=list[Alert])
def alerts(service: Annotated[AtlasService, Depends(get_service)]) -> list[Alert]:
    return service.list_alerts()


@router.get("/metrics", response_model=Metrics)
def metrics(service: Annotated[AtlasService, Depends(get_service)]) -> Metrics:
    return service.get_metrics()


def _resolve_frame_image_ref(ref: str) -> Path | None:
    if ref.startswith(("http://", "https://", "data:")):
        return None

    candidate = Path(ref)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    try:
        resolved = candidate.resolve()
    except OSError:
        return None

    allowed_roots = [root.resolve() for root in FRAME_IMAGE_ROOTS]
    if not any(resolved == root or root in resolved.parents for root in allowed_roots):
        return None
    if not resolved.is_file():
        return None
    return resolved
