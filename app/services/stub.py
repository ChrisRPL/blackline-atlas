from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.config import Settings
from app.schemas.alert import Alert, AlertSource
from app.schemas.asset import Asset
from app.schemas.frame import FrameEnvelope, FrameRecord
from app.schemas.health import HealthDependency, HealthResponse
from app.schemas.metrics import Metrics
from app.schemas.replay import ReplayStartRequest, ReplayState


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


@dataclass
class MutableReplayState:
    running: bool
    asset_id: str | None
    scenario_id: str | None
    last_transition_at: str


class StubAtlasService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.assets = [
            Asset(
                asset_id="demo_port_01",
                asset_name="Demo Grain Port",
                asset_type="grain_port",
                region="Black Sea",
                latitude=46.501,
                longitude=30.747,
                hero=True,
            ),
            Asset(
                asset_id="demo_bridge_01",
                asset_name="Demo Logistics Bridge",
                asset_type="bridge",
                region="Lower Danube",
                latitude=45.169,
                longitude=28.801,
            ),
        ]
        self.metrics = Metrics(
            frames_scanned=143,
            alerts_emitted=5,
            raw_frames_suppressed=138,
            downlink_rate=0.035,
        )
        self.replay = MutableReplayState(
            running=False,
            asset_id=None,
            scenario_id=None,
            last_transition_at=utc_now(),
        )

    @property
    def hero_asset(self) -> Asset:
        return next(asset for asset in self.assets if asset.hero)

    def get_health(self) -> HealthResponse:
        return HealthResponse(
            status="ok",
            app_env=self.settings.app_env,
            model_backend=HealthDependency(status="ready", detail=self.settings.model_version),
            simsat_current=self._dependency_state(
                self.settings.simsat_current_endpoint,
                "current Sentinel endpoint not configured yet",
            ),
            simsat_baseline=self._dependency_state(
                self.settings.simsat_baseline_endpoint,
                "historical baseline endpoint not configured yet",
            ),
            mapbox=HealthDependency(
                status="ready" if self.settings.mapbox_token_present else "not_configured",
                detail="token present" if self.settings.mapbox_token_present else "token missing",
            ),
        )

    def list_assets(self) -> list[Asset]:
        return self.assets

    def start_replay(self, request: ReplayStartRequest) -> ReplayState:
        chosen_asset = request.asset_id or self.hero_asset.asset_id
        self.replay.running = True
        self.replay.asset_id = chosen_asset
        self.replay.scenario_id = request.scenario_id or "hero_scenario"
        self.replay.last_transition_at = utc_now()
        return self.get_replay_state()

    def stop_replay(self) -> ReplayState:
        self.replay.running = False
        self.replay.last_transition_at = utc_now()
        return self.get_replay_state()

    def get_replay_state(self) -> ReplayState:
        return ReplayState(
            running=self.replay.running,
            asset_id=self.replay.asset_id,
            scenario_id=self.replay.scenario_id,
            last_transition_at=self.replay.last_transition_at,
            hero_asset_id=self.hero_asset.asset_id,
        )

    def get_current_frame(self) -> FrameEnvelope:
        asset_id = self.replay.asset_id or self.hero_asset.asset_id
        return FrameEnvelope(
            frame=FrameRecord(
                frame_id=f"cur_{asset_id}",
                asset_id=asset_id,
                captured_at=utc_now(),
                image_ref=None,
                cloud_cover=0.07,
                source="sentinel_current_stub",
            ),
            baseline_frame_id=f"base_{asset_id}",
            overlay_ref=None,
        )

    def get_baseline_frame(self) -> FrameEnvelope:
        asset_id = self.replay.asset_id or self.hero_asset.asset_id
        return FrameEnvelope(
            frame=FrameRecord(
                frame_id=f"base_{asset_id}",
                asset_id=asset_id,
                captured_at="2025-09-01T10:00:00Z",
                image_ref=None,
                cloud_cover=0.03,
                source="sentinel_baseline_stub",
            ),
            baseline_frame_id=None,
            overlay_ref=None,
        )

    def list_alerts(self) -> list[Alert]:
        asset = self._asset_by_id(self.replay.asset_id or self.hero_asset.asset_id)
        return [
            Alert(
                alert_id="blk_00017",
                timestamp=utc_now(),
                asset_id=asset.asset_id,
                asset_name=asset.asset_name,
                asset_type=asset.asset_type,
                event_type="probable_large_scale_disruption",
                severity="high",
                confidence=0.89,
                bbox=(0.19, 0.26, 0.73, 0.84),
                civilian_impact="shipping_or_aid_disruption",
                why="Significant surface change near terminal footprint versus recent baseline.",
                action="downlink_now",
                source=AlertSource(
                    current_frame_id=f"cur_{asset.asset_id}",
                    baseline_frame_id=f"base_{asset.asset_id}",
                    model_version=self.settings.model_version,
                ),
            )
        ]

    def get_metrics(self) -> Metrics:
        return self.metrics

    def _dependency_state(self, endpoint: str | None, missing_detail: str) -> HealthDependency:
        if endpoint:
            return HealthDependency(status="ready", detail=endpoint)
        return HealthDependency(status="not_configured", detail=missing_detail)

    def _asset_by_id(self, asset_id: str) -> Asset:
        for asset in self.assets:
            if asset.asset_id == asset_id:
                return asset
        return self.hero_asset
