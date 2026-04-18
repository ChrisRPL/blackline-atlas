from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from app.core.config import Settings
from app.schemas.agent import (
    AtlasAgentCompare,
    AtlasAgentPlan,
    AtlasAgentQueryRequest,
    AtlasAgentQueryResponse,
    AtlasAgentTool,
    AtlasAgentToolArgument,
    AtlasAgentToolSpec,
    AtlasAgentTrust,
)
from app.schemas.alert import Alert
from app.schemas.asset import Asset
from app.schemas.frame import FrameEnvelope
from app.schemas.health import HealthConfig, HealthDependency, HealthResponse
from app.schemas.metrics import Metrics
from app.schemas.replay import ReplayStartRequest, ReplayState
from app.services.agent_planner import (
    FixtureAgentPlannerBackend,
    HttpAgentPlannerBackend,
    PromptedAtlasAgentPlanner,
)
from app.services.agent_prompt_builder import AgentPlannerPromptBuilder
from app.services.agent_provider import resolve_http_agent_planner_provider
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
        )

    def list_assets(self) -> list[Asset]:
        return self.assets

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
        resolved_request = self._resolve_agent_request(request)
        tool = resolved_request.tool or self._infer_agent_tool(resolved_request.query or "")
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
                trust=trust,
            )
        if tool == "explain_alert":
            return self._explain_alert_response(
                request=resolved_request,
                watchlist=watchlist,
                alerts=alerts,
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
                trust=trust,
                no_result_summary=(
                    "No accepted disruptions match that filter. " "Watch posture remains active."
                ),
            )
        return self._agent_alert_list_response(
            tool=cast(AtlasAgentTool, "latest_alerts"),
            alerts=sorted(alerts, key=lambda alert: alert.timestamp, reverse=True),
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
        trust: AtlasAgentTrust,
        no_result_summary: str,
    ) -> AtlasAgentQueryResponse:
        if not alerts:
            return AtlasAgentQueryResponse(
                status="no_result",
                tool=tool,
                summary=no_result_summary,
                alerts=[],
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
            focus_asset_id=focus.asset_id,
            focus_alert_id=focus.alert_id,
            alerts=alerts,
            compare=self._compare_for_asset(focus.asset_id),
            trust=trust,
            replay=self.get_replay_state(),
        )

    def _site_compare_response(
        self,
        *,
        request: AtlasAgentQueryRequest,
        watchlist: list[_WatchlistEvaluation],
        trust: AtlasAgentTrust,
    ) -> AtlasAgentQueryResponse:
        asset_id = request.site_id or request.selected_asset_id or self.hero_asset.asset_id
        asset = self._find_asset(asset_id)
        if asset is None:
            return AtlasAgentQueryResponse(
                status="no_result",
                tool="site_compare",
                summary="Selected site is not on the current watchlist.",
                trust=trust,
                replay=self.get_replay_state(),
            )

        compare = self._compare_for_asset(asset.asset_id, watchlist=watchlist)
        alerts = self._alerts_for_asset(asset.asset_id, watchlist=watchlist)
        current = compare.current_frame
        summary = (
            f"{asset.asset_name}: current {format_agent_timestamp(current.frame.captured_at)} "
            f"versus baseline {format_agent_timestamp(compare.baseline_frame.frame.captured_at)}. "
            f"{'Overlay ready.' if current.overlay_ref else 'Overlay held.'}"
        )
        return AtlasAgentQueryResponse(
            status="ok",
            tool="site_compare",
            summary=summary,
            focus_asset_id=asset.asset_id,
            focus_alert_id=alerts[0].alert_id if alerts else None,
            alerts=alerts,
            compare=compare,
            trust=trust,
            replay=self.get_replay_state(),
        )

    def _explain_alert_response(
        self,
        *,
        request: AtlasAgentQueryRequest,
        watchlist: list[_WatchlistEvaluation],
        alerts: list[Alert],
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
            focus_asset_id=target_alert.asset_id,
            focus_alert_id=target_alert.alert_id,
            alerts=[target_alert],
            compare=compare,
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
            )
        return FixtureAgentPlannerBackend()

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
    ) -> AtlasAgentCompare:
        evaluation = next(
            item
            for item in (watchlist or self._watchlist_evaluations())
            if item.asset.asset_id == asset_id
        )
        return AtlasAgentCompare(
            asset_id=evaluation.asset.asset_id,
            asset_name=evaluation.asset.asset_name,
            current_frame=evaluation.current_frame,
            baseline_frame=evaluation.baseline_frame,
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
        return []

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

    def _resolve_agent_request(self, request: AtlasAgentQueryRequest) -> AtlasAgentQueryRequest:
        if request.tool or not request.query:
            return request.model_copy(
                update={
                    "area": request.area or self._infer_area(request.query or ""),
                    "category": request.category or self._infer_category(request.query or ""),
                }
            )

        fallback_plan = AtlasAgentPlan(
            tool=self._infer_agent_tool(request.query),
            area=request.area or self._infer_area(request.query),
            category=request.category or self._infer_category(request.query),
            site_id=request.site_id,
            alert_id=request.alert_id,
        )
        selected_asset = self._find_asset(request.selected_asset_id)
        plan = self.agent_planner.plan(
            query=request.query,
            assets=self.assets,
            selected_asset=selected_asset,
            fallback_plan=fallback_plan,
        )
        return request.model_copy(
            update={
                "tool": plan.tool,
                "area": request.area or plan.area,
                "category": request.category or plan.category,
                "site_id": request.site_id or plan.site_id,
                "alert_id": request.alert_id or plan.alert_id,
            }
        )

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
