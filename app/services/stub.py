from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings
from app.schemas.alert import Alert
from app.schemas.asset import Asset
from app.schemas.frame import FrameEnvelope
from app.schemas.health import HealthConfig, HealthDependency, HealthResponse
from app.schemas.metrics import Metrics
from app.schemas.replay import ReplayStartRequest, ReplayState
from app.services.alert_pipeline import StructuredAlertPipeline
from app.services.baseline_compare import FixtureBaselineComparator
from app.services.frame_cache import FrameCacheLayout
from app.services.frame_client import CachedFrameClient, FixtureFrameClient
from app.services.frame_filters import FrameFilterPolicy
from app.services.frame_types import FrameRequest
from app.services.model_provider import resolve_http_candidate_provider
from app.services.model_wrapper import (
    FixtureRawCandidateBackend,
    HttpRawCandidateBackend,
    PromptedCandidateModel,
)
from app.services.prompt_builder import (
    CandidatePromptBuilder,
)
from app.services.scenario_evaluator import ScenarioEvaluator
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
        self.alert_pipeline = StructuredAlertPipeline(model_version=self.settings.model_version)
        self.model_wrapper = PromptedCandidateModel(
            model_version=self.settings.model_version,
            backend=self._model_backend(),
            prompt_builder=CandidatePromptBuilder(),
        )
        self.scenario_evaluator = ScenarioEvaluator(
            comparator=self.baseline_comparator,
            frame_filter_policy=self.frame_filter_policy,
            alert_pipeline=self.alert_pipeline,
            model_wrapper=self.model_wrapper,
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
        request = self._active_frame_request()
        planner = ConfiguredSentinelEndpointSource(
            current_endpoint=self.settings.simsat_current_endpoint,
            baseline_endpoint=self.settings.simsat_baseline_endpoint,
        )
        return HealthResponse(
            status="ok",
            app_env=self.settings.app_env,
            model_backend=self._model_backend_dependency(),
            simsat_current=self._dependency_state(
                self.settings.simsat_current_endpoint,
                "current Sentinel endpoint not configured yet",
                http_enabled=self.settings.simsat_current_http_enabled,
                plan=planner.build_current_plan(request),
            ),
            simsat_baseline=self._dependency_state(
                self.settings.simsat_baseline_endpoint,
                "historical baseline endpoint not configured yet",
                http_enabled=self.settings.simsat_baseline_http_enabled,
                plan=planner.build_baseline_plan(request),
            ),
            mapbox=self._mapbox_dependency_state(),
            config=HealthConfig(
                simsat_current_http_enabled=self.settings.simsat_current_http_enabled,
                simsat_baseline_http_enabled=self.settings.simsat_baseline_http_enabled,
                mapbox_context_enabled=self.settings.mapbox_context_enabled,
                model_http_enabled=self.settings.model_http_enabled,
                model_provider=self.settings.model_provider,
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
        return self._evaluate_active_scenario().current_frame

    def get_baseline_frame(self) -> FrameEnvelope:
        return self.frame_client.get_baseline_frame(self._active_frame_request())

    def list_alerts(self) -> list[Alert]:
        alerts = self._evaluate_active_scenario().alerts
        if not alerts:
            return []

        if not self.settings.mapbox_token_present or not self.settings.mapbox_context_enabled:
            return alerts

        return [self._attach_mapbox_context(alert) for alert in alerts]

    def get_metrics(self) -> Metrics:
        return self._evaluate_active_scenario().metrics

    def _dependency_state(
        self,
        endpoint: str | None,
        missing_detail: str,
        *,
        http_enabled: bool,
        plan,
    ) -> HealthDependency:
        if endpoint:
            if http_enabled and plan is not None:
                if HttpSentinelPayloadTransport().fetch(plan) is not None:
                    return HealthDependency(
                        status="ready",
                        detail=f"{endpoint} (http transport enabled)",
                    )
                return HealthDependency(
                    status="degraded",
                    detail=f"{endpoint} (http transport failed; fixture fallback active)",
                )
            transport_mode = "http transport enabled" if http_enabled else "fixture transport"
            return HealthDependency(status="ready", detail=f"{endpoint} ({transport_mode})")
        return HealthDependency(status="not_configured", detail=missing_detail)

    def _mapbox_dependency_state(self) -> HealthDependency:
        if not self.settings.mapbox_token_present:
            return HealthDependency(
                status="not_configured",
                detail="token missing; inspection context disabled",
            )
        if self.settings.mapbox_context_enabled:
            return HealthDependency(
                status="ready",
                detail="token present; inspection context enabled",
            )
        return HealthDependency(
            status="ready",
            detail="token present; inspection context disabled by config",
        )

    def _model_backend_dependency(self) -> HealthDependency:
        if not self.settings.model_http_enabled:
            return HealthDependency(
                status="ready",
                detail=f"{self.settings.model_version} (fixture backend)",
            )
        if not self.settings.model_endpoint:
            return HealthDependency(
                status="not_configured",
                detail="model endpoint not configured yet",
            )
        provider = resolve_http_candidate_provider(self.settings.model_provider)
        if provider is None:
            return HealthDependency(
                status="degraded",
                detail=f"{self.settings.model_provider} unsupported; fixture backend active",
            )
        return HealthDependency(
            status="ready",
            detail=f"{self.settings.model_version} ({provider.provider_id} http backend)",
        )

    def _attach_mapbox_context(self, alert: Alert) -> Alert:
        context_path = self._mapbox_context_path(alert)
        context_path.parent.mkdir(parents=True, exist_ok=True)
        context_path.touch(exist_ok=True)
        return alert.model_copy(update={"mapbox_context_ref": str(context_path)})

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

    def _mapbox_context_path(self, alert: Alert) -> Path:
        return Path(".cache") / "mapbox" / alert.asset_id / alert.alert_id / "context.png"

    def _model_backend(self):
        provider = resolve_http_candidate_provider(self.settings.model_provider)
        if (
            self.settings.model_http_enabled
            and self.settings.model_endpoint
            and provider is not None
        ):
            return HttpRawCandidateBackend(
                endpoint=self.settings.model_endpoint,
                provider=provider,
                api_key=self.settings.model_api_key,
            )
        return FixtureRawCandidateBackend()

    def _evaluate_active_scenario(self):
        scenario = self._active_scenario()
        request = self._active_frame_request()
        current = self.frame_client.get_current_frame(request)
        baseline = self.frame_client.get_baseline_frame(request)
        self.scenario_evaluator.frame_filter_policy = self.frame_filter_policy
        self.scenario_evaluator.model_wrapper = self.model_wrapper
        return self.scenario_evaluator.evaluate(
            asset=self._asset_by_id(scenario.asset_id),
            scenario=scenario,
            current=current,
            baseline=baseline,
        )

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
