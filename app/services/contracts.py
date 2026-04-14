from __future__ import annotations

from typing import Protocol

from app.schemas.alert import Alert
from app.schemas.asset import Asset
from app.schemas.frame import FrameEnvelope
from app.schemas.health import HealthResponse
from app.schemas.metrics import Metrics
from app.schemas.replay import ReplayStartRequest, ReplayState


class AtlasService(Protocol):
    def get_health(self) -> HealthResponse: ...

    def list_assets(self) -> list[Asset]: ...

    def start_replay(self, request: ReplayStartRequest) -> ReplayState: ...

    def stop_replay(self) -> ReplayState: ...

    def get_replay_state(self) -> ReplayState: ...

    def get_current_frame(self) -> FrameEnvelope: ...

    def get_baseline_frame(self) -> FrameEnvelope: ...

    def list_alerts(self) -> list[Alert]: ...

    def get_metrics(self) -> Metrics: ...
