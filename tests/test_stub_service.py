from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from app.core.config import Settings
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

    monkeypatch.setattr("app.services.model_wrapper.urlopen", fake_urlopen)
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
