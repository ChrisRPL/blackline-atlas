from __future__ import annotations

import json
from urllib.error import URLError

from app.schemas.agent import AtlasAgentPlan
from app.schemas.lead import Lead
from app.services.agent_planner import (
    AgentPlannerBackendResult,
    HttpAgentPlannerBackend,
    PromptedAtlasAgentPlanner,
)
from app.services.agent_prompt_builder import AgentPlannerPromptBuilder
from app.services.agent_provider import (
    AtlasJsonHttpAgentPlannerProvider,
    OpenAIChatCompletionsAgentPlannerProvider,
    OpenAIResponsesAgentPlannerProvider,
)
from app.services.lead_registry_loader import load_lead_registry
from app.services.model_gateway import ModelGateway
from app.services.watchlist_loader import load_watchlist_assets


def test_agent_prompt_builder_targets_tool_plan_only() -> None:
    assets = load_watchlist_assets(None)
    leads = load_lead_registry(None)
    qasmiyeh = next(lead for lead in leads if lead.lead_id == "lead_qasmiyeh_bridge_202604")
    prompt = AgentPlannerPromptBuilder().build(
        query="show biggest disruptions near Black Sea",
        assets=assets,
        leads=leads,
        selected_asset=assets[0],
        selected_lead=qasmiyeh,
    )

    assert "Output exactly one minified JSON object" in prompt.system
    assert "Required keys: tool, area, category, site_id, alert_id, camera" in prompt.system
    assert "answer" in prompt.system
    assert "scope_refusal" in prompt.system
    assert "search_live_leads" in prompt.system
    assert "latest_alerts" in prompt.system
    assert "biggest_disruptions" in prompt.system
    assert "refresh_live_leads" in prompt.system
    assert (
        "Categories: aid_shelter_campus, aid_warehouse_cluster, "
        "bridge, container_port, grain_port, grain_storage_complex, logistics_hub, "
        "medical_aid_node, water_infrastructure."
    ) in prompt.system
    assert "site_id must be one listed asset id or null." in prompt.system
    assert "use site_compare" in prompt.system
    assert "tool must be search_live_leads" in prompt.system
    assert "This overrides search_live_leads" in prompt.system
    assert "loads satellite/VLM evidence" in prompt.system
    assert "use refresh_live_leads" in prompt.system
    assert "If a selected_lead exists" in prompt.system
    assert "Inspect the selected marker" in prompt.system
    assert "use answer" in prompt.system
    assert "If the user asks targeting/strike/troop/weapon" in prompt.system
    assert 'Example output: {"tool":"search_live_leads"' in prompt.system
    assert "selected_asset: demo_port_01" in prompt.user
    assert "selected_lead: lead_qasmiyeh_bridge_202604" in prompt.user
    assert "linked_asset_id=none" in prompt.user
    assert "user_query: show biggest disruptions near Black Sea" in prompt.user


def test_agent_prompt_builder_marks_linked_leads_as_inspectable() -> None:
    assets = load_watchlist_assets(None)
    leads = load_lead_registry(None)
    qasmiyeh = next(lead for lead in leads if lead.lead_id == "lead_qasmiyeh_bridge_202604")
    inspectable = qasmiyeh.model_copy(update={"linked_asset_id": "live_lead_qasmiyeh"})

    prompt = AgentPlannerPromptBuilder().build(
        query="compare this point with baseline",
        assets=assets,
        leads=[inspectable],
        selected_asset=None,
        selected_lead=inspectable,
    )

    assert "use site_compare" in prompt.system
    assert "lead_qasmiyeh_bridge_202604:" in prompt.user
    assert "selected_lead: lead_qasmiyeh_bridge_202604" in prompt.user
    assert "linked_asset_id=live_lead_qasmiyeh" in prompt.user


def test_agent_prompt_builder_includes_query_relevant_linked_lead() -> None:
    assets = load_watchlist_assets(None)
    lead = Lead(
        lead_id="gdelt_port_au_prince",
        title="Port-Au-Prince armed conflict",
        region="Port-au-Prince, Haiti",
        latitude=18.5392,
        longitude=-72.335,
        category_guess="container_port",
        status="lead_only",
        linked_asset_id="live_gdelt_port_au_prince",
    )

    prompt = AgentPlannerPromptBuilder().build(
        query="What is the current situation in Port-au-Prince?",
        assets=assets,
        leads=[lead],
        selected_asset=None,
        selected_lead=None,
    )

    assert "gdelt_port_au_prince:" in prompt.user
    assert "linked_asset_id=live_gdelt_port_au_prince" in prompt.user


def test_agent_prompt_builder_keeps_live_registry_context_compact() -> None:
    assets = load_watchlist_assets(None)
    leads = [
        Lead(
            lead_id=f"lead_{index}",
            title=f"Lead {index}",
            region=f"Region {index}",
            latitude=0.0,
            longitude=0.0,
            category_guess="water_infrastructure",
            status="lead_only",
        )
        for index in range(120)
    ]

    prompt = AgentPlannerPromptBuilder().build(
        query="show recent disruption near Lebanon",
        assets=assets,
        leads=leads,
        selected_asset=None,
        selected_lead=None,
    )

    assert "lead_count: 120" in prompt.user
    assert "selected_or_relevant_leads: none" in prompt.user
    assert "lead_0" not in prompt.user


def test_prompted_agent_planner_builds_text_only_payload() -> None:
    assets = load_watchlist_assets(None)
    leads = load_lead_registry(None)
    planner = PromptedAtlasAgentPlanner(
        model_version="lfm2.5-1.2b-instruct",
        backend=_RecordingPlannerBackend(raw_text='{"tool":"latest_alerts"}'),
    )

    payload = planner.build_payload(
        query="latest alerts",
        assets=assets,
        leads=leads,
        selected_asset=assets[0],
        selected_lead=None,
    )

    assert payload.model_version == "lfm2.5-1.2b-instruct"
    assert [item.role for item in payload.inputs] == ["system", "user"]


def test_agent_planner_parser_uses_first_balanced_json_object() -> None:
    planner = PromptedAtlasAgentPlanner(
        model_version="lfm2.5-1.2b-instruct",
        backend=_RecordingPlannerBackend(raw_text='{"tool":"latest_alerts"}'),
    )

    plan = planner.parse_plan(
        raw_text=(
            '{\n  "tool": "search_live_leads",\n  "area": "Port-au-Prince",\n'
            '  "category": null,\n  "site_id": null,\n  "alert_id": null,\n'
            '  "camera": null\n}\n'
            'Example output: {"tool":"search_live_leads","area":"Iran"}'
        ),
        fallback_plan=AtlasAgentPlan(tool="answer"),
    )

    assert plan == AtlasAgentPlan(tool="search_live_leads", area="Port-au-Prince")


def test_prompted_agent_planner_falls_back_on_invalid_json() -> None:
    assets = load_watchlist_assets(None)
    leads = load_lead_registry(None)
    fallback = AtlasAgentPlan(tool="biggest_disruptions", area="Black Sea")
    planner = PromptedAtlasAgentPlanner(
        model_version="lfm2.5-1.2b-instruct",
        backend=_RecordingPlannerBackend(raw_text="not json"),
    )

    decision = planner.plan(
        query="show biggest disruptions near Black Sea",
        assets=assets,
        leads=leads,
        selected_asset=assets[0],
        selected_lead=None,
        fallback_plan=fallback,
    )

    assert decision.plan == fallback
    assert decision.mode == "fallback"
    assert decision.reason == "planner_invalid_json"


def test_prompted_agent_planner_accepts_refresh_live_leads_plan() -> None:
    plan = PromptedAtlasAgentPlanner(
        model_version="lfm2.5-1.2b-instruct",
        backend=_RecordingPlannerBackend(raw_text='{"tool":"refresh_live_leads","area":"Ukraine"}'),
    ).parse_plan(
        raw_text='{"tool":"refresh_live_leads","area":"Ukraine"}',
        fallback_plan=AtlasAgentPlan(tool="latest_alerts"),
    )

    assert plan == AtlasAgentPlan(tool="refresh_live_leads", area="Ukraine")


def test_prompted_agent_planner_normalizes_common_local_model_json_drift() -> None:
    plan = PromptedAtlasAgentPlanner(
        model_version="lfm2.5-1.2b-instruct",
        backend=_RecordingPlannerBackend(raw_text="unused"),
    ).parse_plan(
        raw_text=(
            "```json\n"
            '{"tool":"search_live_leads","area":"Lebanon","category":"disruptions",'
            '"site_id":"none","alert_id":"none","camera":null}\n'
            "```"
        ),
        fallback_plan=AtlasAgentPlan(tool="answer"),
    )

    assert plan == AtlasAgentPlan(tool="search_live_leads", area="Lebanon")


def test_prompted_agent_planner_rejects_payload_without_tool() -> None:
    plan = PromptedAtlasAgentPlanner(
        model_version="lfm2.5-1.2b-instruct",
        backend=_RecordingPlannerBackend(raw_text="unused"),
    ).parse_plan(
        raw_text='{"area":"Lebanon","category":null}',
        fallback_plan=AtlasAgentPlan(tool="answer"),
    )

    assert plan is None


def test_http_agent_planner_backend_posts_payload() -> None:
    captured = {}

    def fake_urlopen(request, timeout: float):
        captured["url"] = request.full_url
        captured["auth"] = request.get_header("Authorization")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _FakeHTTPResponse(
            body=json.dumps(
                {"output_text": '{"tool":"site_compare","site_id":"demo_port_01"}'}
            ).encode("utf-8")
        )

    backend = HttpAgentPlannerBackend(
        endpoint="https://example.test/planner",
        provider=AtlasJsonHttpAgentPlannerProvider(),
        api_key="planner-key",
        timeout_seconds=6.0,
        gateway=ModelGateway(timeout_seconds=6.0, opener=fake_urlopen),
    )

    result = backend.generate(
        payload=PromptedAtlasAgentPlanner(
            model_version="lfm2.5-1.2b-instruct",
            backend=_RecordingPlannerBackend(raw_text='{"tool":"latest_alerts"}'),
        ).build_payload(
            query="compare this site",
            assets=load_watchlist_assets(None),
            leads=load_lead_registry(None),
            selected_asset=load_watchlist_assets(None)[0],
            selected_lead=None,
        ),
        fallback_plan=AtlasAgentPlan(tool="latest_alerts"),
    )

    assert result.raw_text == '{"tool":"site_compare","site_id":"demo_port_01"}'
    assert result.reason is None
    assert captured["url"] == "https://example.test/planner"
    assert captured["auth"] == "Bearer planner-key"
    assert captured["body"]["model_version"] == "lfm2.5-1.2b-instruct"
    assert captured["timeout"] == 6.0


def test_http_agent_planner_backend_falls_back_on_failure() -> None:
    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        raise URLError("offline")

    backend = HttpAgentPlannerBackend(
        endpoint="https://example.test/planner",
        provider=AtlasJsonHttpAgentPlannerProvider(),
        gateway=ModelGateway(opener=fake_urlopen),
    )
    fallback = AtlasAgentPlan(tool="latest_alerts", area="Black Sea")

    result = backend.generate(
        payload=PromptedAtlasAgentPlanner(
            model_version="lfm2.5-1.2b-instruct",
            backend=_RecordingPlannerBackend(raw_text='{"tool":"latest_alerts"}'),
        ).build_payload(
            query="latest alerts near Black Sea",
            assets=load_watchlist_assets(None),
            leads=load_lead_registry(None),
            selected_asset=None,
            selected_lead=None,
        ),
        fallback_plan=fallback,
    )

    assert result.raw_text == fallback.model_dump_json(exclude_none=True)
    assert result.reason == "planner_http_failed"


def test_openai_agent_planner_provider_builds_responses_request() -> None:
    provider = OpenAIResponsesAgentPlannerProvider()
    payload = PromptedAtlasAgentPlanner(
        model_version="gpt-4.1-mini",
        backend=_RecordingPlannerBackend(raw_text='{"tool":"latest_alerts"}'),
    ).build_payload(
        query="show latest alerts",
        assets=load_watchlist_assets(None),
        leads=load_lead_registry(None),
        selected_asset=None,
        selected_lead=None,
    )

    request = provider.build_request(
        endpoint="https://api.openai.com/v1/responses",
        payload=payload,
        api_key="agent-key",
    )
    body = json.loads(request.data.decode("utf-8"))

    assert request.full_url == "https://api.openai.com/v1/responses"
    assert request.get_header("Authorization") == "Bearer agent-key"
    assert body["model"] == "gpt-4.1-mini"
    assert body["input"][0]["role"] == "system"
    assert body["input"][1]["role"] == "user"


def test_openai_chat_completions_agent_planner_provider_builds_request() -> None:
    provider = OpenAIChatCompletionsAgentPlannerProvider()
    payload = PromptedAtlasAgentPlanner(
        model_version="LiquidAI/LFM2.5-1.2B-Instruct",
        backend=_RecordingPlannerBackend(raw_text='{"tool":"latest_alerts"}'),
    ).build_payload(
        query="show biggest disruptions near Black Sea",
        assets=load_watchlist_assets(None),
        leads=load_lead_registry(None),
        selected_asset=None,
        selected_lead=None,
    )

    request = provider.build_request(
        endpoint="https://liquid.example/v1/chat/completions",
        payload=payload,
        api_key="liquid-key",
    )
    body = json.loads(request.data.decode("utf-8"))

    assert request.full_url == "https://liquid.example/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer liquid-key"
    assert body["model"] == "LiquidAI/LFM2.5-1.2B-Instruct"
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][1]["role"] == "user"
    assert body["temperature"] == 0
    assert body["max_tokens"] == 256
    assert body["response_format"] == {"type": "json_object"}


def test_openai_chat_completions_agent_planner_provider_parses_response() -> None:
    provider = OpenAIChatCompletionsAgentPlannerProvider()

    parsed = provider.parse_response(
        body=json.dumps(
            {
                "choices": [
                    {"message": {"content": '{"tool":"biggest_disruptions","area":"Black Sea"}'}}
                ]
            }
        ),
        fallback='{"tool":"latest_alerts"}',
    )

    assert parsed == '{"tool":"biggest_disruptions","area":"Black Sea"}'


class _RecordingPlannerBackend:
    def __init__(self, raw_text: str) -> None:
        self.raw_text = raw_text

    def generate(self, *, payload, fallback_plan) -> str:
        _ = payload
        _ = fallback_plan
        return AgentPlannerBackendResult(raw_text=self.raw_text)


class _FakeHTTPResponse:
    def __init__(self, *, body: bytes, status: int = 200) -> None:
        self._body = body
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = exc_type
        _ = exc
        _ = tb
