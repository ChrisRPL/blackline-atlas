from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Literal, cast
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from app.core.config import Settings
from app.schemas.agent import (
    AtlasAgentCameraIntent,
    AtlasAgentCompare,
    AtlasAgentPlan,
    AtlasAgentPlannerTelemetry,
    AtlasAgentQueryRequest,
    AtlasAgentQueryResponse,
    AtlasAgentResolvedRequest,
    AtlasAgentTool,
    AtlasAgentToolArgument,
    AtlasAgentToolObservation,
    AtlasAgentToolSpec,
    AtlasAgentTrust,
)
from app.schemas.alert import Alert
from app.schemas.asset import Asset
from app.schemas.frame import FrameEnvelope, FrameRecord
from app.schemas.health import (
    HealthConfig,
    HealthDebug,
    HealthDependency,
    HealthGatewayRecent,
    HealthResponse,
)
from app.schemas.lead import Lead, LeadRefreshRequest, LeadRefreshResponse
from app.schemas.liquid_analyst import LiquidAnalystReport
from app.schemas.metrics import Metrics
from app.schemas.model_status import ModelStatus
from app.schemas.replay import ReplaySnapshot, ReplayStartRequest, ReplayState
from app.schemas.sam3_evidence import Sam3EvidenceReport
from app.schemas.satellite_evidence import SatelliteEvidenceAttempt, SatelliteEvidenceBundle
from app.services.acled_lead_source import DEFAULT_ACLED_COUNTRIES, parse_acled_csv_list
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
from app.services.gdelt_cloud_lead_source import (
    DEFAULT_GDELT_CLOUD_COUNTRIES,
    parse_gdelt_cloud_csv_list,
)
from app.services.lead_registry_loader import load_lead_registry
from app.services.lead_registry_refresh import (
    lead_refresh_summary,
    parse_gdelt_country_allowlist,
    refresh_lead_registry,
)
from app.services.liquid_analyst import (
    FixtureLiquidAnalystBackend,
    HttpLiquidAnalystBackend,
    LiquidAnalystService,
)
from app.services.model_gateway import ModelGateway, ModelGatewayTelemetry
from app.services.model_provider import resolve_http_candidate_provider
from app.services.model_status_catalog import build_model_status
from app.services.model_wrapper import (
    FixtureRawCandidateBackend,
    HttpRawCandidateBackend,
    PromptedCandidateModel,
)
from app.services.prompt_builder import (
    CandidatePromptBuilder,
)
from app.services.sam3_evidence import (
    FixtureSam3EvidenceBackend,
    HttpSam3EvidenceBackend,
    Sam3EvidenceService,
    source_context_for_lead,
)
from app.services.satellite_evidence_resolver import resolve_live_lead_satellite_evidence
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

_SIMSAT_LIVE_FALLBACK_WINDOW_SECONDS = 730 * 24 * 60 * 60
_MAPBOX_CONTEXT_ZOOM = 18.0
_MAPBOX_CONTEXT_SIZE = "1024x576@2x"
_MAPBOX_CONTEXT_WIDTH = 1024


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _mapbox_context_size_km(latitude: float) -> float:
    meters_per_pixel = 156543.03392 * max(math.cos(math.radians(latitude)), 0.05)
    meters_per_pixel /= 2**_MAPBOX_CONTEXT_ZOOM
    return round((meters_per_pixel * _MAPBOX_CONTEXT_WIDTH) / 1000, 2)


def _query_is_scope_refusal(lowered: str) -> bool:
    tactical_phrases = (
        "best target",
        "target list",
        "targeting",
        "strike plan",
        "attack plan",
        "where should i strike",
        "where to strike",
        "how to attack",
        "how can i attack",
        "route a convoy",
        "track troops",
        "troop movement",
        "weapons system",
        "missile launcher",
        "air defense",
        "military base",
    )
    return any(phrase in lowered for phrase in tactical_phrases)


def _query_is_refresh_intent(lowered: str) -> bool:
    return any(term in lowered for term in ("refresh", "reload", "update", "sync", "fetch"))


def _normalized_text(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").split())


def _normalized_place_text(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def _normalized_contains(text: str, term: str) -> bool:
    return f" {_normalized_place_text(term)} " in f" {text} "


_AREA_SEARCH_ALIASES = {
    "persian gulf": (
        "iran",
        "iraq",
        "kuwait",
        "bahrain",
        "qatar",
        "united arab emirates",
        "uae",
        "oman",
        "saudi arabia",
    ),
    "sahel": (
        "mali",
        "niger",
        "burkina faso",
        "chad",
        "sudan",
        "nigeria",
        "western africa",
    ),
    "red sea": (
        "red sea state",
        "sudan",
        "yemen",
        "eritrea",
        "djibouti",
        "egypt",
        "saudi arabia",
    ),
}


def _area_search_terms(area: str) -> list[str]:
    normalized = _normalized_place_text(area)
    if not normalized:
        return []
    aliases = _AREA_SEARCH_ALIASES.get(normalized, ())
    return list(dict.fromkeys([normalized, *(_normalized_place_text(alias) for alias in aliases)]))


def _fallback_area_from_query_text(query: str) -> str | None:
    text = " ".join(query.replace("/", " ").strip().strip("?.!").split())
    if not text:
        return None

    patterns = (
        r"\b(?:in|near|around|inside|over|from|for|on)\s+([a-zA-Z][a-zA-Z' -]{2,80})",
        r"\b(?:show|focus|open|center|centre)\s+([a-zA-Z][a-zA-Z' -]{2,80})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        area = _clean_fallback_area(match.group(1))
        if area:
            return area
    return None


def _clean_fallback_area(value: str) -> str | None:
    area = re.split(
        r"\b(?:and|or|then|with|where|what|when|recently|today|now|last|latest|this|please|to|should|can|could)\b",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    area = area.strip(" ,.;:!?")
    if area.lower().startswith("the "):
        area = area[4:].strip()
    if len(area) < 3:
        return None
    return area.title() if area.islower() else area


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
_CATEGORY_QUERY_ALIASES = {
    "aid_corridor_node": ("aid corridor", "humanitarian corridor"),
    "aid_shelter_campus": ("aid shelter", "shelter", "camp", "idp"),
    "aid_warehouse_cluster": ("aid warehouse", "warehouse"),
    "bridge": ("bridge", "crossing"),
    "civilian_building_cluster": (
        "building",
        "buildings",
        "residential",
        "neighborhood",
        "civilian district",
    ),
    "container_port": ("container port", "port"),
    "grain_port": ("grain port", "port"),
    "grain_storage_complex": ("grain storage", "grain silo", "silo"),
    "logistics_hub": ("logistics", "hub"),
    "medical_aid_node": ("hospital", "medical", "clinic"),
    "rail_yard": ("rail", "railway", "train"),
    "road_access_corridor": ("road", "route", "access corridor"),
    "water_infrastructure": ("dam", "water", "filtration", "reservoir"),
}
_SATELLITE_DAMAGE_TERMS = (
    "blast",
    "burned",
    "burning",
    "collapsed",
    "crater",
    "damage",
    "damaged",
    "damages",
    "destroy",
    "destroyed",
    "explosion",
    "impact site",
    "rubble",
)
_SATELLITE_STRUCTURE_TERMS = (
    "apartment",
    "bridge",
    "building",
    "factory",
    "hospital",
    "infrastructure",
    "market",
    "plant",
    "port",
    "power",
    "rail",
    "refinery",
    "road",
    "school",
    "warehouse",
    "water",
)
_SATELLITE_ATTACK_TERMS = (
    "airstrike",
    "bombardment",
    "drone attack",
    "hit",
    "missile",
    "shelling",
    "strike",
)
_SOURCE_ONLY_EVENT_TERMS = (
    "ambush",
    "arrest",
    "assassinated",
    "casualties",
    "clash",
    "crossfire",
    "dies",
    "fighter",
    "fighters",
    "gunned down",
    "injured",
    "killed",
    "militant",
    "operation",
    "peacekeeper",
    "rebel",
    "soldier",
    "troop",
    "wounded",
)


class StubAtlasService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model_gateway_events: list[ModelGatewayTelemetry] = []
        self._agent_gateway_events: list[ModelGatewayTelemetry] = []
        self._analyst_gateway_events: list[ModelGatewayTelemetry] = []
        self._agent_planner_lock = Lock()
        self.assets = load_watchlist_assets(settings.watchlist_path)
        self._lead_registry_runtime_path = settings.lead_registry_path
        self.leads = load_lead_registry(self._lead_registry_runtime_path)
        self.reference_cases = load_reference_cases()
        self.scenarios = build_stub_scenarios(
            settings=self.settings,
            hero_asset=self.hero_asset,
            bridge_asset=self._asset_by_id("demo_bridge_01"),
        )
        self.frame_client = CachedFrameClient(
            delegate=self._frame_delegate(),
            cache_layout=FrameCacheLayout(),
            cache_namespace=self._frame_cache_namespace(),
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
        self.sam3_evidence = Sam3EvidenceService(
            model_version=self.settings.sam3_model_version,
            backend=self._sam3_backend(),
        )
        self.liquid_analyst = LiquidAnalystService(
            model_version=self.settings.analyst_model_version,
            backend=self._analyst_backend(),
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
            sam3_backend=self._sam3_backend_dependency(),
            analyst_backend=self._analyst_backend_dependency(),
            simsat_current=self._dependency_state(
                self.settings.simsat_current_endpoint,
                "current Sentinel endpoint not configured yet",
                http_enabled=self.settings.simsat_current_http_enabled,
                required=self.settings.simsat_required,
                plan=planner.build_current_plan(request),
            ),
            simsat_baseline=self._dependency_state(
                self.settings.simsat_baseline_endpoint,
                "historical baseline endpoint not configured yet",
                http_enabled=self.settings.simsat_baseline_http_enabled,
                required=self.settings.simsat_required,
                plan=planner.build_baseline_plan(request),
            ),
            mapbox=self._mapbox_dependency_state(),
            config=HealthConfig(
                simsat_current_http_enabled=self.settings.simsat_current_http_enabled,
                simsat_baseline_http_enabled=self.settings.simsat_baseline_http_enabled,
                simsat_required=self.settings.simsat_required,
                mapbox_context_enabled=self.settings.mapbox_context_enabled,
                model_http_enabled=self.settings.model_http_enabled,
                model_provider=self.settings.model_provider,
                agent_model_version=self.settings.agent_model_version,
                agent_http_enabled=self.settings.agent_http_enabled,
                agent_provider=self.settings.agent_provider,
                sam3_model_version=self.settings.sam3_model_version,
                sam3_http_enabled=self.settings.sam3_http_enabled,
                sam3_required=self.settings.sam3_required,
                analyst_model_version=self.settings.analyst_model_version,
                analyst_http_enabled=self.settings.analyst_http_enabled,
                analyst_provider=self.settings.analyst_provider,
            ),
            debug=self._health_debug(),
        )

    def get_model_status(self) -> ModelStatus:
        return build_model_status()

    def list_assets(self) -> list[Asset]:
        self._reload_leads()
        return [
            asset.model_copy(
                update={
                    "evidence_available": self._asset_has_evidence(asset.asset_id),
                    "evidence_state": self._asset_evidence_state(asset.asset_id),
                }
            )
            for asset in self._runtime_assets()
        ]

    def list_leads(self) -> list[Lead]:
        self._reload_leads()
        return [self._lead_with_runtime_link(lead) for lead in self.leads]

    def refresh_leads(self, request: LeadRefreshRequest) -> LeadRefreshResponse:
        output_path = self._lead_refresh_output_path()
        source_mode = self._resolved_lead_refresh_source_mode(request.source_mode)
        leads, reachable_count = self._refresh_leads_from_source(
            request=request,
            output_path=output_path,
            source_mode=source_mode,
        )
        if request.source_mode == "auto" and source_mode in {"acled", "gdelt_cloud"} and not leads:
            source_mode = "gdelt"
            leads, reachable_count = self._refresh_leads_from_source(
                request=request,
                output_path=output_path,
                source_mode=source_mode,
            )
        if not request.dry_run and (leads or source_mode not in {"acled", "gdelt", "gdelt_cloud"}):
            self._lead_registry_runtime_path = output_path
            self.leads = leads

        summary = lead_refresh_summary(
            leads=leads,
            reachable_count=reachable_count,
            output_path=output_path,
            dry_run=request.dry_run,
        )
        return LeadRefreshResponse(
            source_mode=source_mode,
            leads=[self._lead_with_runtime_link(lead) for lead in leads],
            **summary,
        )

    def list_agent_tools(self) -> list[AtlasAgentToolSpec]:
        return [
            AtlasAgentToolSpec(
                name="answer",
                description=(
                    "Answer capability, status, or usage questions without changing map focus."
                ),
                arguments=[],
            ),
            AtlasAgentToolSpec(
                name="scope_refusal",
                description=(
                    "Refuse tactical, targeting, troop, weapon, or attack-support requests."
                ),
                arguments=[],
            ),
            AtlasAgentToolSpec(
                name="search_live_leads",
                description=(
                    "Search current conflict and disruption source markers, summarize "
                    "matching leads, and emit camera focus for the map."
                ),
                arguments=[
                    AtlasAgentToolArgument(
                        name="area",
                        description="Optional region, country, city, or lead-title filter.",
                    ),
                    AtlasAgentToolArgument(
                        name="category",
                        description="Optional civilian infrastructure category filter.",
                    ),
                    AtlasAgentToolArgument(
                        name="limit",
                        description="Maximum number of source leads to return.",
                    ),
                ],
            ),
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
                description=(
                    "Return current-versus-baseline evidence for one watchlist site "
                    "or linked live lead."
                ),
                arguments=[
                    AtlasAgentToolArgument(
                        name="site_id",
                        description="Asset id to compare.",
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
                    AtlasAgentToolArgument(
                        name="selected_lead_id",
                        description="Optional selected lead marker when no asset is focused.",
                    ),
                ],
            ),
            AtlasAgentToolSpec(
                name="refresh_live_leads",
                description=(
                    "Refresh live conflict and disruption lead markers, then return the "
                    "updated registry for map rendering."
                ),
                arguments=[
                    AtlasAgentToolArgument(
                        name="area",
                        description=(
                            "Optional region or lead-title fragment to focus after refresh."
                        ),
                    ),
                    AtlasAgentToolArgument(
                        name="limit",
                        description="Maximum number of focused lead markers to highlight.",
                    ),
                ],
            ),
        ]

    def run_agent_query(self, request: AtlasAgentQueryRequest) -> AtlasAgentQueryResponse:
        self._reload_leads()
        resolved_request, planner = self._resolve_agent_request(request)
        tool = resolved_request.tool or "answer"
        resolved = self._resolved_agent_request(request=resolved_request, tool=tool)
        selected_lead = self._find_lead(resolved_request.selected_lead_id)
        if tool == "scope_refusal":
            return self._agent_answer_response(
                tool="scope_refusal",
                status="no_result",
                summary=(
                    "I cannot help with targeting, strike planning, troop tracking, weapons, "
                    "or tactical movement. I can help with civilian disruption awareness: "
                    "live conflict source leads, selected-point satellite evidence, and "
                    "humanitarian infrastructure triage."
                ),
                planner=planner,
                resolved=resolved,
                trust=self._agent_trust(),
            )
        if tool == "answer":
            return self._agent_answer_response(
                tool="answer",
                status="ok" if planner.mode == "live" else "no_result",
                summary=self._agent_answer_summary(
                    planner=planner,
                    query=resolved_request.query or request.query,
                ),
                planner=planner,
                resolved=resolved,
                trust=self._agent_trust(),
            )
        trust = self._agent_trust()

        if tool == "refresh_live_leads":
            return self._refresh_live_leads_response(
                query=resolved_request.query or request.query or "",
                planner=planner,
                resolved=resolved,
                trust=trust,
            )
        if tool == "search_live_leads":
            return self._search_live_leads_response(
                query=resolved_request.query or request.query or "",
                planner=planner,
                resolved=resolved,
                trust=trust,
            )
        skip_watchlist = (
            tool == "site_compare"
            and selected_lead is not None
            and not selected_lead.linked_asset_id
            and not resolved_request.selected_asset_id
            and not resolved_request.site_id
        )
        watchlist = [] if skip_watchlist else self._watchlist_evaluations()
        alerts = self._filter_agent_alerts(
            alerts=[alert for evaluation in watchlist for alert in evaluation.alerts],
            area=resolved.area,
            category=resolved.category,
            limit=resolved.limit,
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
                    "No confirmed satellite disruptions match that filter. "
                    "Search live source leads or refresh the feed for current regional reports."
                ),
            )
        return self._agent_alert_list_response(
            tool=cast(AtlasAgentTool, "latest_alerts"),
            alerts=sorted(alerts, key=lambda alert: alert.timestamp, reverse=True),
            planner=planner,
            resolved=resolved,
            trust=trust,
            no_result_summary=(
                "No confirmed satellite alerts match that filter. "
                "Search live source leads or refresh the feed for current regional reports."
            ),
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

    def get_replay_snapshot(self) -> ReplaySnapshot:
        evaluated = self._evaluate_active_scenario()
        alerts = evaluated.alerts
        if alerts and self.settings.mapbox_token_present and self.settings.mapbox_context_enabled:
            alerts = [self._attach_mapbox_context(alert) for alert in alerts]
        return ReplaySnapshot(
            replay=self.get_replay_state(),
            current_frame=evaluated.current_frame,
            baseline_frame=evaluated.baseline_frame,
            alerts=alerts,
            metrics=evaluated.metrics,
        )

    def get_current_evidence(self) -> Sam3EvidenceReport:
        evaluated = self._evaluate_active_scenario()
        asset = self._asset_by_id(evaluated.current_frame.frame.asset_id)
        alert = evaluated.alerts[0] if evaluated.alerts else None
        return self.sam3_evidence.analyze(
            asset=asset,
            current=evaluated.current_frame,
            baseline=evaluated.baseline_frame,
            alert=alert,
        )

    def get_asset_evidence(self, asset_id: str) -> Sam3EvidenceReport | None:
        scenario = next(
            (item for item in self.scenarios.values() if item.asset_id == asset_id),
            None,
        )
        if scenario is not None:
            evaluated = self._evaluate_scenario(scenario)
            alert = evaluated.alerts[0] if evaluated.alerts else None
            return self.sam3_evidence.analyze(
                asset=self._asset_by_id(asset_id),
                current=evaluated.current_frame,
                baseline=evaluated.baseline_frame,
                alert=alert,
            )

        reference_case = self._reference_case_for_asset(asset_id)
        if reference_case is None:
            lead = self._lead_for_asset_id(asset_id)
            if lead is None:
                return None
            compare = self._live_lead_compare(lead)
            if compare is None:
                return None
            if not self._compare_usable_for_model_evidence(compare):
                return None
            if not self._live_model_evidence_backend_ready():
                return None
            asset = self._find_asset(asset_id)
            if asset is None:
                return None
            return self.sam3_evidence.analyze(
                asset=asset,
                current=compare.current_frame,
                baseline=compare.baseline_frame,
                alert=None,
                source_context=source_context_for_lead(lead),
            )
        alert = (
            reference_case.expected_alert if reference_case.expected_action != "discard" else None
        )
        return self.sam3_evidence.analyze(
            asset=reference_case.asset,
            current=self._reference_current_frame(reference_case),
            baseline=reference_case.baseline_frame,
            alert=alert,
        )

    def get_asset_analyst_report(self, asset_id: str) -> LiquidAnalystReport | None:
        compare = self._compare_for_asset(asset_id)
        return self._analyst_report_for_compare(
            asset_id=asset_id,
            compare=compare,
            alerts=self._alerts_for_asset(asset_id),
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

    def _agent_answer_response(
        self,
        *,
        tool: AtlasAgentTool,
        status: Literal["ok", "no_result"],
        summary: str,
        planner: AtlasAgentPlannerTelemetry,
        resolved: AtlasAgentResolvedRequest,
        trust: AtlasAgentTrust,
    ) -> AtlasAgentQueryResponse:
        return AtlasAgentQueryResponse(
            status=status,
            tool=tool,
            summary=summary,
            resolved=resolved,
            observations=[
                AtlasAgentToolObservation(
                    tool=tool,
                    status=status,
                    summary="Answered without invoking evidence or alert tools.",
                )
            ],
            planner=planner,
            trust=trust,
            replay=self.get_replay_state(),
        )

    def _agent_answer_summary(
        self,
        *,
        planner: AtlasAgentPlannerTelemetry,
        query: str | None,
    ) -> str:
        _ = query
        return (
            "Atlas can refresh live conflict/disruption leads, focus the globe on a country "
            "or city, summarize source reports, request current-versus-baseline satellite "
            "evidence for a selected marker, and explain civilian triage decisions."
        )

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
            matching_leads = self._lead_matches_for_request(resolved)
            response_leads = [self._lead_with_runtime_link(lead) for lead in matching_leads]
            focus_lead = (
                response_leads[0]
                if len(response_leads) == 1
                else self._find_lead(resolved.selected_lead_id)
            )
            if focus_lead is not None:
                focus_lead = self._lead_with_runtime_link(focus_lead)
            status = "no_result"
            summary = no_result_summary
            if response_leads:
                status = "ok"
                lead_scope = f" near {resolved.area}" if resolved.area else ""
                lead_titles = "; ".join(
                    f"{lead.title} ({lead.region})" for lead in response_leads[:3]
                )
                summary = (
                    f"I found {len(response_leads)} live source "
                    f"{'lead' if len(response_leads) == 1 else 'leads'}{lead_scope}: "
                    f"{lead_titles}. These are source markers, not confirmed satellite alerts yet. "
                    "Click a marker or ask for current versus baseline evidence to review it."
                )
            elif focus_lead is not None:
                summary = (
                    f"{focus_lead.title}: {focus_lead.summary or 'Live source marker selected.'} "
                    "This is not confirmed by satellite evidence yet."
                )
            return AtlasAgentQueryResponse(
                status=status,
                tool=tool,
                summary=summary,
                resolved=resolved,
                camera=self._camera_intent(
                    tool=tool,
                    alerts=[],
                    focus_asset_id=None,
                    focus_lead_id=focus_lead.lead_id if focus_lead is not None else None,
                    lead_matches=response_leads,
                ),
                focus_lead_id=focus_lead.lead_id if focus_lead is not None else None,
                alerts=[],
                leads=response_leads,
                planner=planner,
                trust=trust,
                replay=self.get_replay_state(),
            )

        focus = alerts[0]
        compare = self._compare_for_asset(focus.asset_id)
        return AtlasAgentQueryResponse(
            status="ok",
            tool=tool,
            summary=(
                f"{focus.asset_name}: {focus.why} "
                f"{humanize_tool_label(tool)} returned {len(alerts)} matching "
                f"{'alert' if len(alerts) == 1 else 'alerts'}."
            ),
            resolved=resolved,
            camera=self._camera_intent(
                tool=tool,
                alerts=alerts,
                focus_asset_id=focus.asset_id,
            ),
            focus_asset_id=focus.asset_id,
            focus_alert_id=focus.alert_id,
            alerts=alerts,
            compare=compare,
            analyst_report=self._analyst_report_for_compare(
                asset_id=focus.asset_id,
                compare=compare,
                alerts=alerts,
            ),
            planner=planner,
            trust=trust,
            replay=self.get_replay_state(),
        )

    def _search_live_leads_response(
        self,
        *,
        query: str,
        planner: AtlasAgentPlannerTelemetry,
        resolved: AtlasAgentResolvedRequest,
        trust: AtlasAgentTrust,
    ) -> AtlasAgentQueryResponse:
        _ = query

        matching_leads = self._lead_matches_for_request(resolved)
        response_leads = [self._lead_with_runtime_link(lead) for lead in matching_leads]
        observations = [
            AtlasAgentToolObservation(
                tool="search_live_leads",
                status="ok" if response_leads else "no_result",
                summary=(
                    f"Matched {len(response_leads)} live source "
                    f"{'lead' if len(response_leads) == 1 else 'leads'}."
                ),
                count=len(response_leads),
            )
        ]
        selected_lead = self._find_lead(resolved.selected_lead_id)
        focus_lead = next(
            (
                lead
                for lead in response_leads
                if selected_lead is not None and lead.lead_id == selected_lead.lead_id
            ),
            None,
        )
        if focus_lead is None:
            focus_lead = next((lead for lead in response_leads if lead.linked_asset_id), None)
        if focus_lead is None and response_leads:
            focus_lead = response_leads[0]
        if resolved.area:
            scope = f" near {resolved.area}"
        elif resolved.user_latitude is not None and resolved.user_longitude is not None:
            scope = " nearest your location"
        else:
            scope = ""

        if response_leads:
            lead_titles = "; ".join(f"{lead.title} ({lead.region})" for lead in response_leads[:3])
            summary = (
                f"I found {len(response_leads)} live source "
                f"{'lead' if len(response_leads) == 1 else 'leads'}{scope}: "
                f"{lead_titles}. These are source markers, not confirmed satellite alerts yet. "
                "Click a marker or ask for current versus baseline evidence to review it."
            )
            status = "ok"
        else:
            summary = (
                f"No live source leads matched{scope}. Try refreshing live leads, "
                "or ask for a broader region."
            )
            status = "no_result"

        return AtlasAgentQueryResponse(
            status=status,
            tool="search_live_leads",
            summary=summary,
            resolved=resolved,
            camera=self._camera_intent(
                tool="search_live_leads",
                alerts=[],
                focus_asset_id=None,
                focus_lead_id=focus_lead.lead_id if focus_lead is not None else None,
                lead_matches=response_leads,
            ),
            focus_lead_id=focus_lead.lead_id if focus_lead is not None else None,
            alerts=[],
            leads=response_leads,
            observations=observations,
            planner=planner,
            trust=trust,
            replay=self.get_replay_state(),
        )

    def _refresh_live_leads_response(
        self,
        *,
        query: str,
        planner: AtlasAgentPlannerTelemetry,
        resolved: AtlasAgentResolvedRequest,
        trust: AtlasAgentTrust,
    ) -> AtlasAgentQueryResponse:
        refresh = self.refresh_leads(
            LeadRefreshRequest(
                source_mode="auto",
                limit=500,
                hours=72,
                max_files=288,
                gdelt_cloud_days=30,
                gdelt_cloud_confidence_profile="loose",
            )
        )
        refreshed_leads = refresh.leads
        _ = query
        matching_leads = self._filter_leads(
            area=resolved.area,
            category=resolved.category,
            user_latitude=resolved.user_latitude,
            user_longitude=resolved.user_longitude,
            limit=resolved.limit,
        )
        focus_lead = matching_leads[0] if len(matching_leads) == 1 else None
        scope = f" for {resolved.area}" if resolved.area else ""
        if refreshed_leads:
            summary = (
                f"Refreshed live conflict feed from {refresh.source_mode}: "
                f"{refresh.lead_count} markers loaded{scope}."
            )
            if resolved.area:
                summary += (
                    f" {len(matching_leads)} marker"
                    f"{'' if len(matching_leads) == 1 else 's'} match the requested area."
                )
            status = "ok"
        else:
            summary = (
                "Live refresh returned no usable conflict markers. "
                "Existing watchlist remains active."
            )
            status = "no_result"

        return AtlasAgentQueryResponse(
            status=status,
            tool="refresh_live_leads",
            summary=summary,
            resolved=resolved,
            camera=self._camera_intent(
                tool="refresh_live_leads",
                alerts=[],
                focus_asset_id=None,
                focus_lead_id=focus_lead.lead_id if focus_lead is not None else None,
                lead_matches=matching_leads,
            ),
            focus_lead_id=focus_lead.lead_id if focus_lead is not None else None,
            alerts=[],
            leads=refreshed_leads,
            observations=[
                AtlasAgentToolObservation(
                    tool="refresh_live_leads",
                    status=status,
                    summary=summary,
                    count=refresh.lead_count,
                )
            ],
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
        lead = self._find_lead(request.selected_lead_id)
        lead_asset_id = self._lead_backed_asset_id(request.selected_lead_id)
        if not request.site_id and not request.selected_asset_id and not request.selected_lead_id:
            return AtlasAgentQueryResponse(
                status="no_result",
                tool="site_compare",
                summary=(
                    "Select a live source marker before requesting current-versus-baseline "
                    "satellite evidence."
                ),
                resolved=resolved,
                observations=[
                    AtlasAgentToolObservation(
                        tool="site_compare",
                        status="no_result",
                        summary="Compare request had no selected lead or site.",
                    )
                ],
                planner=planner,
                trust=trust,
                replay=self.get_replay_state(),
            )
        if (
            request.selected_lead_id
            and lead is None
            and not request.selected_asset_id
            and not request.site_id
        ):
            return AtlasAgentQueryResponse(
                status="no_result",
                tool="site_compare",
                summary=(
                    "The selected source marker is no longer in the live registry. "
                    "Refresh live leads or click a current marker before evidence review."
                ),
                resolved=resolved,
                observations=[
                    AtlasAgentToolObservation(
                        tool="site_compare",
                        status="no_result",
                        summary="Selected lead id was not present in the live registry.",
                    )
                ],
                planner=planner,
                trust=trust,
                replay=self.get_replay_state(),
            )
        asset_id = request.site_id or request.selected_asset_id or lead_asset_id
        asset = self._find_asset(asset_id)
        if asset is None and lead is not None:
            runtime_lead = self._lead_with_runtime_link(lead)
            satellite_eligible = self._lead_satellite_review_eligible(lead)
            summary = (
                f"{lead.title}: satellite evidence is not available for this source point yet. "
                "The marker stays selected; refresh live leads or inspect another point."
            )
            observation_summary = "Selected lead has no resolved current-baseline satellite pair."
            if not satellite_eligible:
                summary = (
                    f"{lead.title}: this source report is not satellite-observable enough "
                    "for before/after inspection. Atlas keeps it as a source marker; use "
                    "the article context or select an infrastructure-damage marker."
                )
                observation_summary = (
                    "Selected lead describes source-only violence or casualties without "
                    "a clear macro-scale visual damage target."
                )
            return AtlasAgentQueryResponse(
                status="no_result",
                tool="site_compare",
                summary=summary,
                resolved=resolved,
                camera=self._camera_intent(
                    tool="site_compare",
                    alerts=[],
                    focus_asset_id=None,
                    focus_lead_id=lead.lead_id,
                    lead_matches=[runtime_lead],
                ),
                focus_lead_id=lead.lead_id,
                leads=[runtime_lead],
                observations=[
                    AtlasAgentToolObservation(
                        tool="site_compare",
                        status="no_result",
                        summary=observation_summary,
                    )
                ],
                planner=planner,
                trust=trust,
                replay=self.get_replay_state(),
            )
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
            if lead is not None:
                runtime_lead = self._lead_with_runtime_link(lead)
                return AtlasAgentQueryResponse(
                    status="no_result",
                    tool="site_compare",
                    summary=(
                        f"{lead.title}: SimSat/Sentinel imagery did not resolve within the "
                        "live timeout for this source point. The source marker stays selected; "
                        "refresh or try a broader regional lead."
                    ),
                    resolved=resolved,
                    camera=self._camera_intent(
                        tool="site_compare",
                        alerts=[],
                        focus_asset_id=asset.asset_id,
                        focus_lead_id=lead.lead_id,
                        lead_matches=[runtime_lead],
                    ),
                    focus_asset_id=asset.asset_id,
                    focus_lead_id=lead.lead_id,
                    leads=[runtime_lead],
                    observations=[
                        AtlasAgentToolObservation(
                            tool="site_compare",
                            status="no_result",
                            summary=(
                                "Live satellite evidence timed out before both frames resolved."
                            ),
                        )
                    ],
                    planner=planner,
                    trust=trust,
                    replay=self.get_replay_state(),
                )
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
        elif (
            compare.satellite_evidence is not None
            and compare.satellite_evidence.scope == "satellite_context_only"
        ):
            summary = (
                f"{asset.asset_name}: satellite context imagery loaded for operator inspection. "
                "A dated SimSat/Sentinel before-after evidence pair did not resolve for this "
                "source point."
            )
        elif (
            compare.satellite_evidence is not None
            and compare.satellite_evidence.usability == "cloud_limited"
        ):
            source_context = f" Source report: {lead.title}." if lead is not None else ""
            summary = (
                f"{asset.asset_name}: optical before/after imagery loaded, but cloud cover "
                "or low visibility blocks a defensible model read."
                f"{source_context} Treat this as source intelligence plus degraded imagery, "
                "not a confirmed visual alert."
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
            camera=self._camera_intent(
                tool="site_compare",
                alerts=alerts,
                focus_asset_id=asset.asset_id,
            ),
            focus_asset_id=asset.asset_id,
            focus_alert_id=alerts[0].alert_id if alerts else None,
            alerts=alerts,
            compare=compare,
            analyst_report=self._analyst_report_for_compare(
                asset_id=asset.asset_id,
                compare=compare,
                alerts=alerts,
            ),
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
        lead = self._find_lead(request.selected_lead_id)
        if request.selected_asset_id is None and request.site_id is None and lead is not None:
            if lead.linked_asset_id is None:
                return AtlasAgentQueryResponse(
                    status="no_result",
                    tool="explain_alert",
                    summary=(
                        f"{lead.title} is a lead marker, not a confirmed watchlist alert. "
                        "Open the point popup or wait for evidence review."
                    ),
                    resolved=resolved,
                    camera=self._camera_intent(
                        tool="explain_alert",
                        alerts=[],
                        focus_asset_id=None,
                        focus_lead_id=lead.lead_id,
                        lead_matches=[lead],
                    ),
                    focus_lead_id=lead.lead_id,
                    planner=planner,
                    trust=trust,
                    replay=self.get_replay_state(),
                )
        target_alert = self._resolve_alert_target(
            alert_id=request.alert_id,
            selected_asset_id=request.selected_asset_id
            or request.site_id
            or (lead.linked_asset_id if lead else None),
            filtered_alerts=alerts,
            watchlist=watchlist,
        )
        if target_alert is None:
            return AtlasAgentQueryResponse(
                status="no_result",
                tool="explain_alert",
                summary=(
                    "No confirmed satellite alert is available to explain for this filter. "
                    "Ask what happened in the region to inspect live source leads."
                ),
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
            camera=self._camera_intent(
                tool="explain_alert",
                alerts=[target_alert],
                focus_asset_id=target_alert.asset_id,
            ),
            focus_asset_id=target_alert.asset_id,
            focus_alert_id=target_alert.alert_id,
            alerts=[target_alert],
            compare=compare,
            analyst_report=self._analyst_report_for_compare(
                asset_id=target_alert.asset_id,
                compare=compare,
                alerts=[target_alert],
            ),
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
        required: bool,
        plan,
    ) -> HealthDependency:
        if endpoint:
            if http_enabled and plan is not None:
                if HttpSentinelPayloadTransport(
                    timeout_seconds=_sentinel_health_timeout_for_endpoint(endpoint)
                ).probe(plan):
                    return HealthDependency(
                        status="ready",
                        detail=f"{endpoint} (http transport enabled)",
                    )
                return HealthDependency(
                    status="degraded",
                    detail=(
                        f"{endpoint} (http transport failed"
                        f"{'; live SimSat required' if required else '; fixture fallback active'})"
                    ),
                )
            transport_mode = "http transport enabled" if http_enabled else "fixture transport"
            return HealthDependency(status="ready", detail=f"{endpoint} ({transport_mode})")
        if required:
            return HealthDependency(
                status="degraded",
                detail=f"{missing_detail}; live SimSat required",
            )
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

    def _sam3_backend_dependency(self) -> HealthDependency:
        if not self.settings.sam3_http_enabled:
            if self.settings.sam3_required:
                return HealthDependency(
                    status="degraded",
                    detail=(
                        f"{self.settings.sam3_model_version} real HTTP segmentation "
                        "is required, but SAM3_HTTP_ENABLED is false"
                    ),
                )
            return HealthDependency(
                status="ready",
                detail=(
                    f"{self.settings.sam3_model_version} "
                    "(reference-only fixture; live selected points are not mask-scored)"
                ),
            )
        if not self.settings.sam3_endpoint:
            return HealthDependency(
                status="degraded" if self.settings.sam3_required else "not_configured",
                detail=(
                    "SAM3 endpoint not configured yet; real SAM3 HTTP segmentation is "
                    "required for live selected-point evidence"
                    if self.settings.sam3_required
                    else "SAM3 endpoint not configured yet"
                ),
            )
        return HealthDependency(
            status="ready",
            detail=f"{self.settings.sam3_model_version} (sam3_http segmentation)",
        )

    def _analyst_backend_dependency(self) -> HealthDependency:
        if not self.settings.analyst_http_enabled:
            return HealthDependency(
                status="ready",
                detail=(
                    f"{self.settings.analyst_model_version} "
                    "(reference-only fixture; live selected points require HTTP endpoint)"
                ),
            )
        if not self.settings.analyst_endpoint:
            return HealthDependency(
                status="not_configured",
                detail="Liquid analyst endpoint not configured yet",
            )
        provider = resolve_http_candidate_provider(self.settings.analyst_provider)
        if provider is None:
            return HealthDependency(
                status="degraded",
                detail=f"{self.settings.analyst_provider} unsupported; fixture analyst active",
            )
        return HealthDependency(
            status="ready",
            detail=f"{self.settings.analyst_model_version} ({provider.provider_id} analyst)",
        )

    def _attach_mapbox_context(self, alert: Alert) -> Alert:
        context_path = self._mapbox_context_path(alert)
        context_path.parent.mkdir(parents=True, exist_ok=True)
        context_path.touch(exist_ok=True)
        return alert.model_copy(update={"mapbox_context_ref": str(context_path)})

    def _asset_by_id(self, asset_id: str) -> Asset:
        for asset in self._runtime_assets():
            if asset.asset_id == asset_id:
                return asset
        return self.hero_asset

    def _active_scenario(self) -> ScenarioFixture:
        scenario_id = self.replay.scenario_id or "hero_port_disruption"
        return self.scenarios.get(scenario_id, self.scenarios["hero_port_disruption"])

    def _active_frame_request(self) -> FrameRequest:
        scenario = self._active_scenario()
        return self._scenario_frame_request(scenario)

    def _scenario_frame_request(self, scenario: ScenarioFixture) -> FrameRequest:
        asset = self._asset_by_id(scenario.asset_id)
        return FrameRequest(
            asset_id=scenario.asset_id,
            scenario_id=scenario.scenario_id,
            latitude=asset.latitude,
            longitude=asset.longitude,
            requested_timestamp=scenario.current_frame.frame.captured_at,
            baseline_timestamp=scenario.baseline_frame.frame.captured_at,
        )

    def _select_scenario(self, asset_id: str | None, scenario_id: str | None) -> ScenarioFixture:
        if scenario_id and scenario_id in self.scenarios:
            return self.scenarios[scenario_id]

        if asset_id == "demo_bridge_01":
            return self.scenarios["bridge_access_obstruction"]

        return self.scenarios["hero_port_disruption"]

    def _mapbox_context_path(self, alert: Alert) -> Path:
        return Path(".cache") / "mapbox" / alert.asset_id / alert.alert_id / "context.png"

    def _runtime_assets(self) -> list[Asset]:
        base_assets = list(self.assets)
        if not self._live_lead_review_enabled():
            return base_assets
        base_ids = {asset.asset_id for asset in base_assets}
        lead_assets: list[Asset] = []
        for lead in self.leads:
            runtime_lead = self._lead_with_runtime_link(lead)
            asset_id = runtime_lead.linked_asset_id
            if not asset_id or not asset_id.startswith("live_") or asset_id in base_ids:
                continue
            lead_assets.append(self._asset_from_lead(runtime_lead))
        return base_assets + lead_assets

    def _asset_from_lead(self, lead: Lead) -> Asset:
        return Asset(
            asset_id=self._synthetic_asset_id_for_lead(lead),
            asset_name=lead.title,
            asset_type=lead.category_guess or "civilian_building_cluster",
            region=lead.region,
            latitude=lead.latitude,
            longitude=lead.longitude,
        )

    def _lead_with_runtime_link(self, lead: Lead) -> Lead:
        if lead.linked_asset_id and not lead.linked_asset_id.startswith("live_"):
            return lead
        reviewable = self._live_lead_review_enabled() and self._lead_satellite_review_eligible(lead)
        if reviewable:
            return lead.model_copy(
                update={"linked_asset_id": self._synthetic_asset_id_for_lead(lead)}
            )
        if lead.linked_asset_id and lead.linked_asset_id.startswith("live_"):
            return lead.model_copy(update={"linked_asset_id": None})
        return lead

    def _lead_satellite_review_eligible(self, lead: Lead) -> bool:
        if lead.linked_asset_id and not lead.linked_asset_id.startswith("live_"):
            return True
        text = _normalized_place_text(
            " ".join(
                value
                for value in (
                    lead.title,
                    lead.summary or "",
                    lead.region,
                )
                if value
            )
        )
        if not text:
            return False
        has_damage_signal = any(
            _normalized_contains(text, term) for term in _SATELLITE_DAMAGE_TERMS
        )
        if has_damage_signal:
            return True
        has_attack_signal = any(
            _normalized_contains(text, term) for term in _SATELLITE_ATTACK_TERMS
        )
        has_structure_signal = any(
            _normalized_contains(text, term) for term in _SATELLITE_STRUCTURE_TERMS
        )
        if has_attack_signal and has_structure_signal:
            return True
        has_source_only_signal = any(
            _normalized_contains(text, term) for term in _SOURCE_ONLY_EVENT_TERMS
        )
        if has_source_only_signal:
            return False
        return has_structure_signal

    def _live_lead_review_enabled(self) -> bool:
        return bool(
            self.settings.simsat_current_endpoint
            and self.settings.simsat_baseline_endpoint
            and self.settings.simsat_current_http_enabled
            and self.settings.simsat_baseline_http_enabled
        )

    def _synthetic_asset_id_for_lead(self, lead: Lead) -> str:
        return f"live_{lead.lead_id}"

    def _nearest_seeded_evidence_asset_id(self, lead: Lead) -> str | None:
        evidence_assets = [
            asset
            for asset in self.assets
            if asset.asset_id in {scenario.asset_id for scenario in self.scenarios.values()}
            or asset.asset_id in self.reference_cases
        ]
        nearby = sorted(
            (
                (
                    self._distance_km(
                        lead.latitude, lead.longitude, asset.latitude, asset.longitude
                    ),
                    asset,
                )
                for asset in evidence_assets
            ),
            key=lambda item: item[0],
        )
        if nearby and nearby[0][0] <= 55:
            return nearby[0][1].asset_id
        return None

    def _distance_km(self, lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
        radius_km = 6371.0
        phi_a = math.radians(lat_a)
        phi_b = math.radians(lat_b)
        delta_phi = math.radians(lat_b - lat_a)
        delta_lambda = math.radians(lon_b - lon_a)
        haversine = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi_a) * math.cos(phi_b) * math.sin(delta_lambda / 2) ** 2
        )
        return 2 * radius_km * math.asin(math.sqrt(haversine))

    def _lead_for_asset_id(self, asset_id: str) -> Lead | None:
        for lead in self.leads:
            if (
                lead.linked_asset_id == asset_id
                or self._synthetic_asset_id_for_lead(lead) == asset_id
            ):
                return lead
        return None

    def _live_lead_compare(self, lead: Lead) -> AtlasAgentCompare | None:
        if not self._live_lead_review_enabled():
            return None

        asset = self._asset_from_lead(lead)
        requested_timestamp = self._lead_current_timestamp(lead)
        baseline_timestamp = self._lead_baseline_timestamp(lead)
        bundle = resolve_live_lead_satellite_evidence(
            asset=asset,
            lead=lead,
            frame_client=self.frame_client,
            requested_timestamp=requested_timestamp,
            baseline_timestamp=baseline_timestamp,
        )
        if bundle.current_frame is None or bundle.baseline_frame is None:
            return self._mapbox_context_compare(
                asset=asset,
                lead=lead,
                requested_timestamp=requested_timestamp,
                baseline_timestamp=baseline_timestamp,
                attempts=bundle.attempts,
            )
        return AtlasAgentCompare(
            asset_id=asset.asset_id,
            asset_name=asset.asset_name,
            current_frame=bundle.current_frame,
            baseline_frame=bundle.baseline_frame,
            satellite_evidence=bundle,
        )

    def _mapbox_context_compare(
        self,
        *,
        asset: Asset,
        lead: Lead,
        requested_timestamp: str,
        baseline_timestamp: str,
        attempts: list[SatelliteEvidenceAttempt] | None = None,
    ) -> AtlasAgentCompare | None:
        current = self._mapbox_context_frame(
            asset=asset,
            lead=lead,
            captured_at=requested_timestamp,
            variant="current",
        )
        baseline = self._mapbox_context_frame(
            asset=asset,
            lead=lead,
            captured_at=baseline_timestamp,
            variant="baseline",
        )
        if current is None or baseline is None:
            return None
        bundle = SatelliteEvidenceBundle(
            asset_id=asset.asset_id,
            lead_id=lead.lead_id,
            status="ready",
            scope="satellite_context_only",
            usable_for_evidence=False,
            usability="context_only",
            quality_score=0.1,
            quality_summary=(
                "Mapbox imagery is static context only. It is not a dated Sentinel "
                "before/after pair and is not model-scored."
            ),
            reason=(
                "SimSat/Sentinel did not resolve a dated before/after pair, so Atlas loaded "
                "server-side Mapbox satellite context for operator inspection only."
            ),
            target_latitude=lead.latitude,
            target_longitude=lead.longitude,
            resolved_latitude=lead.latitude,
            resolved_longitude=lead.longitude,
            offset_km=0.0,
            size_km=_mapbox_context_size_km(lead.latitude),
            requested_timestamp=requested_timestamp,
            baseline_timestamp=baseline_timestamp,
            current_frame=current,
            baseline_frame=baseline,
            attempts=attempts or [],
            quality_warnings=["mapbox_context_not_time_aware", "no_dated_pair_resolved"],
        )
        return AtlasAgentCompare(
            asset_id=asset.asset_id,
            asset_name=asset.asset_name,
            current_frame=current,
            baseline_frame=baseline,
            satellite_evidence=bundle,
        )

    def _mapbox_context_frame(
        self,
        *,
        asset: Asset,
        lead: Lead,
        captured_at: str,
        variant: Literal["current", "baseline"],
    ) -> FrameEnvelope | None:
        if not self.settings.mapbox_token or not self.settings.mapbox_context_enabled:
            return None

        output_path = (
            Path("var")
            / "mapbox_context"
            / asset.asset_id
            / (
                f"{variant}_z{_MAPBOX_CONTEXT_ZOOM:.1f}_"
                f"{lead.latitude:.5f}_{lead.longitude:.5f}.png"
            )
        )
        if not output_path.exists() or output_path.stat().st_size == 0:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            query = urlencode({"access_token": self.settings.mapbox_token})
            url = (
                "https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/"
                f"{lead.longitude:.6f},{lead.latitude:.6f},{_MAPBOX_CONTEXT_ZOOM:.1f},0/"
                f"{_MAPBOX_CONTEXT_SIZE}?{query}"
            )
            try:
                with urlopen(url, timeout=4.0) as response:
                    status = getattr(response, "status", response.getcode())
                    if status != 200:
                        return None
                    body = response.read()
            except (OSError, TimeoutError, URLError, ValueError):
                return None
            if not body:
                return None
            output_path.write_bytes(body)

        return FrameEnvelope(
            frame=FrameRecord(
                frame_id=f"mapbox_{variant}_{asset.asset_id}",
                asset_id=asset.asset_id,
                captured_at=captured_at,
                image_ref=str(output_path),
                cloud_cover=None,
                source=f"mapbox_static_satellite_context_z{_MAPBOX_CONTEXT_ZOOM:.1f}",
            ),
            accepted_for_alerting=False,
            filter_reason="satellite_context_only",
        )

    def _lead_current_timestamp(self, lead: Lead) -> str:
        source_date = lead.source_date or datetime.now(tz=UTC).date()
        return f"{source_date.isoformat()}T12:00:00Z"

    def _lead_baseline_timestamp(self, lead: Lead) -> str:
        source_date = lead.source_date or datetime.now(tz=UTC).date()
        baseline_date = source_date - timedelta(days=365 * 3)
        return f"{baseline_date.isoformat()}T12:00:00Z"

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
                timeout_seconds=self.settings.agent_timeout_seconds,
                gateway=ModelGateway(
                    timeout_seconds=self.settings.agent_timeout_seconds,
                    telemetry_sink=self._agent_gateway_events,
                ),
            )
        return FixtureAgentPlannerBackend()

    def _sam3_backend(self):
        if self.settings.sam3_http_enabled and self.settings.sam3_endpoint:
            return HttpSam3EvidenceBackend(
                endpoint=self.settings.sam3_endpoint,
                api_key=self.settings.sam3_api_key,
            )
        return FixtureSam3EvidenceBackend()

    def _analyst_backend(self):
        provider = resolve_http_candidate_provider(self.settings.analyst_provider)
        if (
            self.settings.analyst_http_enabled
            and self.settings.analyst_endpoint
            and provider is not None
        ):
            return HttpLiquidAnalystBackend(
                endpoint=self.settings.analyst_endpoint,
                provider=provider,
                api_key=self.settings.analyst_api_key,
                gateway=ModelGateway(telemetry_sink=self._analyst_gateway_events),
            )
        return FixtureLiquidAnalystBackend()

    def _health_debug(self) -> HealthDebug | None:
        model_recent = self._recent_gateway_event(self._model_gateway_events)
        agent_recent = self._recent_gateway_event(self._agent_gateway_events)
        analyst_recent = self._recent_gateway_event(self._analyst_gateway_events)
        if model_recent is None and agent_recent is None and analyst_recent is None:
            return None
        return HealthDebug(
            model_recent=model_recent,
            agent_recent=agent_recent,
            analyst_recent=analyst_recent,
        )

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
        request = self._scenario_frame_request(scenario)
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
                for item in (self._watchlist_evaluations() if watchlist is None else watchlist)
                if item.asset.asset_id == asset_id
            ),
            None,
        )
        if evaluation is None:
            reference_case = self._reference_case_for_asset(asset_id)
            if reference_case is None:
                lead = self._lead_for_asset_id(asset_id)
                if lead is not None:
                    return self._live_lead_compare(lead)
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
        selected_lead = self._find_lead(request.selected_lead_id)
        effective_site_id = request.site_id
        if effective_site_id is None and tool in {"site_compare", "explain_alert"}:
            effective_site_id = request.selected_asset_id or self._lead_backed_asset_id(
                request.selected_lead_id
            )
        effective_area = request.area
        effective_category = request.category
        if (
            selected_lead is not None
            and request.selected_asset_id is None
            and tool in {"latest_alerts", "biggest_disruptions", "refresh_live_leads"}
        ):
            effective_area = request.area or selected_lead.region
            effective_category = request.category or selected_lead.category_guess

        return AtlasAgentResolvedRequest(
            tool=tool,
            area=effective_area,
            category=effective_category,
            site_id=effective_site_id,
            alert_id=request.alert_id,
            selected_asset_id=request.selected_asset_id,
            selected_lead_id=request.selected_lead_id,
            user_latitude=request.user_latitude,
            user_longitude=request.user_longitude,
            limit=request.limit,
        )

    def _alerts_for_asset(
        self,
        asset_id: str,
        *,
        watchlist: list[_WatchlistEvaluation] | None = None,
    ) -> list[Alert]:
        for evaluation in self._watchlist_evaluations() if watchlist is None else watchlist:
            if evaluation.asset.asset_id == asset_id:
                return evaluation.alerts
        reference_case = self._reference_case_for_asset(asset_id)
        if reference_case and reference_case.expected_action != "discard":
            return [reference_case.expected_alert]
        return []

    def _analyst_report_for_compare(
        self,
        *,
        asset_id: str,
        compare: AtlasAgentCompare | None,
        alerts: list[Alert],
    ) -> LiquidAnalystReport | None:
        asset = self._find_asset(asset_id)
        if asset is None or compare is None:
            return None
        if not self._compare_usable_for_model_evidence(compare):
            return None
        if (
            compare.satellite_evidence is not None
            and self.liquid_analyst.backend.backend_id == "fixture"
        ):
            return None
        alert = alerts[0] if alerts else None
        source_lead = self._lead_for_asset_id(asset_id)
        source_context = source_context_for_lead(source_lead) if source_lead else None
        evidence = self.sam3_evidence.analyze(
            asset=asset,
            current=compare.current_frame,
            baseline=compare.baseline_frame,
            alert=alert,
            source_context=source_context,
        )
        return self.liquid_analyst.analyze(
            asset=asset,
            current=compare.current_frame,
            baseline=compare.baseline_frame,
            evidence=evidence,
            alert=alert,
        )

    def _compare_usable_for_model_evidence(self, compare: AtlasAgentCompare) -> bool:
        if compare.satellite_evidence is None:
            return True
        return compare.satellite_evidence.usability == "direct_clear"

    def _live_model_evidence_backend_ready(self) -> bool:
        return self.sam3_evidence.backend.backend_id != "fixture"

    def _asset_has_evidence(self, asset_id: str) -> bool:
        has_seeded_evidence = (
            asset_id in {scenario.asset_id for scenario in self.scenarios.values()}
            or asset_id in self.reference_cases
        )
        if has_seeded_evidence:
            return True
        return self._live_lead_review_enabled() and self._lead_for_asset_id(asset_id) is not None

    def _asset_evidence_state(self, asset_id: str) -> str:
        if asset_id in {scenario.asset_id for scenario in self.scenarios.values()}:
            return "live_demo"
        reference_case = self._reference_case_for_asset(asset_id)
        if reference_case and reference_case.expected_action == "discard":
            return "reference_control"
        if reference_case:
            return "reference_event"
        return "watch_only"

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

    def _filter_leads(
        self,
        *,
        area: str | None,
        category: str | None,
        user_latitude: float | None = None,
        user_longitude: float | None = None,
        limit: int,
    ) -> list[Lead]:
        filtered = self.leads
        if area:
            area_terms = _area_search_terms(area)
            filtered = [
                lead
                for lead in filtered
                if any(
                    term in _normalized_place_text(f"{lead.title} {lead.region}")
                    for term in area_terms
                )
            ]
        if category:
            filtered = [lead for lead in filtered if lead.category_guess == category]
        if user_latitude is not None and user_longitude is not None:
            filtered = sorted(
                filtered,
                key=lambda lead: self._distance_km(
                    user_latitude,
                    user_longitude,
                    lead.latitude,
                    lead.longitude,
                ),
            )
        return filtered[:limit]

    def _lead_matches_for_request(self, request: AtlasAgentResolvedRequest) -> list[Lead]:
        matching = self._filter_leads(
            area=request.area,
            category=request.category,
            user_latitude=request.user_latitude,
            user_longitude=request.user_longitude,
            limit=request.limit,
        )
        selected = self._find_lead(request.selected_lead_id)
        if selected is None:
            return matching
        if request.area or request.category:
            selected_matches = selected in matching
            if not selected_matches:
                return matching
        return ([selected] + [lead for lead in matching if lead.lead_id != selected.lead_id])[
            : request.limit
        ]

    def _camera_intent(
        self,
        *,
        tool: AtlasAgentTool,
        alerts: list[Alert],
        focus_asset_id: str | None,
        focus_lead_id: str | None = None,
        lead_matches: list[Lead] | None = None,
    ) -> AtlasAgentCameraIntent:
        if tool in {"site_compare", "explain_alert"} and focus_asset_id:
            return AtlasAgentCameraIntent(
                mode="focus_asset",
                asset_id=focus_asset_id,
                highlight_asset_ids=[focus_asset_id],
            )
        if focus_lead_id:
            return AtlasAgentCameraIntent(
                mode="focus_lead",
                lead_id=focus_lead_id,
                highlight_asset_ids=[alert.asset_id for alert in alerts],
                highlight_lead_ids=[focus_lead_id],
            )

        return AtlasAgentCameraIntent(
            mode="watchlist",
            highlight_asset_ids=[alert.asset_id for alert in alerts],
            highlight_lead_ids=[lead.lead_id for lead in lead_matches or []],
        )

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
                request,
                AtlasAgentPlannerTelemetry(
                    mode="deterministic",
                    detail="Explicit tool path bypassed planner.",
                    reason="explicit_tool",
                ),
            )

        query = request.query or ""
        if _query_is_scope_refusal(query.lower()):
            return (
                request.model_copy(
                    update={
                        "tool": "scope_refusal",
                        "area": request.area,
                        "category": request.category,
                        "site_id": request.site_id,
                        "alert_id": request.alert_id,
                    }
                ),
                AtlasAgentPlannerTelemetry(
                    mode="deterministic",
                    detail="Safety guardrail bypassed planner.",
                    reason="fixture_planner",
                ),
            )

        fallback_plan = self._fallback_agent_plan(request)
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
                    mode="fallback",
                    detail=(
                        "Liquid planner disabled; typed live-context fallback routed "
                        "this command."
                    ),
                    reason="planner_not_configured",
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
                    detail=(
                        "Planner endpoint missing; typed live-context fallback routed "
                        "this command."
                    ),
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
                    detail=(
                        "Planner provider unsupported; typed live-context fallback routed "
                        "this command."
                    ),
                    reason="planner_unsupported_provider",
                ),
            )
        selected_asset = self._find_asset(request.selected_asset_id)
        selected_lead = self._find_lead(request.selected_lead_id)
        runtime_selected_lead = (
            self._lead_with_runtime_link(selected_lead) if selected_lead is not None else None
        )
        decision = self._plan_with_local_agent(
            query=request.query,
            selected_asset=selected_asset,
            selected_lead=runtime_selected_lead,
            fallback_plan=fallback_plan,
        )
        plan = self._agent_plan_runtime_guardrail(
            self._sanitized_planner_plan(decision.plan, request=request),
            request=request,
            fallback_plan=fallback_plan,
        )
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

    def _plan_with_local_agent(
        self,
        *,
        query: str,
        selected_asset: Asset | None,
        selected_lead: Lead | None,
        fallback_plan: AtlasAgentPlan,
    ) -> AgentPlannerDecision:
        with self._agent_planner_lock:
            decision = self.agent_planner.plan(
                query=query,
                assets=self._runtime_assets(),
                leads=self.list_leads(),
                selected_asset=selected_asset,
                selected_lead=selected_lead,
                fallback_plan=fallback_plan,
            )
        if decision.reason != "planner_http_failed":
            return decision

        return decision

    def _fallback_agent_plan(self, request: AtlasAgentQueryRequest) -> AtlasAgentPlan:
        if self._selected_marker_evidence_intent(request):
            return AtlasAgentPlan(tool="site_compare")

        query = (request.query or "").strip()
        lowered = query.lower()
        area = self._fallback_area_from_live_leads(query)
        if not query:
            return AtlasAgentPlan(tool="answer")
        if any(term in lowered for term in ("refresh", "reload", "update", "sync", "fetch")):
            return AtlasAgentPlan(tool="refresh_live_leads", area=area)
        if any(
            term in lowered
            for term in (
                "what can",
                "capability",
                "capabilities",
                "how do you work",
                "help",
                "status",
            )
        ):
            return AtlasAgentPlan(tool="answer")
        if request.selected_asset_id and any(
            term in lowered for term in ("evidence", "satellite", "image", "baseline", "compare")
        ):
            return AtlasAgentPlan(tool="site_compare")
        if any(term in lowered for term in ("biggest", "highest", "most severe")):
            return AtlasAgentPlan(tool="biggest_disruptions", area=area)
        if any(term in lowered for term in ("latest alert", "confirmed alert", "active alert")):
            return AtlasAgentPlan(tool="latest_alerts", area=area)
        return AtlasAgentPlan(tool="search_live_leads", area=area)

    def _fallback_area_from_live_leads(self, query: str) -> str | None:
        normalized_query = _normalized_text(query)
        if not normalized_query:
            return None

        candidates: list[str] = []
        for lead in self.leads:
            candidates.extend(part.strip() for part in lead.region.split(","))
            candidates.append(lead.region)
        for candidate in candidates:
            normalized_candidate = _normalized_text(candidate)
            if len(normalized_candidate) < 3:
                continue
            if normalized_candidate in normalized_query:
                return candidate.strip()
        return _fallback_area_from_query_text(query)

    def _agent_plan_runtime_guardrail(
        self,
        plan: AtlasAgentPlan,
        *,
        request: AtlasAgentQueryRequest,
        fallback_plan: AtlasAgentPlan,
    ) -> AtlasAgentPlan:
        query = request.query or ""
        lowered = query.lower()
        _ = fallback_plan
        if _query_is_scope_refusal(lowered) and plan.tool != "scope_refusal":
            return plan.model_copy(update={"tool": "scope_refusal"})
        if _query_is_refresh_intent(lowered) and plan.tool != "refresh_live_leads":
            return plan.model_copy(update={"tool": "refresh_live_leads"})
        if self._selected_marker_evidence_intent(request) and plan.tool in {
            "answer",
            "search_live_leads",
            "latest_alerts",
            "biggest_disruptions",
        }:
            return plan.model_copy(
                update={
                    "tool": "site_compare",
                    "area": None,
                    "category": None,
                    "site_id": None,
                    "alert_id": None,
                }
            )
        return plan

    def _selected_marker_evidence_intent(self, request: AtlasAgentQueryRequest) -> bool:
        if not request.selected_lead_id or not request.query:
            return False

        lowered = request.query.lower()
        evidence_terms = (
            "satellite",
            "imagery",
            "image",
            "baseline",
            "current frame",
            "evidence",
            "compare",
        )
        action_terms = (
            "inspect",
            "watch",
            "review",
            "check",
            "open",
            "analyze",
            "analyse",
            "load",
        )
        selected_terms = (
            "this",
            "selected",
            "site",
            "point",
            "marker",
            "lead",
            "location",
        )
        if any(term in lowered for term in evidence_terms):
            return True
        return any(term in lowered for term in action_terms) and any(
            term in lowered for term in selected_terms
        )

    def _planner_telemetry(self, decision: AgentPlannerDecision) -> AtlasAgentPlannerTelemetry:
        if decision.mode == "live":
            return AtlasAgentPlannerTelemetry(
                mode="live",
                detail="Live planner routed this command.",
            )

        detail_by_reason = {
            "planner_http_failed": (
                "Planner request failed; typed live-context fallback routed this command."
            ),
            "planner_invalid_json": (
                "Planner output invalid; typed live-context fallback routed this command."
            ),
        }
        return AtlasAgentPlannerTelemetry(
            mode="fallback",
            detail=detail_by_reason.get(
                decision.reason,
                "Planner degraded; typed live-context fallback routed this command.",
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
        linked_asset_id = self._lead_backed_asset_id(request.selected_lead_id)
        if linked_asset_id:
            return linked_asset_id
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

        candidates = self._runtime_assets()
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
        area = self._safe_planner_area(
            plan.area,
            query=request.query or "",
            allow_known_asset_area=plan.tool in {"site_compare", "explain_alert"},
        )
        if area is None and plan.tool in {
            "search_live_leads",
            "latest_alerts",
            "biggest_disruptions",
            "refresh_live_leads",
        }:
            area = self._fallback_area_from_live_leads(request.query or "")
        category = self._canonical_category(plan.category)
        if (
            category is not None
            and request.category is None
            and not self._query_mentions_category(request.query or "", category)
        ):
            category = None
        site_id = plan.site_id if self._find_asset(plan.site_id) is not None else None
        anchor_asset = self._planner_anchor_asset(request=request, plan=plan, site_id=site_id)
        if anchor_asset is not None:
            area = None
        alert_id = plan.alert_id if request.alert_id else None
        return plan.model_copy(
            update={
                "area": area,
                "category": category,
                "site_id": site_id,
                "alert_id": alert_id,
            }
        )

    def _planner_anchor_asset(
        self,
        *,
        request: AtlasAgentQueryRequest,
        plan: AtlasAgentPlan,
        site_id: str | None,
    ) -> Asset | None:
        if plan.tool not in {"site_compare", "explain_alert"}:
            return None
        return self._find_asset(
            request.selected_asset_id
            or request.site_id
            or self._lead_backed_asset_id(request.selected_lead_id)
            or site_id
        )

    def _safe_planner_area(
        self,
        area: str | None,
        *,
        query: str,
        allow_known_asset_area: bool = False,
    ) -> str | None:
        if not area:
            return None
        normalized = " ".join(area.strip().split())
        if not normalized or len(normalized) > 120:
            return None
        normalized_lower = normalized.lower()
        for asset_type in {asset.asset_type for asset in self._runtime_assets()}:
            if normalized_lower in {asset_type, asset_type.replace("_", " ")}:
                return None
        if (
            not self._query_mentions_area(
                query=query,
                area=normalized,
            )
            and not self._area_matches_live_lead_region_for_query(
                query=query,
                area=normalized,
            )
            and not (allow_known_asset_area and self._area_matches_known_asset(normalized))
        ):
            return None
        return normalized

    def _query_mentions_area(self, *, query: str, area: str) -> bool:
        normalized_query = _normalized_place_text(query)
        normalized_area = _normalized_place_text(area)
        if not normalized_query or not normalized_area:
            return False
        return normalized_area in normalized_query

    def _area_matches_live_lead_region_for_query(self, *, query: str, area: str) -> bool:
        normalized_query = _normalized_place_text(query)
        normalized_area = _normalized_place_text(area)
        if not normalized_query or not normalized_area:
            return False
        for lead in self.leads:
            if _normalized_place_text(lead.region) != normalized_area:
                continue
            region_parts = [
                _normalized_place_text(part)
                for part in lead.region.split(",")
                if len(_normalized_place_text(part)) >= 3
            ]
            if any(part in normalized_query for part in region_parts):
                return True
        return False

    def _area_matches_known_asset(self, area: str) -> bool:
        normalized_area = _normalized_place_text(area)
        if not normalized_area:
            return False
        for asset in self._runtime_assets():
            if normalized_area in {
                _normalized_place_text(asset.asset_name),
                _normalized_place_text(asset.region),
            }:
                return True
        return False

    def _canonical_category(self, category: str | None) -> str | None:
        if not category:
            return None
        category_lower = category.lower()
        known = {asset.asset_type for asset in self._runtime_assets()}
        return next((value for value in known if value == category_lower), None)

    def _query_mentions_category(self, query: str, category: str) -> bool:
        query_lower = query.lower()
        category_terms = {
            category,
            category.replace("_", " "),
            *_CATEGORY_QUERY_ALIASES.get(category, ()),
        }
        return any(term in query_lower for term in category_terms)

    def _find_asset(self, asset_id: str | None) -> Asset | None:
        if asset_id is None:
            return None
        return next((asset for asset in self._runtime_assets() if asset.asset_id == asset_id), None)

    def _find_lead(self, lead_id: str | None) -> Lead | None:
        if lead_id is None:
            return None
        return next((lead for lead in self.leads if lead.lead_id == lead_id), None)

    def _lead_refresh_output_path(self) -> str:
        return (
            self._lead_registry_runtime_path
            or self.settings.lead_registry_path
            or "var/live_leads.json"
        )

    def _refresh_leads_from_source(
        self,
        *,
        request: LeadRefreshRequest,
        output_path: str,
        source_mode: str,
    ) -> tuple[list[Lead], int]:
        return refresh_lead_registry(
            source_path=None,
            output_path=output_path,
            source_mode=source_mode,
            gdelt_hours=request.hours,
            gdelt_max_files=request.max_files,
            gdelt_limit=request.limit,
            gdelt_min_articles=request.min_articles,
            gdelt_country_allowlist=parse_gdelt_country_allowlist(request.country_allowlist),
            acled_access_token=self.settings.acled_access_token,
            acled_username=self.settings.acled_username,
            acled_password=self.settings.acled_password,
            acled_days=request.acled_days,
            acled_limit=request.limit,
            acled_countries=parse_acled_csv_list(request.acled_countries, DEFAULT_ACLED_COUNTRIES),
            gdelt_cloud_api_key=self.settings.gdelt_cloud_api_key,
            gdelt_cloud_days=request.gdelt_cloud_days,
            gdelt_cloud_limit=request.limit,
            gdelt_cloud_countries=parse_gdelt_cloud_csv_list(
                request.gdelt_cloud_countries,
                DEFAULT_GDELT_CLOUD_COUNTRIES,
            ),
            gdelt_cloud_confidence_profile=request.gdelt_cloud_confidence_profile,
            dry_run=request.dry_run,
            preserve_on_empty=source_mode in {"acled", "gdelt", "gdelt_cloud"},
        )

    def _resolved_lead_refresh_source_mode(self, source_mode: str) -> str:
        if source_mode != "auto":
            return source_mode
        if self.settings.gdelt_cloud_api_key:
            return "gdelt_cloud"
        if self.settings.acled_lead_enabled and (
            self.settings.acled_access_token
            or (self.settings.acled_username and self.settings.acled_password)
        ):
            return "acled"
        return "gdelt"

    def _reload_leads(self) -> None:
        refreshed = load_lead_registry(self._lead_registry_runtime_path)
        if refreshed:
            self.leads = refreshed

    def _lead_backed_asset_id(self, lead_id: str | None) -> str | None:
        lead = self._find_lead(lead_id)
        if lead is None:
            return None
        return self._lead_with_runtime_link(lead).linked_asset_id

    def _agent_trust(self) -> AtlasAgentTrust:
        health = self.get_health()
        if "degraded" in {
            health.simsat_current.status,
            health.simsat_baseline.status,
            health.model_backend.status,
            health.sam3_backend.status,
            health.analyst_backend.status,
        }:
            return AtlasAgentTrust(
                mode="degraded",
                detail="live fetch degraded; cached fallback truth active",
            )
        if (
            health.config.simsat_current_http_enabled
            or health.config.simsat_baseline_http_enabled
            or health.config.model_http_enabled
            or health.config.sam3_http_enabled
            or health.config.analyst_http_enabled
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
            HttpSentinelPayloadTransport(
                timeout_seconds=_sentinel_timeout_for_endpoint(
                    self.settings.simsat_current_endpoint
                )
            )
            if self.settings.simsat_current_http_enabled
            else fixture_transport
        )
        baseline_transport = (
            HttpSentinelPayloadTransport(
                timeout_seconds=_sentinel_timeout_for_endpoint(
                    self.settings.simsat_baseline_endpoint
                )
            )
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

    def _frame_cache_namespace(self) -> str:
        return "|".join(
            [
                self.settings.simsat_current_endpoint or "",
                self.settings.simsat_baseline_endpoint or "",
                str(self.settings.simsat_current_http_enabled),
                str(self.settings.simsat_baseline_http_enabled),
            ]
        )


@dataclass(frozen=True)
class _CompositeSentinelFrameClient:
    current: CurrentSentinelAdapter | FixtureFrameClient
    baseline: BaselineSentinelAdapter | FixtureFrameClient

    def get_current_frame(self, request: FrameRequest) -> FrameEnvelope:
        try:
            return self.current.get_current_frame(request)
        except (KeyError, ValueError):
            if (
                request.latitude is None
                or request.longitude is None
                or request.requested_timestamp is None
            ):
                raise
            historical_request = replace(
                request,
                baseline_timestamp=request.requested_timestamp,
                window_seconds=max(
                    request.window_seconds,
                    _SIMSAT_LIVE_FALLBACK_WINDOW_SECONDS,
                ),
            )
            historical = self.baseline.get_baseline_frame(historical_request)
            return historical.model_copy(
                update={"filter_reason": "simsat_historical_current_frame"}
            )

    def get_baseline_frame(self, request: FrameRequest) -> FrameEnvelope:
        return self.baseline.get_baseline_frame(request)


def humanize_tool_label(tool: AtlasAgentTool) -> str:
    return tool.replace("_", " ")


def format_agent_timestamp(value: str) -> str:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return timestamp.strftime("%Y-%m-%d %H:%M UTC")


def _sentinel_timeout_for_endpoint(endpoint: str | None) -> float:
    if endpoint and ("localhost" in endpoint or "127.0.0.1" in endpoint):
        return 45.0
    return 5.0


def _sentinel_health_timeout_for_endpoint(endpoint: str | None) -> float:
    if endpoint and ("localhost" in endpoint or "127.0.0.1" in endpoint):
        return 10.0
    return 5.0
