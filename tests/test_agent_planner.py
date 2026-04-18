from __future__ import annotations

import json
from urllib.error import URLError

from app.schemas.agent import AtlasAgentPlan
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
from app.services.watchlist_loader import load_watchlist_assets


def test_agent_prompt_builder_targets_tool_plan_only() -> None:
    assets = load_watchlist_assets(None)
    prompt = AgentPlannerPromptBuilder().build(
        query="show biggest disruptions near Black Sea",
        assets=assets,
        selected_asset=assets[0],
    )

    assert "Choose exactly one tool" in prompt.system
    assert "Return JSON only" in prompt.system
    assert "latest_alerts" in prompt.system
    assert "biggest_disruptions" in prompt.system
    assert (
        "Allowed category values: aid_warehouse_cluster, bridge, container_port, "
        "grain_port, logistics_hub, medical_aid_node, water_infrastructure."
    ) in prompt.system
    assert "site_id must be exactly one watchlist asset_id or null." in prompt.system
    assert "For site_compare, set site_id" in prompt.system
    assert "selected_asset: demo_port_01" in prompt.user
    assert "user_query: show biggest disruptions near Black Sea" in prompt.user


def test_prompted_agent_planner_builds_text_only_payload() -> None:
    assets = load_watchlist_assets(None)
    planner = PromptedAtlasAgentPlanner(
        model_version="lfm2.5-1.2b-instruct",
        backend=_RecordingPlannerBackend(raw_text='{"tool":"latest_alerts"}'),
    )

    payload = planner.build_payload(
        query="latest alerts",
        assets=assets,
        selected_asset=assets[0],
    )

    assert payload.model_version == "lfm2.5-1.2b-instruct"
    assert [item.role for item in payload.inputs] == ["system", "user"]


def test_prompted_agent_planner_falls_back_on_invalid_json() -> None:
    assets = load_watchlist_assets(None)
    fallback = AtlasAgentPlan(tool="biggest_disruptions", area="Black Sea")
    planner = PromptedAtlasAgentPlanner(
        model_version="lfm2.5-1.2b-instruct",
        backend=_RecordingPlannerBackend(raw_text="not json"),
    )

    decision = planner.plan(
        query="show biggest disruptions near Black Sea",
        assets=assets,
        selected_asset=assets[0],
        fallback_plan=fallback,
    )

    assert decision.plan == fallback
    assert decision.mode == "fallback"
    assert decision.reason == "planner_invalid_json"


def test_http_agent_planner_backend_posts_payload(monkeypatch) -> None:
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

    monkeypatch.setattr("app.services.agent_planner.urlopen", fake_urlopen)
    backend = HttpAgentPlannerBackend(
        endpoint="https://example.test/planner",
        provider=AtlasJsonHttpAgentPlannerProvider(),
        api_key="planner-key",
        timeout_seconds=6.0,
    )

    result = backend.generate(
        payload=PromptedAtlasAgentPlanner(
            model_version="lfm2.5-1.2b-instruct",
            backend=_RecordingPlannerBackend(raw_text='{"tool":"latest_alerts"}'),
        ).build_payload(
            query="compare this site",
            assets=load_watchlist_assets(None),
            selected_asset=load_watchlist_assets(None)[0],
        ),
        fallback_plan=AtlasAgentPlan(tool="latest_alerts"),
    )

    assert result.raw_text == '{"tool":"site_compare","site_id":"demo_port_01"}'
    assert result.reason is None
    assert captured["url"] == "https://example.test/planner"
    assert captured["auth"] == "Bearer planner-key"
    assert captured["body"]["model_version"] == "lfm2.5-1.2b-instruct"
    assert captured["timeout"] == 6.0


def test_http_agent_planner_backend_falls_back_on_failure(monkeypatch) -> None:
    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        raise URLError("offline")

    monkeypatch.setattr("app.services.agent_planner.urlopen", fake_urlopen)
    backend = HttpAgentPlannerBackend(
        endpoint="https://example.test/planner",
        provider=AtlasJsonHttpAgentPlannerProvider(),
    )
    fallback = AtlasAgentPlan(tool="latest_alerts", area="Black Sea")

    result = backend.generate(
        payload=PromptedAtlasAgentPlanner(
            model_version="lfm2.5-1.2b-instruct",
            backend=_RecordingPlannerBackend(raw_text='{"tool":"latest_alerts"}'),
        ).build_payload(
            query="latest alerts near Black Sea",
            assets=load_watchlist_assets(None),
            selected_asset=None,
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
        selected_asset=None,
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
        selected_asset=None,
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
    assert body["max_tokens"] == 64
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
