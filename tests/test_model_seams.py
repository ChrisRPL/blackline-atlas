from __future__ import annotations

import base64
import json
from urllib.error import URLError

from app.core.config import Settings
from app.schemas.asset import Asset
from app.schemas.frame import FrameEnvelope, FrameRecord
from app.services.model_gateway import ModelGateway
from app.services.model_provider import (
    AtlasJsonHttpCandidateProvider,
    OpenAIResponsesCandidateProvider,
)
from app.services.model_wrapper import HttpRawCandidateBackend, PromptedCandidateModel
from app.services.prompt_builder import CandidatePromptBuilder
from app.services.scenario_fixtures import build_stub_scenarios
from app.services.watchlist_loader import load_watchlist_assets


def test_candidate_prompt_builder_targets_candidate_json_only() -> None:
    prompt = CandidatePromptBuilder().build(
        asset=_asset(),
        current=_current_frame(),
        baseline=_baseline_frame(),
    )

    assert "Return a candidate, not a full alert." in prompt.system
    assert "Do not add markdown, prose, or code fences." in prompt.system
    assert "Confidence must be a numeric decimal between 0.0 and 1.0." in prompt.system
    assert "probable_large_scale_disruption: major structural loss" in prompt.system
    assert "alert_id" not in prompt.system
    assert "source" not in prompt.system
    assert "asset_id: demo_port_01" in prompt.user
    assert "frame_id: cur_demo_port_01_20260414" in prompt.user
    assert "frame_id: base_demo_port_01_20250901" in prompt.user
    assert "overlay_ref: fixtures/demo_port_01/overlay-2026-04-14.png" in prompt.user
    assert "confidence must be numeric like 0.84" in prompt.user
    assert "action=discard" in prompt.user


def test_prompted_candidate_model_builds_minimal_multimodal_payload() -> None:
    model = PromptedCandidateModel(
        model_version="lfm2.5-vl-450m-prompted",
        backend=_RecordingBackend(raw_text="{}"),
    )

    payload = model.build_payload(
        asset=_asset(),
        scenario=_scenario(),
        current=_current_frame(),
        baseline=_baseline_frame(),
    )

    assert payload.model_version == "lfm2.5-vl-450m-prompted"
    assert payload.asset_id == "demo_port_01"
    assert payload.scenario_id == "hero_port_disruption"
    assert [item.type for item in payload.inputs] == [
        "input_text",
        "input_text",
        "input_image",
        "input_image",
        "input_image",
    ]
    assert payload.inputs[2].image_ref == "fixtures/demo_port_01/current-2026-04-14.png"
    assert payload.inputs[4].image_ref == "fixtures/demo_port_01/overlay-2026-04-14.png"


def test_prompted_candidate_model_passes_prompt_and_returns_raw_text() -> None:
    backend = _RecordingBackend(
        raw_text=(
            '{"event_type":"probable_large_scale_disruption","severity":"high",'
            '"confidence":0.89,"bbox":[0.19,0.26,0.73,0.84],'
            '"civilian_impact":"shipping_or_aid_disruption",'
            '"why":"Large terminal footprint change versus baseline.",'
            '"action":"downlink_now"}'
        )
    )
    model = PromptedCandidateModel(
        model_version="lfm2.5-vl-450m-prompted",
        backend=backend,
    )

    raw_text = model.generate_candidate_text(
        asset=_asset(),
        scenario=_scenario(),
        current=_current_frame(),
        baseline=_baseline_frame(),
    )

    assert raw_text == backend.raw_text
    assert backend.payload is not None
    assert backend.payload.model_version == "lfm2.5-vl-450m-prompted"
    assert backend.payload.inputs[0].role == "system"
    assert backend.scenario.scenario_id == "hero_port_disruption"


def test_prompted_candidate_model_exposes_prompt_build_step() -> None:
    model = PromptedCandidateModel(
        model_version="lfm2.5-vl-450m-prompted",
        backend=_RecordingBackend(raw_text="{}"),
    )

    prompt = model.build_prompt(
        asset=_asset(),
        current=_current_frame(),
        baseline=_baseline_frame(),
    )

    assert "probable_access_obstruction" in prompt.system
    assert prompt.render().startswith("You are Blackline Atlas candidate generation.")


def test_http_raw_candidate_backend_posts_payload() -> None:
    captured = {}

    def fake_urlopen(request, timeout: float):
        captured["url"] = request.full_url
        captured["auth"] = request.get_header("Authorization")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _FakeHTTPResponse(
            body=json.dumps({"output_text": '{"action":"defer"}'}).encode("utf-8")
        )

    backend = HttpRawCandidateBackend(
        endpoint="https://example.test/model",
        provider=AtlasJsonHttpCandidateProvider(),
        api_key="secret-token",
        timeout_seconds=7.0,
        gateway=ModelGateway(timeout_seconds=7.0, opener=fake_urlopen),
    )
    model = PromptedCandidateModel(
        model_version="lfm2.5-vl-450m-prompted",
        backend=backend,
    )

    raw_text = model.generate_candidate_text(
        asset=_asset(),
        scenario=_scenario(),
        current=_current_frame(),
        baseline=_baseline_frame(),
    )

    assert raw_text == '{"action":"defer"}'
    assert captured["url"] == "https://example.test/model"
    assert captured["auth"] == "Bearer secret-token"
    assert captured["body"]["scenario_id"] == "hero_port_disruption"
    assert captured["timeout"] == 7.0


def test_http_raw_candidate_backend_falls_back_to_fixture_text_on_failure() -> None:
    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        raise URLError("offline")

    backend = HttpRawCandidateBackend(
        endpoint="https://example.test/model",
        provider=AtlasJsonHttpCandidateProvider(),
        gateway=ModelGateway(opener=fake_urlopen),
    )
    model = PromptedCandidateModel(
        model_version="lfm2.5-vl-450m-prompted",
        backend=backend,
    )
    scenario = _scenario()

    raw_text = model.generate_candidate_text(
        asset=_asset(),
        scenario=scenario,
        current=_current_frame(),
        baseline=_baseline_frame(),
    )

    assert raw_text == scenario.model_output_text


def test_http_raw_candidate_backend_uses_provider_contract() -> None:
    calls = []

    class _Provider:
        provider_id = "fake_provider"

        def build_request(self, *, endpoint, payload, api_key):
            calls.append(("build", endpoint, payload.asset_id, api_key))
            return _FakeProviderRequest(endpoint)

        def parse_response(self, *, body, fallback):
            calls.append(("parse", body, fallback))
            return '{"action":"discard"}'

    def fake_urlopen(request, timeout: float):
        calls.append(("open", request.full_url, timeout))
        return _FakeHTTPResponse(body=b'{"ignored":true}')

    scenario = _scenario()
    model = PromptedCandidateModel(
        model_version="lfm2.5-vl-450m-prompted",
        backend=HttpRawCandidateBackend(
            endpoint="https://example.test/provider",
            provider=_Provider(),
            api_key="api-key",
            timeout_seconds=4.0,
            gateway=ModelGateway(timeout_seconds=4.0, opener=fake_urlopen),
        ),
    )

    raw_text = model.generate_candidate_text(
        asset=_asset(),
        scenario=scenario,
        current=_current_frame(),
        baseline=_baseline_frame(),
    )

    assert raw_text == '{"action":"discard"}'
    assert calls[0] == ("build", "https://example.test/provider", "demo_port_01", "api-key")
    assert calls[1] == ("open", "https://example.test/provider", 4.0)
    assert calls[2] == ("parse", '{"ignored":true}', scenario.model_output_text)


def test_openai_responses_provider_builds_multimodal_request(tmp_path) -> None:
    image_path = tmp_path / "frame.png"
    image_path.write_bytes(base64.b64decode(_PNG_1X1_BASE64))
    provider = OpenAIResponsesCandidateProvider()
    payload = PromptedCandidateModel(
        model_version="gpt-4.1-mini",
        backend=_RecordingBackend(raw_text="{}"),
    ).build_payload(
        asset=_asset(),
        scenario=_scenario(),
        current=_current_frame_with_image(str(image_path)),
        baseline=_baseline_frame_with_image("https://example.test/baseline.png"),
    )

    request = provider.build_request(
        endpoint="https://api.openai.com/v1/responses",
        payload=payload,
        api_key="secret-token",
    )
    body = json.loads(request.data.decode("utf-8"))

    assert request.full_url == "https://api.openai.com/v1/responses"
    assert request.get_header("Authorization") == "Bearer secret-token"
    assert body["model"] == "gpt-4.1-mini"
    assert body["input"][0]["role"] == "system"
    assert body["input"][1]["role"] == "user"
    assert body["input"][1]["content"][0]["type"] == "input_text"
    assert body["input"][1]["content"][1]["type"] == "input_image"
    assert body["input"][1]["content"][1]["image_url"].startswith("data:image/png;base64,")
    assert body["input"][1]["content"][2]["image_url"] == "https://example.test/baseline.png"


def test_openai_responses_provider_parses_output_from_response_body() -> None:
    provider = OpenAIResponsesCandidateProvider()

    text = provider.parse_response(
        body=json.dumps(
            {
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"action":"defer","severity":"medium"}',
                            }
                        ]
                    }
                ]
            }
        ),
        fallback="fallback",
    )

    assert text == '{"action":"defer","severity":"medium"}'


class _RecordingBackend:
    def __init__(self, *, raw_text: str) -> None:
        self.raw_text = raw_text
        self.payload = None
        self.scenario = None

    def generate(self, *, payload, scenario) -> str:
        self.payload = payload
        self.scenario = scenario
        return self.raw_text


class _FakeHTTPResponse:
    def __init__(self, *, body: bytes, status: int = 200) -> None:
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class _FakeProviderRequest:
    def __init__(self, full_url: str) -> None:
        self.full_url = full_url


def _current_frame_with_image(image_ref: str) -> FrameEnvelope:
    frame = _current_frame()
    return frame.model_copy(
        update={"frame": frame.frame.model_copy(update={"image_ref": image_ref})}
    )


def _baseline_frame_with_image(image_ref: str) -> FrameEnvelope:
    frame = _baseline_frame()
    return frame.model_copy(
        update={"frame": frame.frame.model_copy(update={"image_ref": image_ref})}
    )


_PNG_1X1_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9s8m2V0AAAAASUVORK5CYII="
)


def _asset() -> Asset:
    return Asset(
        asset_id="demo_port_01",
        asset_name="Demo Grain Port",
        asset_type="grain_port",
        region="Black Sea",
        latitude=46.501,
        longitude=30.747,
        hero=True,
    )


def _current_frame() -> FrameEnvelope:
    return FrameEnvelope(
        frame=FrameRecord(
            frame_id="cur_demo_port_01_20260414",
            asset_id="demo_port_01",
            captured_at="2026-04-14T18:40:00Z",
            image_ref="fixtures/demo_port_01/current-2026-04-14.png",
            cloud_cover=0.07,
            source="sentinel_current_stub",
        ),
        baseline_frame_id="base_demo_port_01_20250901",
        overlay_ref="fixtures/demo_port_01/overlay-2026-04-14.png",
    )


def _baseline_frame() -> FrameEnvelope:
    return FrameEnvelope(
        frame=FrameRecord(
            frame_id="base_demo_port_01_20250901",
            asset_id="demo_port_01",
            captured_at="2025-09-01T10:00:00Z",
            image_ref="fixtures/demo_port_01/baseline-2025-09-01.png",
            cloud_cover=0.03,
            source="sentinel_baseline_stub",
        ),
    )


def _scenario():
    settings = Settings(
        app_env="test",
        app_port=8000,
        model_version="lfm2.5-vl-450m-prompted",
        simsat_current_endpoint=None,
        simsat_baseline_endpoint=None,
        mapbox_token_present=False,
        watchlist_path=None,
    )
    assets = {asset.asset_id: asset for asset in load_watchlist_assets(settings.watchlist_path)}
    scenarios = build_stub_scenarios(
        settings=settings,
        hero_asset=assets["demo_port_01"],
        bridge_asset=assets["demo_bridge_01"],
    )
    return scenarios["hero_port_disruption"]
