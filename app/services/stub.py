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


@dataclass(frozen=True)
class ScenarioFixture:
    scenario_id: str
    asset_id: str
    current_frame: FrameEnvelope
    baseline_frame: FrameEnvelope
    alerts: list[Alert]
    metrics: Metrics


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
        self.scenarios = self._build_scenarios()
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
        scenario = self._select_scenario(request.asset_id, request.scenario_id)
        self.replay.running = True
        self.replay.asset_id = scenario.asset_id
        self.replay.scenario_id = scenario.scenario_id
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
        return self._active_scenario().current_frame

    def get_baseline_frame(self) -> FrameEnvelope:
        return self._active_scenario().baseline_frame

    def list_alerts(self) -> list[Alert]:
        return self._active_scenario().alerts

    def get_metrics(self) -> Metrics:
        return self._active_scenario().metrics

    def _dependency_state(self, endpoint: str | None, missing_detail: str) -> HealthDependency:
        if endpoint:
            return HealthDependency(status="ready", detail=endpoint)
        return HealthDependency(status="not_configured", detail=missing_detail)

    def _asset_by_id(self, asset_id: str) -> Asset:
        for asset in self.assets:
            if asset.asset_id == asset_id:
                return asset
        return self.hero_asset

    def _active_scenario(self) -> ScenarioFixture:
        scenario_id = self.replay.scenario_id or "hero_port_disruption"
        return self.scenarios.get(scenario_id, self.scenarios["hero_port_disruption"])

    def _select_scenario(self, asset_id: str | None, scenario_id: str | None) -> ScenarioFixture:
        if scenario_id and scenario_id in self.scenarios:
            return self.scenarios[scenario_id]

        if asset_id == "demo_bridge_01":
            return self.scenarios["bridge_access_obstruction"]

        return self.scenarios["hero_port_disruption"]

    def _build_scenarios(self) -> dict[str, ScenarioFixture]:
        hero_asset = self.hero_asset
        bridge_asset = self._asset_by_id("demo_bridge_01")

        hero_current_frame = FrameEnvelope(
            frame=FrameRecord(
                frame_id="cur_demo_port_01_20260414",
                asset_id=hero_asset.asset_id,
                captured_at="2026-04-14T18:40:00Z",
                image_ref="fixtures/demo_port_01/current-2026-04-14.png",
                cloud_cover=0.07,
                source="sentinel_current_stub",
            ),
            baseline_frame_id="base_demo_port_01_20250901",
            overlay_ref="fixtures/demo_port_01/overlay-2026-04-14.png",
        )
        hero_baseline_frame = FrameEnvelope(
            frame=FrameRecord(
                frame_id="base_demo_port_01_20250901",
                asset_id=hero_asset.asset_id,
                captured_at="2025-09-01T10:00:00Z",
                image_ref="fixtures/demo_port_01/baseline-2025-09-01.png",
                cloud_cover=0.03,
                source="sentinel_baseline_stub",
            ),
            baseline_frame_id=None,
            overlay_ref=None,
        )
        bridge_current_frame = FrameEnvelope(
            frame=FrameRecord(
                frame_id="cur_demo_bridge_01_20260414",
                asset_id=bridge_asset.asset_id,
                captured_at="2026-04-14T18:42:00Z",
                image_ref="fixtures/demo_bridge_01/current-2026-04-14.png",
                cloud_cover=0.05,
                source="sentinel_current_stub",
            ),
            baseline_frame_id="base_demo_bridge_01_20251012",
            overlay_ref="fixtures/demo_bridge_01/overlay-2026-04-14.png",
        )
        bridge_baseline_frame = FrameEnvelope(
            frame=FrameRecord(
                frame_id="base_demo_bridge_01_20251012",
                asset_id=bridge_asset.asset_id,
                captured_at="2025-10-12T09:15:00Z",
                image_ref="fixtures/demo_bridge_01/baseline-2025-10-12.png",
                cloud_cover=0.02,
                source="sentinel_baseline_stub",
            ),
            baseline_frame_id=None,
            overlay_ref=None,
        )

        return {
            "hero_port_disruption": ScenarioFixture(
                scenario_id="hero_port_disruption",
                asset_id=hero_asset.asset_id,
                current_frame=hero_current_frame,
                baseline_frame=hero_baseline_frame,
                alerts=[
                    Alert(
                        alert_id="blk_00017",
                        timestamp="2026-04-14T18:40:00Z",
                        asset_id=hero_asset.asset_id,
                        asset_name=hero_asset.asset_name,
                        asset_type=hero_asset.asset_type,
                        event_type="probable_large_scale_disruption",
                        severity="high",
                        confidence=0.89,
                        bbox=(0.19, 0.26, 0.73, 0.84),
                        civilian_impact="shipping_or_aid_disruption",
                        why=(
                            "Large terminal footprint change versus baseline "
                            "near bulk loading berths."
                        ),
                        action="downlink_now",
                        source=AlertSource(
                            current_frame_id=hero_current_frame.frame.frame_id,
                            baseline_frame_id=hero_baseline_frame.frame.frame_id,
                            model_version=self.settings.model_version,
                        ),
                    )
                ],
                metrics=Metrics(
                    frames_scanned=143,
                    alerts_emitted=5,
                    raw_frames_suppressed=138,
                    downlink_rate=0.035,
                ),
            ),
            "bridge_access_obstruction": ScenarioFixture(
                scenario_id="bridge_access_obstruction",
                asset_id=bridge_asset.asset_id,
                current_frame=bridge_current_frame,
                baseline_frame=bridge_baseline_frame,
                alerts=[
                    Alert(
                        alert_id="blk_00018",
                        timestamp="2026-04-14T18:42:00Z",
                        asset_id=bridge_asset.asset_id,
                        asset_name=bridge_asset.asset_name,
                        asset_type=bridge_asset.asset_type,
                        event_type="probable_access_obstruction",
                        severity="medium",
                        confidence=0.78,
                        bbox=(0.31, 0.18, 0.68, 0.71),
                        civilian_impact="public_mobility_disruption",
                        why=(
                            "Bridge deck access appears partially obstructed "
                            "versus stable baseline."
                        ),
                        action="defer",
                        source=AlertSource(
                            current_frame_id=bridge_current_frame.frame.frame_id,
                            baseline_frame_id=bridge_baseline_frame.frame.frame_id,
                            model_version=self.settings.model_version,
                        ),
                    )
                ],
                metrics=Metrics(
                    frames_scanned=88,
                    alerts_emitted=2,
                    raw_frames_suppressed=86,
                    downlink_rate=0.023,
                ),
            ),
        }
