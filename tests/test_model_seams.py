from __future__ import annotations

from app.core.config import Settings
from app.schemas.asset import Asset
from app.schemas.frame import FrameEnvelope, FrameRecord
from app.services.model_wrapper import PromptedCandidateModel
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
    assert "alert_id" not in prompt.system
    assert "source" not in prompt.system
    assert "asset_id: demo_port_01" in prompt.user
    assert "frame_id: cur_demo_port_01_20260414" in prompt.user
    assert "frame_id: base_demo_port_01_20250901" in prompt.user
    assert "overlay_ref: fixtures/demo_port_01/overlay-2026-04-14.png" in prompt.user
    assert "action=discard" in prompt.user


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
    assert backend.model_version == "lfm2.5-vl-450m-prompted"
    assert backend.prompt is not None
    assert "candidate, not a full alert" in backend.prompt.system
    assert "Current frame" in backend.prompt.user


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


class _RecordingBackend:
    def __init__(self, *, raw_text: str) -> None:
        self.raw_text = raw_text
        self.prompt = None
        self.model_version = None

    def generate(self, *, prompt, model_version: str, scenario) -> str:
        self.prompt = prompt
        self.model_version = model_version
        self.scenario = scenario
        return self.raw_text


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
