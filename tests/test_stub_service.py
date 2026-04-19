from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from urllib.error import URLError

from app.core.config import Settings
from app.schemas.agent import AtlasAgentQueryRequest
from app.schemas.replay import ReplayStartRequest
from app.services.frame_filters import FrameFilterPolicy
from app.services.model_wrapper import PromptedCandidateModel
from app.services.prompt_builder import CandidatePromptBuilder
from app.services.sentinel_client import FixtureSentinelPayloadTransport
from app.services.stub import StubAtlasService


def test_stub_service_marks_cloudy_frame_as_suppressed() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )
    service.frame_filter_policy = FrameFilterPolicy(cloud_cover_threshold=0.01)

    frame = service.get_current_frame()
    metrics = service.get_metrics()
    alerts = service.list_alerts()

    assert frame.accepted_for_alerting is False
    assert frame.filter_reason == "cloud_cover_too_high"
    assert frame.overlay_ref is None
    assert metrics.alerts_emitted == 4
    assert metrics.raw_frames_suppressed == 139
    assert metrics.downlink_rate == 0.028
    assert alerts == []


class StaticResponder:
    def __init__(self, raw_output_text: str) -> None:
        self.raw_output_text = raw_output_text

    def generate(self, *, payload, scenario) -> str:
        _ = payload
        _ = scenario
        return self.raw_output_text


def test_stub_service_uses_shared_eval_path_for_invalid_model_output() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )
    hero = service.scenarios["hero_port_disruption"]
    service.scenarios["hero_port_disruption"] = replace(
        hero,
        model_output_text='{"event_type":"probable_large_scale_disruption"}',
    )

    frame = service.get_current_frame()
    metrics = service.get_metrics()
    alerts = service.list_alerts()

    assert frame.accepted_for_alerting is False
    assert frame.filter_reason == "invalid_model_output"
    assert frame.overlay_ref is None
    assert alerts == []
    assert metrics.alerts_emitted == 4
    assert metrics.raw_frames_suppressed == 139
    assert metrics.downlink_rate == 0.028


def test_stub_service_routes_through_model_wrapper() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )
    service.model_wrapper = PromptedCandidateModel(
        model_version="lfm2.5-vl-450m-prompted",
        backend=StaticResponder(
            raw_output_text=(
                '{"event_type":"no_event","severity":"low","confidence":0.11,'
                '"bbox":[0.10,0.10,0.40,0.40],"civilian_impact":"no_material_impact",'
                '"why":"No durable disruption visible.","action":"discard"}'
            )
        ),
        prompt_builder=CandidatePromptBuilder(),
    )

    frame = service.get_current_frame()
    metrics = service.get_metrics()
    alerts = service.list_alerts()

    assert frame.accepted_for_alerting is False
    assert frame.filter_reason == "model_discarded"
    assert frame.overlay_ref is None
    assert alerts == []
    assert metrics.alerts_emitted == 4
    assert metrics.raw_frames_suppressed == 139


def test_stub_service_can_opt_in_model_http_backend(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        assert request.full_url == "https://example.test/model"
        assert timeout == 10.0
        body = json.loads(request.data.decode("utf-8"))
        assert body["scenario_id"] == "hero_port_disruption"
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "output_text": (
                        '{"event_type":"probable_large_scale_disruption","severity":"high",'
                        '"confidence":0.93,"bbox":[0.19,0.26,0.73,0.84],'
                        '"civilian_impact":"shipping_or_aid_disruption",'
                        '"why":"Live backend confirmed macro disruption.","action":"downlink_now"}'
                    )
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            model_endpoint="https://example.test/model",
            model_http_enabled=True,
            model_provider="atlas_json_http",
        )
    )

    frame = service.get_current_frame()
    alerts = service.list_alerts()

    assert frame.accepted_for_alerting is True
    assert frame.filter_reason == "accepted"
    assert alerts[0].confidence == 0.93
    assert alerts[0].why == "Live backend confirmed macro disruption."


def test_stub_service_can_opt_in_openai_responses_model_backend(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        assert request.full_url == "https://api.openai.com/v1/responses"
        assert timeout == 10.0
        body = json.loads(request.data.decode("utf-8"))
        assert body["model"] == "gpt-4.1-mini"
        assert body["input"][0]["role"] == "system"
        assert body["input"][1]["role"] == "user"
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "output_text": (
                        '{"event_type":"probable_large_scale_disruption","severity":"high",'
                        '"confidence":0.91,"bbox":[0.19,0.26,0.73,0.84],'
                        '"civilian_impact":"trade_disruption",'
                        '"why":"OpenAI provider confirmed macro disruption.",'
                        '"action":"downlink_now"}'
                    )
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="gpt-4.1-mini",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            model_endpoint="https://api.openai.com/v1/responses",
            model_http_enabled=True,
            model_provider="openai_responses_http",
            model_api_key="test-key",
        )
    )

    frame = service.get_current_frame()
    alerts = service.list_alerts()

    assert frame.accepted_for_alerting is True
    assert frame.filter_reason == "accepted"
    assert alerts[0].confidence == 0.91
    assert alerts[0].civilian_impact == "trade_disruption"
    assert alerts[0].why == "OpenAI provider confirmed macro disruption."


def test_stub_service_keeps_fixture_only_frames_without_sentinel_endpoints(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    current = service.get_current_frame()
    baseline = service.get_baseline_frame()

    assert current.frame.source == "sentinel_current_stub"
    assert baseline.frame.source == "sentinel_baseline_stub"


def test_stub_service_composes_sentinel_adapters_when_endpoints_are_configured(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="https://example.test/sentinel/current/",
            simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    current = service.get_current_frame()
    baseline = service.get_baseline_frame()

    assert current.frame.source == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=current"
    )
    assert baseline.frame.source == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=baseline"
    )
    assert current.frame.image_ref is not None
    assert baseline.frame.image_ref is not None
    assert tmp_path.joinpath(
        ".cache",
        "frames",
        "demo_port_01",
        "hero_port_disruption",
        "current",
        "cur_demo_port_01_20260414",
        "metadata.json",
    ).exists()
    assert tmp_path.joinpath(
        ".cache",
        "frames",
        "demo_port_01",
        "hero_port_disruption",
        "baseline",
        "base_demo_port_01_20250901",
        "metadata.json",
    ).exists()


def test_stub_service_uses_current_adapter_and_fixture_baseline_with_current_only_endpoint(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="https://example.test/sentinel/current/",
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    current = service.get_current_frame()
    baseline = service.get_baseline_frame()

    assert current.frame.source == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=current"
    )
    assert baseline.frame.source == "sentinel_baseline_stub"
    assert current.frame.image_ref is not None
    assert baseline.frame.image_ref is not None


def test_stub_service_can_opt_in_current_http_transport(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(url: str, timeout: float):
        assert url == (
            "https://example.test/sentinel/current"
            "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=current"
        )
        assert timeout == 5.0
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "frame_id": "live_cur_demo_port_01_20260415",
                    "captured_at": "2026-04-15T07:10:00Z",
                    "image_ref": "live/demo_port_01/current.png",
                    "cloud_cover": 0.11,
                    "baseline_frame_id": "base_demo_port_01_20250901",
                    "overlay_ref": "live/demo_port_01/overlay.png",
                    "accepted_for_alerting": True,
                    "filter_reason": "accepted",
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="https://example.test/sentinel/current/",
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            simsat_current_http_enabled=True,
        )
    )

    current = service.get_current_frame()
    baseline = service.get_baseline_frame()

    assert current.frame.frame_id == "live_cur_demo_port_01_20260415"
    assert current.frame.source == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=current"
    )
    assert current.frame.image_ref is not None
    assert baseline.frame.source == "sentinel_baseline_stub"


def test_stub_service_uses_baseline_adapter_and_fixture_current_with_baseline_only_endpoint(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    current = service.get_current_frame()
    baseline = service.get_baseline_frame()

    assert current.frame.source == "sentinel_current_stub"
    assert baseline.frame.source == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=baseline"
    )
    assert current.frame.image_ref is not None
    assert baseline.frame.image_ref is not None


def test_stub_service_can_opt_in_baseline_http_transport(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(url: str, timeout: float):
        assert url == (
            "https://example.test/sentinel/baseline"
            "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=baseline"
        )
        assert timeout == 5.0
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "frame_id": "live_base_demo_port_01_20250902",
                    "captured_at": "2025-09-02T10:00:00Z",
                    "image_ref": "live/demo_port_01/baseline.png",
                    "cloud_cover": 0.03,
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
            mapbox_token_present=False,
            watchlist_path=None,
            simsat_baseline_http_enabled=True,
        )
    )

    current = service.get_current_frame()
    baseline = service.get_baseline_frame()

    assert current.frame.source == "sentinel_current_stub"
    assert baseline.frame.frame_id == "live_base_demo_port_01_20250902"
    assert baseline.frame.source == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=baseline"
    )
    assert baseline.frame.image_ref is not None


def test_stub_service_keeps_opt_in_sentinel_wiring_across_replay_switch(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="https://example.test/sentinel/current/",
            simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )
    service.start_replay(
        ReplayStartRequest(
            asset_id="demo_bridge_01",
            scenario_id="bridge_access_obstruction",
        )
    )

    current = service.get_current_frame()
    baseline = service.get_baseline_frame()

    assert current.frame.source == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=current"
    )
    assert baseline.frame.source == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=baseline"
    )
    assert current.frame.image_ref is not None
    assert baseline.frame.image_ref is not None
    assert tmp_path.joinpath(
        ".cache",
        "frames",
        "demo_bridge_01",
        "bridge_access_obstruction",
        "current",
        "cur_demo_bridge_01_20260414",
        "metadata.json",
    ).exists()
    assert tmp_path.joinpath(
        ".cache",
        "frames",
        "demo_bridge_01",
        "bridge_access_obstruction",
        "baseline",
        "base_demo_bridge_01_20251012",
        "metadata.json",
    ).exists()


def test_stub_service_uses_fixture_payload_transport_for_baseline_when_configured(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_fetch(self, plan):
        if plan.params["mode"] != "baseline":
            return None
        return {
            "frame_id": "live_base_demo_bridge_01_20251012",
            "captured_at": "2025-10-12T09:15:00Z",
            "image_ref": "live/demo_bridge_01/baseline.png",
            "cloud_cover": 0.02,
        }

    monkeypatch.setattr(FixtureSentinelPayloadTransport, "fetch", fake_fetch)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="https://example.test/sentinel/current/",
            simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )
    service.start_replay(
        ReplayStartRequest(
            asset_id="demo_bridge_01",
            scenario_id="bridge_access_obstruction",
        )
    )

    baseline = service.get_baseline_frame()

    assert baseline.frame.frame_id == "live_base_demo_bridge_01_20251012"
    assert baseline.frame.source == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=baseline"
    )
    assert baseline.frame.image_ref is not None


def test_stub_service_loads_assets_from_watchlist_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "watchlist.json"
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "asset_id": "demo_port_01",
                    "asset_name": "Manifest Grain Port",
                    "asset_type": "grain_port",
                    "region": "Manifest Coast",
                    "latitude": 46.501,
                    "longitude": 30.747,
                    "hero": True,
                },
                {
                    "asset_id": "demo_bridge_01",
                    "asset_name": "Manifest Logistics Bridge",
                    "asset_type": "bridge",
                    "region": "Manifest Danube",
                    "latitude": 45.169,
                    "longitude": 28.801,
                    "hero": False,
                },
            ]
        ),
        encoding="utf-8",
    )
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=str(manifest_path),
        )
    )

    assets = service.list_assets()

    assert [asset.asset_id for asset in assets] == ["demo_port_01", "demo_bridge_01"]
    assert assets[0].asset_name == "Manifest Grain Port"
    assert service.hero_asset.asset_name == "Manifest Grain Port"


def test_stub_service_default_watchlist_includes_real_civilian_sites() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    asset_ids = [asset.asset_id for asset in service.list_assets()]
    asset_by_id = {asset.asset_id: asset for asset in service.list_assets()}

    assert asset_ids[:2] == ["demo_port_01", "demo_bridge_01"]
    assert "beirut_port_01" in asset_ids
    assert "port_sudan_01" in asset_ids
    assert "ras_abu_jarjur_01" in asset_ids
    assert "bahri_water_01" in asset_ids
    assert "silpo_kvitneve_01" in asset_ids
    assert "unhcr_baghdad_01" in asset_ids
    assert "mosul_medical_city_01" in asset_ids
    assert asset_by_id["demo_port_01"].evidence_state == "live_demo"
    assert asset_by_id["beirut_port_01"].evidence_state == "reference_event"
    assert asset_by_id["silpo_kvitneve_01"].evidence_state == "reference_event"
    assert asset_by_id["ras_abu_jarjur_01"].evidence_state == "reference_control"
    assert asset_by_id["bahri_water_01"].evidence_state == "reference_control"
    assert asset_by_id["mosul_medical_city_01"].evidence_state == "reference_control"


def test_stub_service_can_opt_in_http_agent_planner(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        assert request.full_url == "https://example.test/agent"
        assert timeout == 10.0
        body = json.loads(request.data.decode("utf-8"))
        assert body["model_version"] == "lfm2.5-1.2b-instruct"
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "output_text": json.dumps(
                        {
                            "tool": "site_compare",
                            "site_id": "demo_bridge_01",
                        }
                    )
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            agent_endpoint="https://example.test/agent",
            agent_http_enabled=True,
            agent_provider="atlas_json_http",
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(query="compare the bridge"),
    )

    assert response.tool == "site_compare"
    assert response.planner.mode == "live"
    assert response.focus_asset_id == "demo_bridge_01"
    assert response.compare is not None
    assert response.compare.asset_id == "demo_bridge_01"


def test_stub_service_can_opt_in_openai_chat_agent_planner(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        assert request.full_url == "https://liquid.example/v1/chat/completions"
        assert timeout == 10.0
        body = json.loads(request.data.decode("utf-8"))
        assert body["model"] == "LiquidAI/LFM2.5-1.2B-Instruct"
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][1]["role"] == "user"
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "tool": "site_compare",
                                        "site_id": "demo_bridge_01",
                                    }
                                )
                            }
                        }
                    ]
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            agent_model_version="LiquidAI/LFM2.5-1.2B-Instruct",
            agent_endpoint="https://liquid.example/v1/chat/completions",
            agent_http_enabled=True,
            agent_provider="openai_chat_completions_http",
            agent_api_key="liquid-key",
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(query="compare the bridge"),
    )

    assert response.tool == "site_compare"
    assert response.planner.mode == "live"
    assert response.focus_asset_id == "demo_bridge_01"
    assert response.compare is not None
    assert response.compare.asset_id == "demo_bridge_01"


def test_stub_service_resolves_missing_live_planner_site_id_from_query(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "tool": "site_compare",
                                        "area": "Lower Danube",
                                        "category": "bridge",
                                        "site_id": None,
                                        "alert_id": None,
                                    }
                                )
                            }
                        }
                    ]
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            agent_model_version="hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF",
            agent_endpoint="http://127.0.0.1:11434/v1/chat/completions",
            agent_http_enabled=True,
            agent_provider="openai_chat_completions_http",
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(query="compare the bridge"),
    )

    assert response.tool == "site_compare"
    assert response.planner.mode == "live"
    assert response.focus_asset_id == "demo_bridge_01"
    assert response.resolved.site_id == "demo_bridge_01"


def test_stub_service_sanitizes_invalid_live_planner_area_filter(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "tool": "latest_alerts",
                                        "area": "grain_port",
                                        "category": None,
                                        "site_id": None,
                                        "alert_id": "invented-alert",
                                    }
                                )
                            }
                        }
                    ]
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            agent_model_version="hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF",
            agent_endpoint="http://127.0.0.1:11434/v1/chat/completions",
            agent_http_enabled=True,
            agent_provider="openai_chat_completions_http",
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(query="show latest alerts"),
    )

    assert response.tool == "latest_alerts"
    assert response.planner.mode == "live"
    assert response.focus_asset_id == "demo_bridge_01"
    assert response.focus_alert_id == "blk_00018"
    assert response.resolved.area is None


def test_stub_service_drops_spurious_live_planner_category_filter(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "tool": "latest_alerts",
                                        "area": "Black Sea",
                                        "category": "aid_warehouse_cluster",
                                        "site_id": None,
                                        "alert_id": None,
                                    }
                                )
                            }
                        }
                    ]
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            agent_model_version="hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF",
            agent_endpoint="http://127.0.0.1:11434/v1/chat/completions",
            agent_http_enabled=True,
            agent_provider="openai_chat_completions_http",
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(query="show latest alerts near Black Sea"),
    )

    assert response.tool == "latest_alerts"
    assert response.planner.mode == "live"
    assert response.focus_asset_id == "demo_port_01"
    assert response.focus_alert_id == "blk_00017"
    assert response.resolved.area == "Black Sea"
    assert response.resolved.category is None


def test_stub_service_reports_agent_planner_http_fallback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        raise URLError("offline")

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            agent_endpoint="https://example.test/agent",
            agent_http_enabled=True,
            agent_provider="atlas_json_http",
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(query="show biggest disruptions"),
    )

    assert response.tool == "biggest_disruptions"
    assert response.planner.mode == "fallback"
    assert response.planner.reason == "planner_http_failed"


def test_stub_service_reports_agent_planner_invalid_json_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        return _FakeHTTPResponse(body=b'{"output_text":"not-json"}')

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            agent_endpoint="https://example.test/agent",
            agent_http_enabled=True,
            agent_provider="atlas_json_http",
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(query="compare the bridge"),
    )

    assert response.tool == "site_compare"
    assert response.planner.mode == "fallback"
    assert response.planner.reason == "planner_invalid_json"


def test_stub_service_site_compare_returns_reference_event_for_seeded_real_site() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", site_id="beirut_port_01"),
    )

    assert response.status == "ok"
    assert response.tool == "site_compare"
    assert response.focus_asset_id == "beirut_port_01"
    assert response.focus_alert_id == "blk_nd_00001"
    assert response.compare is not None
    assert response.compare.current_frame.accepted_for_alerting is True
    assert "reference event evidence" in response.summary
    assert response.resolved.site_id == "beirut_port_01"


def test_stub_service_site_compare_returns_reference_control_for_seeded_water_site() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", site_id="ras_abu_jarjur_01"),
    )

    assert response.status == "ok"
    assert response.tool == "site_compare"
    assert response.focus_asset_id == "ras_abu_jarjur_01"
    assert response.focus_alert_id is None
    assert response.compare is not None
    assert response.compare.current_frame.accepted_for_alerting is False
    assert response.alerts == []
    assert "No material change" in response.summary


def test_stub_service_site_compare_returns_reference_event_for_seeded_food_site() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", site_id="silpo_kvitneve_01"),
    )

    assert response.status == "ok"
    assert response.tool == "site_compare"
    assert response.focus_asset_id == "silpo_kvitneve_01"
    assert response.focus_alert_id == "blk_nd_00010"
    assert response.compare is not None
    assert response.compare.current_frame.accepted_for_alerting is True
    assert response.alerts[0].civilian_impact == "trade_disruption"
    assert "reference event evidence" in response.summary


class _FakeHTTPResponse:
    def __init__(self, *, body: bytes, status: int = 200) -> None:
        self.status = status
        self._body = body

    def __enter__(self) -> _FakeHTTPResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self.status
