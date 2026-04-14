from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.schemas.alert import Alert, AlertSource
from app.schemas.asset import Asset
from app.schemas.frame import FrameEnvelope, FrameRecord
from app.schemas.metrics import Metrics


@dataclass(frozen=True)
class ScenarioFixture:
    scenario_id: str
    asset_id: str
    current_frame: FrameEnvelope
    baseline_frame: FrameEnvelope
    alerts: list[Alert]
    metrics: Metrics


def build_stub_scenarios(
    *,
    settings: Settings,
    hero_asset: Asset,
    bridge_asset: Asset,
) -> dict[str, ScenarioFixture]:
    hero_current_frame = FrameEnvelope(
        frame=FrameRecord(
            frame_id="cur_demo_port_01_20260414",
            asset_id=hero_asset.asset_id,
            captured_at="2026-04-14T18:40:00Z",
            image_ref="fixtures/demo_port_01/current-2026-04-14.png",
            cloud_cover=0.07,
            source="sentinel_current_stub",
        ),
        baseline_frame_id="base_demo_port_01_20250901",
        overlay_ref="fixtures/demo_port_01/overlay-2026-04-14.png",
    )
    hero_baseline_frame = FrameEnvelope(
        frame=FrameRecord(
            frame_id="base_demo_port_01_20250901",
            asset_id=hero_asset.asset_id,
            captured_at="2025-09-01T10:00:00Z",
            image_ref="fixtures/demo_port_01/baseline-2025-09-01.png",
            cloud_cover=0.03,
            source="sentinel_baseline_stub",
        ),
        baseline_frame_id=None,
        overlay_ref=None,
    )
    bridge_current_frame = FrameEnvelope(
        frame=FrameRecord(
            frame_id="cur_demo_bridge_01_20260414",
            asset_id=bridge_asset.asset_id,
            captured_at="2026-04-14T18:42:00Z",
            image_ref="fixtures/demo_bridge_01/current-2026-04-14.png",
            cloud_cover=0.05,
            source="sentinel_current_stub",
        ),
        baseline_frame_id="base_demo_bridge_01_20251012",
        overlay_ref="fixtures/demo_bridge_01/overlay-2026-04-14.png",
    )
    bridge_baseline_frame = FrameEnvelope(
        frame=FrameRecord(
            frame_id="base_demo_bridge_01_20251012",
            asset_id=bridge_asset.asset_id,
            captured_at="2025-10-12T09:15:00Z",
            image_ref="fixtures/demo_bridge_01/baseline-2025-10-12.png",
            cloud_cover=0.02,
            source="sentinel_baseline_stub",
        ),
        baseline_frame_id=None,
        overlay_ref=None,
    )

    return {
        "hero_port_disruption": ScenarioFixture(
            scenario_id="hero_port_disruption",
            asset_id=hero_asset.asset_id,
            current_frame=hero_current_frame,
            baseline_frame=hero_baseline_frame,
            alerts=[
                Alert(
                    alert_id="blk_00017",
                    timestamp="2026-04-14T18:40:00Z",
                    asset_id=hero_asset.asset_id,
                    asset_name=hero_asset.asset_name,
                    asset_type=hero_asset.asset_type,
                    event_type="probable_large_scale_disruption",
                    severity="high",
                    confidence=0.89,
                    bbox=(0.19, 0.26, 0.73, 0.84),
                    civilian_impact="shipping_or_aid_disruption",
                    why=(
                        "Large terminal footprint change versus baseline "
                        "near bulk loading berths."
                    ),
                    action="downlink_now",
                    source=AlertSource(
                        current_frame_id=hero_current_frame.frame.frame_id,
                        baseline_frame_id=hero_baseline_frame.frame.frame_id,
                        model_version=settings.model_version,
                    ),
                )
            ],
            metrics=Metrics(
                frames_scanned=143,
                alerts_emitted=5,
                raw_frames_suppressed=138,
                downlink_rate=0.035,
            ),
        ),
        "bridge_access_obstruction": ScenarioFixture(
            scenario_id="bridge_access_obstruction",
            asset_id=bridge_asset.asset_id,
            current_frame=bridge_current_frame,
            baseline_frame=bridge_baseline_frame,
            alerts=[
                Alert(
                    alert_id="blk_00018",
                    timestamp="2026-04-14T18:42:00Z",
                    asset_id=bridge_asset.asset_id,
                    asset_name=bridge_asset.asset_name,
                    asset_type=bridge_asset.asset_type,
                    event_type="probable_access_obstruction",
                    severity="medium",
                    confidence=0.78,
                    bbox=(0.31, 0.18, 0.68, 0.71),
                    civilian_impact="public_mobility_disruption",
                    why=(
                        "Bridge deck access appears partially obstructed " "versus stable baseline."
                    ),
                    action="defer",
                    source=AlertSource(
                        current_frame_id=bridge_current_frame.frame.frame_id,
                        baseline_frame_id=bridge_baseline_frame.frame.frame_id,
                        model_version=settings.model_version,
                    ),
                )
            ],
            metrics=Metrics(
                frames_scanned=88,
                alerts_emitted=2,
                raw_frames_suppressed=86,
                downlink_rate=0.023,
            ),
        ),
    }
