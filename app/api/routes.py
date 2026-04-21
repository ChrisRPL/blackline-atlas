from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.schemas.agent import AtlasAgentQueryRequest, AtlasAgentQueryResponse, AtlasAgentToolSpec
from app.schemas.alert import Alert
from app.schemas.asset import Asset
from app.schemas.frame import FrameEnvelope
from app.schemas.health import HealthResponse
from app.schemas.lead import Lead
from app.schemas.metrics import Metrics
from app.schemas.replay import ReplayStartRequest, ReplayState
from app.services.contracts import AtlasService

router = APIRouter()


def get_service(request: Request) -> AtlasService:
    return request.app.state.atlas_service


@router.get("/health", response_model=HealthResponse)
def health(service: Annotated[AtlasService, Depends(get_service)]) -> HealthResponse:
    return service.get_health()


@router.get("/assets", response_model=list[Asset])
def assets(service: Annotated[AtlasService, Depends(get_service)]) -> list[Asset]:
    return service.list_assets()


@router.get("/leads", response_model=list[Lead])
def leads(service: Annotated[AtlasService, Depends(get_service)]) -> list[Lead]:
    return service.list_leads()


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
