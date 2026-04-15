from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.config import Settings
from app.schemas.alert import Alert
from app.schemas.asset import Asset
from app.schemas.frame import FrameEnvelope
from app.schemas.health import HealthDependency, HealthResponse
from app.schemas.metrics import Metrics
from app.schemas.replay import ReplayStartRequest, ReplayState
from app.services.baseline_compare import FixtureBaselineComparator
from app.services.frame_cache import FrameCacheLayout
from app.services.frame_client import CachedFrameClient, FixtureFrameClient
from app.services.frame_filters import FrameFilterPolicy
from app.services.frame_types import FrameRequest
from app.services.scenario_fixtures import ScenarioFixture, build_stub_scenarios
from app.services.sentinel_client import (
    BaselineSentinelAdapter,
    ConfiguredSentinelEndpointSource,
    CurrentSentinelAdapter,
    FixtureSentinelPayloadTransport,
    FixtureSentinelSource,
    HttpSentinelPayloadTransport,
)
from app.services.watchlist_loader import load_watchlist_assets


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
        self.assets = load_watchlist_assets(settings.watchlist_path)
        self.scenarios = build_stub_scenarios(
            settings=self.settings,
            hero_asset=self.hero_asset,
            bridge_asset=self._asset_by_id("demo_bridge_01"),
        )
        self.frame_client = CachedFrameClient(
            delegate=self._frame_delegate(),
            cache_layout=FrameCacheLayout(),
        )
        self.baseline_comparator = FixtureBaselineComparator()
        self.frame_filter_policy = FrameFilterPolicy()
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
                http_enabled=self.settings.simsat_current_http_enabled,
            ),
            simsat_baseline=self._dependency_state(
                self.settings.simsat_baseline_endpoint,
                "historical baseline endpoint not configured yet",
                http_enabled=self.settings.simsat_baseline_http_enabled,
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
        self.replay.asset_id = None
        self.replay.scenario_id = None
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
        request = self._active_frame_request()
        current = self.frame_client.get_current_frame(request)
        baseline = self.frame_client.get_baseline_frame(request)
        compared = self.baseline_comparator.compare(current=current, baseline=baseline)
        decision = self.frame_filter_policy.evaluate(current=compared, baseline=baseline)

        if decision.accepted:
            return compared.model_copy(
                update={
                    "accepted_for_alerting": True,
                    "filter_reason": decision.reason,
                }
            )

        return compared.model_copy(
            update={
                "accepted_for_alerting": False,
                "filter_reason": decision.reason,
                "overlay_ref": None,
            }
        )

    def get_baseline_frame(self) -> FrameEnvelope:
        return self.frame_client.get_baseline_frame(self._active_frame_request())

    def list_alerts(self) -> list[Alert]:
        scenario = self._active_scenario()
        decision = self.frame_filter_policy.evaluate(
            current=scenario.current_frame,
            baseline=scenario.baseline_frame,
        )

        if not decision.accepted:
            return []

        return scenario.alerts

    def get_metrics(self) -> Metrics:
        scenario = self._active_scenario()
        decision = self.frame_filter_policy.evaluate(
            current=scenario.current_frame,
            baseline=scenario.baseline_frame,
        )
        emitted_alerts = max(
            scenario.metrics.alerts_emitted - (0 if decision.accepted else len(scenario.alerts)),
            0,
        )
        suppressed_frames = scenario.metrics.raw_frames_suppressed + (0 if decision.accepted else 1)

        return scenario.metrics.model_copy(
            update={
                "alerts_emitted": emitted_alerts,
                "raw_frames_suppressed": suppressed_frames,
                "downlink_rate": round(
                    emitted_alerts / scenario.metrics.frames_scanned,
                    3,
                ),
            }
        )

    def _dependency_state(
        self,
        endpoint: str | None,
        missing_detail: str,
        *,
        http_enabled: bool,
    ) -> HealthDependency:
        if endpoint:
            transport_mode = "http transport enabled" if http_enabled else "fixture transport"
            return HealthDependency(status="ready", detail=f"{endpoint} ({transport_mode})")
        return HealthDependency(status="not_configured", detail=missing_detail)

    def _asset_by_id(self, asset_id: str) -> Asset:
        for asset in self.assets:
            if asset.asset_id == asset_id:
                return asset
        return self.hero_asset

    def _active_scenario(self) -> ScenarioFixture:
        scenario_id = self.replay.scenario_id or "hero_port_disruption"
        return self.scenarios.get(scenario_id, self.scenarios["hero_port_disruption"])

    def _active_frame_request(self) -> FrameRequest:
        scenario = self._active_scenario()
        return FrameRequest(asset_id=scenario.asset_id, scenario_id=scenario.scenario_id)

    def _select_scenario(self, asset_id: str | None, scenario_id: str | None) -> ScenarioFixture:
        if scenario_id and scenario_id in self.scenarios:
            return self.scenarios[scenario_id]

        if asset_id == "demo_bridge_01":
            return self.scenarios["bridge_access_obstruction"]

        return self.scenarios["hero_port_disruption"]

    def _frame_delegate(self):
        if not self.settings.simsat_current_endpoint and not self.settings.simsat_baseline_endpoint:
            return FixtureFrameClient(self.scenarios)

        planner = ConfiguredSentinelEndpointSource(
            current_endpoint=self.settings.simsat_current_endpoint,
            baseline_endpoint=self.settings.simsat_baseline_endpoint,
        )
        fallback = FixtureSentinelSource(self.scenarios)
        fixture_transport = FixtureSentinelPayloadTransport(self.scenarios)
        current_transport = (
            HttpSentinelPayloadTransport()
            if self.settings.simsat_current_http_enabled
            else fixture_transport
        )
        baseline_transport = (
            HttpSentinelPayloadTransport()
            if self.settings.simsat_baseline_http_enabled
            else fixture_transport
        )
        return _CompositeSentinelFrameClient(
            current=CurrentSentinelAdapter(
                planner=planner,
                fallback=fallback,
                transport=current_transport,
            ),
            baseline=BaselineSentinelAdapter(
                planner=planner,
                fallback=fallback,
                transport=baseline_transport,
            ),
        )


@dataclass(frozen=True)
class _CompositeSentinelFrameClient:
    current: CurrentSentinelAdapter | FixtureFrameClient
    baseline: BaselineSentinelAdapter | FixtureFrameClient

    def get_current_frame(self, request: FrameRequest) -> FrameEnvelope:
        return self.current.get_current_frame(request)

    def get_baseline_frame(self, request: FrameRequest) -> FrameEnvelope:
        return self.baseline.get_baseline_frame(request)
