from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from app.core.config import Settings
from app.schemas.agent import (
    AtlasAgentCompare,
    AtlasAgentPlan,
    AtlasAgentPlannerTelemetry,
    AtlasAgentQueryRequest,
    AtlasAgentQueryResponse,
    AtlasAgentResolvedRequest,
    AtlasAgentTool,
    AtlasAgentToolArgument,
    AtlasAgentToolSpec,
    AtlasAgentTrust,
)
from app.schemas.alert import Alert
from app.schemas.asset import Asset
from app.schemas.frame import FrameEnvelope
from app.schemas.health import (
    HealthConfig,
    HealthDebug,
    HealthDependency,
    HealthGatewayRecent,
    HealthResponse,
)
from app.schemas.metrics import Metrics
from app.schemas.replay import ReplayStartRequest, ReplayState
from app.services.agent_planner import (
    AgentPlannerDecision,
    FixtureAgentPlannerBackend,
    HttpAgentPlannerBackend,
    PromptedAtlasAgentPlanner,
)
from app.services.agent_prompt_builder import AgentPlannerPromptBuilder
from app.services.agent_provider import resolve_http_agent_planner_provider
from app.services.alert_pipeline import StructuredAlertPipeline
from app.services.annotated_case_loader import load_reference_cases
from app.services.baseline_compare import FixtureBaselineComparator
from app.services.frame_cache import FrameCacheLayout
from app.services.frame_client import CachedFrameClient, FixtureFrameClient
from app.services.frame_filters import FrameFilterPolicy
from app.services.frame_types import FrameRequest
from app.services.model_gateway import ModelGateway, ModelGatewayTelemetry
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


@dataclass(frozen=True)
class _WatchlistEvaluation:
    asset: Asset
    scenario: ScenarioFixture
    current_frame: FrameEnvelope
    baseline_frame: FrameEnvelope
    alerts: list[Alert]


_SEVERITY_ORDER = {"high": 3, "medium": 2, "low": 1}


class StubAtlasService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model_gateway_events: list[ModelGatewayTelemetry] = []
        self._agent_gateway_events: list[ModelGatewayTelemetry] = []
        self.assets = load_watchlist_assets(settings.watchlist_path)
        self.reference_cases = load_reference_cases()
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
        self.agent_planner = PromptedAtlasAgentPlanner(
            model_version=self.settings.agent_model_version,
            backend=self._agent_planner_backend(),
            prompt_builder=AgentPlannerPromptBuilder(),
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
            agent_backend=self._agent_backend_dependency(),
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
                agent_model_version=self.settings.agent_model_version,
                agent_http_enabled=self.settings.agent_http_enabled,
                agent_provider=self.settings.agent_provider,
            ),
            debug=self._health_debug(),
        )

    def list_assets(self) -> list[Asset]:
        return [
            asset.model_copy(
                update={
                    "evidence_available": self._asset_has_evidence(asset.asset_id),
                    "evidence_state": self._asset_evidence_state(asset.asset_id),
                }
            )
            for asset in self.assets
        ]

    def list_agent_tools(self) -> list[AtlasAgentToolSpec]:
        return [
            AtlasAgentToolSpec(
                name="latest_alerts",
                description="List the latest matching alerts, filtered by area or asset category.",
                arguments=[
                    AtlasAgentToolArgument(
                        name="area",
                        description="Optional region or asset-name fragment filter.",
                    ),
                    AtlasAgentToolArgument(
                        name="category",
                        description="Optional asset type filter.",
                    ),
                    AtlasAgentToolArgument(
                        name="limit",
                        description="Maximum number of alerts to return.",
                    ),
                ],
            ),
            AtlasAgentToolSpec(
                name="biggest_disruptions",
                description="Rank matching alerts by severity and confidence.",
                arguments=[
                    AtlasAgentToolArgument(
                        name="area",
                        description="Optional region or asset-name fragment filter.",
                    ),
                    AtlasAgentToolArgument(
                        name="category",
                        description="Optional asset type filter.",
                    ),
                    AtlasAgentToolArgument(
                        name="limit",
                        description="Maximum number of alerts to return.",
                    ),
                ],
            ),
            AtlasAgentToolSpec(
                name="site_compare",
                description="Return current-versus-baseline evidence for one watchlist site.",
                arguments=[
                    AtlasAgentToolArgument(
                        name="site_id",
                        description="Watchlist asset id to compare.",
                        required=True,
                    ),
                ],
            ),
            AtlasAgentToolSpec(
                name="explain_alert",
                description="Explain the selected or latest alert with compare evidence.",
                arguments=[
                    AtlasAgentToolArgument(
                        name="alert_id",
                        description="Optional alert id to explain.",
                    ),
                    AtlasAgentToolArgument(
                        name="selected_asset_id",
                        description="Optional selected asset fallback when alert_id is missing.",
                    ),
                ],
            ),
        ]

    def run_agent_query(self, request: AtlasAgentQueryRequest) -> AtlasAgentQueryResponse:
        resolved_request, planner = self._resolve_agent_request(request)
        tool = resolved_request.tool or self._infer_agent_tool(resolved_request.query or "")
        resolved = self._resolved_agent_request(request=resolved_request, tool=tool)
        watchlist = self._watchlist_evaluations()
        trust = self._agent_trust()
        alerts = self._filter_agent_alerts(
            alerts=[alert for evaluation in watchlist for alert in evaluation.alerts],
            area=resolved_request.area,
            category=resolved_request.category,
            limit=resolved_request.limit,
        )

        if tool == "site_compare":
            return self._site_compare_response(
                request=resolved_request,
                watchlist=watchlist,
                planner=planner,
                resolved=resolved,
                trust=trust,
            )
        if tool == "explain_alert":
            return self._explain_alert_response(
                request=resolved_request,
                watchlist=watchlist,
                alerts=alerts,
                planner=planner,
                resolved=resolved,
                trust=trust,
            )
        if tool == "biggest_disruptions":
            ranked = sorted(
                alerts,
                key=lambda alert: (
                    _SEVERITY_ORDER.get(alert.severity, 0),
                    alert.confidence,
                    alert.timestamp,
                ),
                reverse=True,
            )
            return self._agent_alert_list_response(
                tool=tool,
                alerts=ranked,
                planner=planner,
                resolved=resolved,
                trust=trust,
                no_result_summary=(
                    "No accepted disruptions match that filter. " "Watch posture remains active."
                ),
            )
        return self._agent_alert_list_response(
            tool=cast(AtlasAgentTool, "latest_alerts"),
            alerts=sorted(alerts, key=lambda alert: alert.timestamp, reverse=True),
            planner=planner,
            resolved=resolved,
            trust=trust,
            no_result_summary="No accepted alerts match that filter. Replay-safe watch continues.",
        )

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

    def _agent_alert_list_response(
        self,
        *,
        tool: AtlasAgentTool,
        alerts: list[Alert],
        planner: AtlasAgentPlannerTelemetry,
        resolved: AtlasAgentResolvedRequest,
        trust: AtlasAgentTrust,
        no_result_summary: str,
    ) -> AtlasAgentQueryResponse:
        if not alerts:
            return AtlasAgentQueryResponse(
                status="no_result",
                tool=tool,
                summary=no_result_summary,
                resolved=resolved,
                alerts=[],
                planner=planner,
                trust=trust,
                replay=self.get_replay_state(),
            )

        focus = alerts[0]
        return AtlasAgentQueryResponse(
            status="ok",
            tool=tool,
            summary=(
                f"{focus.asset_name}: {focus.why} "
                f"{humanize_tool_label(tool)} returned {len(alerts)} matching "
                f"{'alert' if len(alerts) == 1 else 'alerts'}."
            ),
            resolved=resolved,
            focus_asset_id=focus.asset_id,
            focus_alert_id=focus.alert_id,
            alerts=alerts,
            compare=self._compare_for_asset(focus.asset_id),
            planner=planner,
            trust=trust,
            replay=self.get_replay_state(),
        )

    def _site_compare_response(
        self,
        *,
        request: AtlasAgentQueryRequest,
        watchlist: list[_WatchlistEvaluation],
        planner: AtlasAgentPlannerTelemetry,
        resolved: AtlasAgentResolvedRequest,
        trust: AtlasAgentTrust,
    ) -> AtlasAgentQueryResponse:
        asset_id = request.site_id or request.selected_asset_id or self.hero_asset.asset_id
        asset = self._find_asset(asset_id)
        if asset is None:
            return AtlasAgentQueryResponse(
                status="no_result",
                tool="site_compare",
                summary="Selected site is not on the current watchlist.",
                resolved=resolved,
                planner=planner,
                trust=trust,
                replay=self.get_replay_state(),
            )

        compare = self._compare_for_asset(asset.asset_id, watchlist=watchlist)
        alerts = self._alerts_for_asset(asset.asset_id, watchlist=watchlist)
        if compare is None:
            return AtlasAgentQueryResponse(
                status="no_result",
                tool="site_compare",
                summary="No compare evidence is loaded yet for this watchlist site.",
                resolved=resolved,
                focus_asset_id=asset.asset_id,
                planner=planner,
                trust=trust,
                replay=self.get_replay_state(),
            )
        evidence_state = self._asset_evidence_state(asset.asset_id)
        current = compare.current_frame
        if evidence_state == "reference_event":
            summary = (
                f"{asset.asset_name}: reference event evidence from "
                f"{format_agent_timestamp(current.frame.captured_at)} versus baseline "
                f"{format_agent_timestamp(compare.baseline_frame.frame.captured_at)}."
            )
        elif evidence_state == "reference_control":
            summary = (
                f"{asset.asset_name}: reference control from "
                f"{format_agent_timestamp(current.frame.captured_at)} versus baseline "
                f"{format_agent_timestamp(compare.baseline_frame.frame.captured_at)}. "
                f"No material change."
            )
        else:
            baseline_timestamp = format_agent_timestamp(compare.baseline_frame.frame.captured_at)
            overlay_state = "Overlay ready." if current.overlay_ref else "Overlay held."
            summary = (
                f"{asset.asset_name}: current {format_agent_timestamp(current.frame.captured_at)} "
                f"versus baseline {baseline_timestamp}. "
                f"{overlay_state}"
            )
        return AtlasAgentQueryResponse(
            status="ok",
            tool="site_compare",
            summary=summary,
            resolved=resolved,
            focus_asset_id=asset.asset_id,
            focus_alert_id=alerts[0].alert_id if alerts else None,
            alerts=alerts,
            compare=compare,
            planner=planner,
            trust=trust,
            replay=self.get_replay_state(),
        )

    def _explain_alert_response(
        self,
        *,
        request: AtlasAgentQueryRequest,
        watchlist: list[_WatchlistEvaluation],
        alerts: list[Alert],
        planner: AtlasAgentPlannerTelemetry,
        resolved: AtlasAgentResolvedRequest,
        trust: AtlasAgentTrust,
    ) -> AtlasAgentQueryResponse:
        target_alert = self._resolve_alert_target(
            alert_id=request.alert_id,
            selected_asset_id=request.selected_asset_id or request.site_id,
            filtered_alerts=alerts,
            watchlist=watchlist,
        )
        if target_alert is None:
            return AtlasAgentQueryResponse(
                status="no_result",
                tool="explain_alert",
                summary="No accepted alert is available to explain on the current watchlist.",
                resolved=resolved,
                planner=planner,
                trust=trust,
                replay=self.get_replay_state(),
            )

        compare = self._compare_for_asset(target_alert.asset_id, watchlist=watchlist)
        return AtlasAgentQueryResponse(
            status="ok",
            tool="explain_alert",
            summary=(
                f"{target_alert.asset_name}: {target_alert.why} "
                f"Action is {target_alert.action.replace('_', ' ')} at "
                f"{round(target_alert.confidence * 100)}% confidence."
            ),
            resolved=resolved,
            focus_asset_id=target_alert.asset_id,
            focus_alert_id=target_alert.alert_id,
            alerts=[target_alert],
            compare=compare,
            planner=planner,
            trust=trust,
            replay=self.get_replay_state(),
        )

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

    def _agent_backend_dependency(self) -> HealthDependency:
        if not self.settings.agent_http_enabled:
            return HealthDependency(
                status="ready",
                detail=f"{self.settings.agent_model_version} (fixture planner)",
            )
        if not self.settings.agent_endpoint:
            return HealthDependency(
                status="not_configured",
                detail="agent planner endpoint not configured yet",
            )
        provider = resolve_http_agent_planner_provider(self.settings.agent_provider)
        if provider is None:
            return HealthDependency(
                status="degraded",
                detail=f"{self.settings.agent_provider} unsupported; fixture planner active",
            )
        return HealthDependency(
            status="ready",
            detail=(
                f"{self.settings.agent_model_version} " f"({provider.provider_id} http planner)"
            ),
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
                gateway=ModelGateway(telemetry_sink=self._model_gateway_events),
            )
        return FixtureRawCandidateBackend()

    def _agent_planner_backend(self):
        provider = resolve_http_agent_planner_provider(self.settings.agent_provider)
        if (
            self.settings.agent_http_enabled
            and self.settings.agent_endpoint
            and provider is not None
        ):
            return HttpAgentPlannerBackend(
                endpoint=self.settings.agent_endpoint,
                provider=provider,
                api_key=self.settings.agent_api_key,
                gateway=ModelGateway(telemetry_sink=self._agent_gateway_events),
            )
        return FixtureAgentPlannerBackend()

    def _health_debug(self) -> HealthDebug | None:
        model_recent = self._recent_gateway_event(self._model_gateway_events)
        agent_recent = self._recent_gateway_event(self._agent_gateway_events)
        if model_recent is None and agent_recent is None:
            return None
        return HealthDebug(model_recent=model_recent, agent_recent=agent_recent)

    def _recent_gateway_event(
        self,
        events: list[ModelGatewayTelemetry],
    ) -> HealthGatewayRecent | None:
        if not events:
            return None
        recent = events[-1]
        return HealthGatewayRecent(
            model_version=recent.model_version,
            provider_id=recent.provider_id,
            latency_ms=recent.latency_ms,
            cache_hit=recent.cache_hit,
            parse_ok=recent.parse_ok,
            seen_at=recent.seen_at,
            fallback_reason=recent.fallback_reason,
        )

    def _evaluate_active_scenario(self):
        scenario = self._active_scenario()
        return self._evaluate_scenario(scenario)

    def _evaluate_scenario(self, scenario: ScenarioFixture):
        request = FrameRequest(asset_id=scenario.asset_id, scenario_id=scenario.scenario_id)
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

    def _watchlist_evaluations(self) -> list[_WatchlistEvaluation]:
        evaluations: list[_WatchlistEvaluation] = []
        for scenario in self.scenarios.values():
            evaluated = self._evaluate_scenario(scenario)
            evaluations.append(
                _WatchlistEvaluation(
                    asset=self._asset_by_id(scenario.asset_id),
                    scenario=scenario,
                    current_frame=evaluated.current_frame,
                    baseline_frame=evaluated.baseline_frame,
                    alerts=evaluated.alerts,
                )
            )
        return evaluations

    def _compare_for_asset(
        self,
        asset_id: str,
        *,
        watchlist: list[_WatchlistEvaluation] | None = None,
    ) -> AtlasAgentCompare | None:
        evaluation = next(
            (
                item
                for item in (watchlist or self._watchlist_evaluations())
                if item.asset.asset_id == asset_id
            ),
            None,
        )
        if evaluation is None:
            reference_case = self._reference_case_for_asset(asset_id)
            if reference_case is None:
                return None
            return AtlasAgentCompare(
                asset_id=reference_case.asset.asset_id,
                asset_name=reference_case.asset.asset_name,
                current_frame=self._reference_current_frame(reference_case),
                baseline_frame=reference_case.baseline_frame,
            )
        return AtlasAgentCompare(
            asset_id=evaluation.asset.asset_id,
            asset_name=evaluation.asset.asset_name,
            current_frame=evaluation.current_frame,
            baseline_frame=evaluation.baseline_frame,
        )

    def _resolved_agent_request(
        self,
        *,
        request: AtlasAgentQueryRequest,
        tool: AtlasAgentTool,
    ) -> AtlasAgentResolvedRequest:
        effective_site_id = request.site_id
        if effective_site_id is None and tool in {"site_compare", "explain_alert"}:
            effective_site_id = request.selected_asset_id

        return AtlasAgentResolvedRequest(
            tool=tool,
            area=request.area,
            category=request.category,
            site_id=effective_site_id,
            alert_id=request.alert_id,
            selected_asset_id=request.selected_asset_id,
            limit=request.limit,
        )

    def _alerts_for_asset(
        self,
        asset_id: str,
        *,
        watchlist: list[_WatchlistEvaluation] | None = None,
    ) -> list[Alert]:
        for evaluation in watchlist or self._watchlist_evaluations():
            if evaluation.asset.asset_id == asset_id:
                return evaluation.alerts
        reference_case = self._reference_case_for_asset(asset_id)
        if reference_case and reference_case.expected_action != "discard":
            return [reference_case.expected_alert]
        return []

    def _asset_has_evidence(self, asset_id: str) -> bool:
        return (
            asset_id in {scenario.asset_id for scenario in self.scenarios.values()}
            or asset_id in self.reference_cases
        )

    def _asset_evidence_state(self, asset_id: str) -> str:
        if asset_id in {scenario.asset_id for scenario in self.scenarios.values()}:
            return "live_demo"
        reference_case = self._reference_case_for_asset(asset_id)
        if reference_case is None:
            return "watch_only"
        if reference_case.expected_action == "discard":
            return "reference_control"
        return "reference_event"

    def _reference_case_for_asset(self, asset_id: str):
        return self.reference_cases.get(asset_id)

    def _reference_current_frame(self, case) -> FrameEnvelope:
        accepted_for_alerting = case.expected_action != "discard"
        filter_reason = "reference_event" if accepted_for_alerting else "reference_control"
        return case.current_frame.model_copy(
            update={
                "accepted_for_alerting": accepted_for_alerting,
                "filter_reason": filter_reason,
            }
        )

    def _filter_agent_alerts(
        self,
        *,
        alerts: list[Alert],
        area: str | None,
        category: str | None,
        limit: int,
    ) -> list[Alert]:
        filtered = alerts
        if area:
            area_lower = area.lower()
            filtered = [
                alert
                for alert in filtered
                if area_lower in alert.asset_name.lower()
                or area_lower in self._asset_by_id(alert.asset_id).region.lower()
            ]
        if category:
            filtered = [alert for alert in filtered if alert.asset_type == category]
        return filtered[:limit]

    def _resolve_alert_target(
        self,
        *,
        alert_id: str | None,
        selected_asset_id: str | None,
        filtered_alerts: list[Alert],
        watchlist: list[_WatchlistEvaluation],
    ) -> Alert | None:
        if alert_id:
            for alert in filtered_alerts:
                if alert.alert_id == alert_id:
                    return alert
            for evaluation in watchlist:
                for alert in evaluation.alerts:
                    if alert.alert_id == alert_id:
                        return alert

        if selected_asset_id:
            selected_alerts = self._alerts_for_asset(selected_asset_id, watchlist=watchlist)
            if selected_alerts:
                return selected_alerts[0]
            if self._find_asset(selected_asset_id) is not None:
                return None

        if filtered_alerts:
            return filtered_alerts[0]

        all_alerts = [alert for evaluation in watchlist for alert in evaluation.alerts]
        if not all_alerts:
            return None
        return sorted(
            all_alerts,
            key=lambda alert: alert.timestamp,
            reverse=True,
        )[0]

    def _resolve_agent_request(
        self,
        request: AtlasAgentQueryRequest,
    ) -> tuple[AtlasAgentQueryRequest, AtlasAgentPlannerTelemetry]:
        if request.tool or not request.query:
            return (
                request.model_copy(
                    update={
                        "area": request.area or self._infer_area(request.query or ""),
                        "category": request.category or self._infer_category(request.query or ""),
                    }
                ),
                AtlasAgentPlannerTelemetry(
                    mode="deterministic",
                    detail="Explicit tool path bypassed planner.",
                    reason="explicit_tool",
                ),
            )

        fallback_plan = AtlasAgentPlan(
            tool=self._infer_agent_tool(request.query),
            area=request.area or self._infer_area(request.query),
            category=request.category or self._infer_category(request.query),
            site_id=request.site_id,
            alert_id=request.alert_id,
        )
        if not self.settings.agent_http_enabled:
            return (
                request.model_copy(
                    update={
                        "tool": fallback_plan.tool,
                        "area": request.area or fallback_plan.area,
                        "category": request.category or fallback_plan.category,
                        "site_id": request.site_id or fallback_plan.site_id,
                        "alert_id": request.alert_id or fallback_plan.alert_id,
                    }
                ),
                AtlasAgentPlannerTelemetry(
                    mode="deterministic",
                    detail="Fixture planner routed this command.",
                    reason="fixture_planner",
                ),
            )
        if not self.settings.agent_endpoint:
            return (
                request.model_copy(
                    update={
                        "tool": fallback_plan.tool,
                        "area": request.area or fallback_plan.area,
                        "category": request.category or fallback_plan.category,
                        "site_id": request.site_id or fallback_plan.site_id,
                        "alert_id": request.alert_id or fallback_plan.alert_id,
                    }
                ),
                AtlasAgentPlannerTelemetry(
                    mode="fallback",
                    detail="Planner endpoint missing; deterministic fallback active.",
                    reason="planner_not_configured",
                ),
            )
        if resolve_http_agent_planner_provider(self.settings.agent_provider) is None:
            return (
                request.model_copy(
                    update={
                        "tool": fallback_plan.tool,
                        "area": request.area or fallback_plan.area,
                        "category": request.category or fallback_plan.category,
                        "site_id": request.site_id or fallback_plan.site_id,
                        "alert_id": request.alert_id or fallback_plan.alert_id,
                    }
                ),
                AtlasAgentPlannerTelemetry(
                    mode="fallback",
                    detail="Planner provider unsupported; deterministic fallback active.",
                    reason="planner_unsupported_provider",
                ),
            )
        selected_asset = self._find_asset(request.selected_asset_id)
        decision = self.agent_planner.plan(
            query=request.query,
            assets=self.assets,
            selected_asset=selected_asset,
            fallback_plan=fallback_plan,
        )
        plan = self._sanitized_planner_plan(decision.plan, request=request)
        return (
            request.model_copy(
                update={
                    "tool": plan.tool,
                    "area": request.area or plan.area,
                    "category": request.category or plan.category,
                    "site_id": self._resolved_planner_site_id(request, plan),
                    "alert_id": request.alert_id or plan.alert_id,
                }
            ),
            self._planner_telemetry(decision),
        )

    def _planner_telemetry(self, decision: AgentPlannerDecision) -> AtlasAgentPlannerTelemetry:
        if decision.mode == "live":
            return AtlasAgentPlannerTelemetry(
                mode="live",
                detail="Live planner routed this command.",
            )

        detail_by_reason = {
            "planner_http_failed": "Planner request failed; deterministic fallback active.",
            "planner_invalid_json": "Planner output invalid; deterministic fallback active.",
        }
        return AtlasAgentPlannerTelemetry(
            mode="fallback",
            detail=detail_by_reason.get(
                decision.reason,
                "Deterministic planner fallback active.",
            ),
            reason=decision.reason,
        )

    def _resolved_planner_site_id(
        self,
        request: AtlasAgentQueryRequest,
        plan: AtlasAgentPlan,
    ) -> str | None:
        if request.site_id or plan.site_id:
            return request.site_id or plan.site_id
        if request.selected_asset_id:
            return request.selected_asset_id
        if plan.tool not in {"site_compare", "explain_alert"}:
            return None

        candidates = self._site_candidates(
            query=request.query or "",
            area=request.area or plan.area,
            category=request.category or plan.category,
        )
        if len(candidates) == 1:
            return candidates[0].asset_id
        return None

    def _site_candidates(
        self,
        *,
        query: str,
        area: str | None,
        category: str | None,
    ) -> list[Asset]:
        area_lower = area.lower() if area else None
        query_lower = query.lower()

        candidates = self.assets
        if area_lower:
            matched = [
                asset
                for asset in candidates
                if area_lower in asset.asset_name.lower() or area_lower in asset.region.lower()
            ]
            if matched:
                candidates = matched

        if category:
            matched = [asset for asset in candidates if asset.asset_type == category]
            if matched:
                candidates = matched

        if len(candidates) == 1:
            return candidates

        query_matches = [
            asset
            for asset in candidates
            if asset.asset_name.lower() in query_lower
            or asset.region.lower() in query_lower
            or asset.asset_type in query_lower
            or asset.asset_type.replace("_", " ") in query_lower
        ]
        if query_matches:
            return query_matches
        return candidates

    def _sanitized_planner_plan(
        self,
        plan: AtlasAgentPlan,
        *,
        request: AtlasAgentQueryRequest,
    ) -> AtlasAgentPlan:
        area = self._canonical_area(plan.area)
        category = self._canonical_category(plan.category)
        if request.category is None and category is not None:
            if not self._query_mentions_category(request.query or "", category):
                category = None
        site_id = plan.site_id if self._find_asset(plan.site_id) is not None else None
        alert_id = plan.alert_id if request.alert_id else None
        return plan.model_copy(
            update={
                "area": area,
                "category": category,
                "site_id": site_id,
                "alert_id": alert_id,
            }
        )

    def _canonical_area(self, area: str | None) -> str | None:
        if not area:
            return None
        area_lower = area.lower()
        for asset in self.assets:
            if asset.asset_name.lower() == area_lower:
                return asset.asset_name
            if asset.region.lower() == area_lower:
                return asset.region
        return None

    def _canonical_category(self, category: str | None) -> str | None:
        if not category:
            return None
        category_lower = category.lower()
        known = {asset.asset_type for asset in self.assets}
        return next((value for value in known if value == category_lower), None)

    def _query_mentions_category(self, query: str, category: str) -> bool:
        lowered = query.lower()
        if category in lowered or category.replace("_", " ") in lowered:
            return True
        category_tokens = {
            "bridge": {"bridge"},
            "grain_port": {"grain port", "grain terminal", "port"},
            "container_port": {"container port", "aid hub", "port"},
            "water_infrastructure": {
                "water",
                "desalination",
                "treatment plant",
                "pumping station",
                "dam",
                "reservoir",
            },
            "logistics_hub": {"logistics", "distribution", "warehouse"},
            "aid_warehouse_cluster": {"aid", "warehouse", "unhcr", "wfp", "red cross"},
            "medical_aid_node": {
                "hospital",
                "medical",
                "ambulance",
                "clinic",
                "health directorate",
                "red crescent",
                "red cross",
                "msf",
            },
        }
        return any(token in lowered for token in category_tokens.get(category, set()))

    def _infer_agent_tool(self, query: str) -> AtlasAgentTool:
        lowered = query.lower()
        if any(term in lowered for term in ("compare", "baseline")):
            return "site_compare"
        if any(term in lowered for term in ("why", "explain")):
            return "explain_alert"
        if any(term in lowered for term in ("biggest", "highest", "most severe")):
            return "biggest_disruptions"
        return "latest_alerts"

    def _infer_area(self, query: str) -> str | None:
        lowered = query.lower()
        for asset in self.assets:
            if asset.asset_name.lower() in lowered:
                return asset.asset_name
            if asset.region.lower() in lowered:
                return asset.region
        return None

    def _infer_category(self, query: str) -> str | None:
        lowered = query.lower()
        for asset in self.assets:
            if asset.asset_type.replace("_", " ") in lowered or asset.asset_type in lowered:
                return asset.asset_type
        if "bridge" in lowered:
            return "bridge"
        if "port" in lowered:
            return "grain_port"
        return None

    def _find_asset(self, asset_id: str | None) -> Asset | None:
        if asset_id is None:
            return None
        return next((asset for asset in self.assets if asset.asset_id == asset_id), None)

    def _agent_trust(self) -> AtlasAgentTrust:
        health = self.get_health()
        if "degraded" in {
            health.simsat_current.status,
            health.simsat_baseline.status,
            health.model_backend.status,
        }:
            return AtlasAgentTrust(
                mode="degraded",
                detail="live fetch degraded; cached fallback truth active",
            )
        if (
            health.config.simsat_current_http_enabled
            or health.config.simsat_baseline_http_enabled
            or health.config.model_http_enabled
        ):
            return AtlasAgentTrust(
                mode="live",
                detail="live transport enabled with deterministic policy guardrails",
            )
        return AtlasAgentTrust(
            mode="replay_safe",
            detail="fixture-backed replay-safe truth",
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


def humanize_tool_label(tool: AtlasAgentTool) -> str:
    return tool.replace("_", " ")


def format_agent_timestamp(value: str) -> str:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return timestamp.strftime("%Y-%m-%d %H:%M UTC")
