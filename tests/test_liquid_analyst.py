from __future__ import annotations

import json

from app.schemas.asset import Asset
from app.schemas.frame import FrameEnvelope, FrameRecord
from app.schemas.sam3_evidence import Sam3EvidenceMask, Sam3EvidenceReport, Sam3SourceContext
from app.services.liquid_analyst import (
    FixtureLiquidAnalystBackend,
    _build_payload,
    parse_liquid_analyst_report,
)


def test_liquid_analyst_parser_accepts_strict_civilian_json() -> None:
    report = parse_liquid_analyst_report(
        json.dumps(
            {
                "visible_change_summary": "Large warehouse apron damage is visible.",
                "civilian_disruption_evidence": ["damaged_port_or_logistics_apron"],
                "negative_evidence": [],
                "uncertainty_factors": ["some smoke or haze"],
                "severity_hint": "high",
                "recommended_action": "downlink",
                "confidence": 0.82,
                "short_rationale": "The current frame shows new logistics apron disruption.",
            }
        ),
        asset=_asset(),
        current=_current_frame(),
        baseline=_baseline_frame(),
        evidence=_evidence(),
        model_version="LiquidAI/LFM2.5-VL-450M",
        backend="liquid_vlm_http",
    )

    assert report is not None
    assert report.severity_hint == "severe"
    assert report.recommended_action == "downlink_now"
    assert report.backend == "liquid_vlm_http"
    assert report.civilian_disruption_evidence == ["damaged_port_or_logistics_apron"]


def test_liquid_analyst_parser_rejects_tactical_language() -> None:
    report = parse_liquid_analyst_report(
        json.dumps(
            {
                "visible_change_summary": "Possible troop convoy target near the site.",
                "civilian_disruption_evidence": ["damaged_bridge_or_access_span"],
                "negative_evidence": [],
                "uncertainty_factors": [],
                "severity_hint": "moderate",
                "recommended_action": "defer",
                "confidence": 0.7,
                "short_rationale": "Mentions a target and convoy, which is out of scope.",
            }
        ),
        asset=_asset(),
        current=_current_frame(),
        baseline=_baseline_frame(),
        evidence=_evidence(),
        model_version="LiquidAI/LFM2.5-VL-450M",
        backend="liquid_vlm_http",
    )

    assert report is None


def test_liquid_analyst_parser_repairs_common_local_vlm_drift() -> None:
    report = parse_liquid_analyst_report(
        json.dumps(
            {
                "visible_change_summary": "The current image is mostly obscured by cloud.",
                "civilian_disruption_evidence": ["destroyed building", "crater"],
                "negative_evidence": ["cloud cover"],
                "uncertainty_factors": ["cloud"],
                "severity_hint": "no change",
                "recommended_action": "ignore",
                "confidence": "12%",
                "short_rationale": "Visibility is too poor for a defensible read.",
            }
        ),
        asset=_asset(),
        current=_current_frame(),
        baseline=_baseline_frame(),
        evidence=None,
        model_version="LiquidAI/LFM2.5-VL-450M-MLX-4bit",
        backend="liquid_vlm_http",
    )

    assert report is not None
    assert report.recommended_action == "discard"
    assert report.confidence == 0.12
    assert report.civilian_disruption_evidence == [
        "collapsed_building",
        "blast_or_crater_scarring",
    ]
    assert report.negative_evidence == ["low_visibility"]


def test_liquid_analyst_parser_repairs_copied_severity_options() -> None:
    report = parse_liquid_analyst_report(
        json.dumps(
            {
                "visible_change_summary": "No visible change.",
                "civilian_disruption_evidence": [],
                "negative_evidence": [],
                "uncertainty_factors": [],
                "severity_hint": "none | low | moderate | severe",
                "recommended_action": "discard",
                "confidence": 0.0,
                "short_rationale": "No defensible disruption detected.",
            }
        ),
        asset=_asset(),
        current=_current_frame(),
        baseline=_baseline_frame(),
        evidence=None,
        model_version="LiquidAI/LFM2.5-VL-450M-MLX-4bit",
        backend="liquid_vlm_http",
    )

    assert report is not None
    assert report.severity_hint == "none"
    assert report.recommended_action == "discard"


def test_liquid_analyst_payload_is_schema_first_not_input_dump() -> None:
    payload = _build_payload(
        asset=_asset(),
        current=_current_frame(),
        baseline=_baseline_frame(),
        evidence=None,
        model_version="LiquidAI/LFM2.5-VL-450M-MLX-4bit",
    )

    user_text = next(
        item.text for item in payload.inputs if item.type == "input_text" and item.role == "user"
    )
    assert "Return exactly this JSON shape" in user_text
    assert '"asset_id"' not in user_text
    assert "Do not repeat the input" not in user_text
    assert [item.role for item in payload.inputs if item.type == "input_image"] == [
        "baseline",
        "current",
    ]


def test_liquid_analyst_payload_uses_source_context_as_visual_brief() -> None:
    payload = _build_payload(
        asset=_asset(),
        current=_current_frame(),
        baseline=_baseline_frame(),
        evidence=_evidence(
            source_context=Sam3SourceContext(
                title="Strike damages shops and apartment buildings in Kherson",
                summary="Source report mentions damaged shops, a pharmacy, and apartments.",
                region="Kherson, Ukraine",
                satellite_relevance="high",
                target_prompts=["apartment block", "commercial building", "rubble pile"],
                ignore_terms=["casualties", "soldiers"],
                rationale="Source context mentions visible physical damage.",
            )
        ),
        model_version="LiquidAI/LFM2.5-VL-450M-MLX-4bit",
    )

    user_text = next(
        item.text for item in payload.inputs if item.type == "input_text" and item.role == "user"
    )
    system_text = next(
        item.text for item in payload.inputs if item.type == "input_text" and item.role == "system"
    )

    assert "The source report is context, not something to validate from imagery" in system_text
    assert "Source event: Strike damages shops" in user_text
    assert (
        "Dynamic SAM3 prompts: ['apartment block', 'commercial building', 'rubble pile']"
        in user_text
    )
    assert "Do not say the source report is proven by imagery" in user_text


def test_fixture_liquid_analyst_uses_sam3_evidence_without_becoming_detector() -> None:
    backend = FixtureLiquidAnalystBackend()

    report = backend.analyze(
        asset=_asset(),
        current=_current_frame(),
        baseline=_baseline_frame(),
        evidence=_evidence(),
        alert=None,
        model_version="LiquidAI/LFM2.5-VL-450M",
    )

    assert report.status == "ready"
    assert report.recommended_action == "defer"
    assert report.severity_hint == "moderate"
    assert report.civilian_disruption_evidence == ["damaged_port_or_logistics_apron"]


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


def _evidence(source_context: Sam3SourceContext | None = None) -> Sam3EvidenceReport:
    return Sam3EvidenceReport(
        asset_id="demo_port_01",
        current_frame_id="cur_demo_port_01_20260414",
        baseline_frame_id="base_demo_port_01_20250901",
        current_image_ref="fixtures/demo_port_01/current-2026-04-14.png",
        baseline_image_ref="fixtures/demo_port_01/baseline-2025-09-01.png",
        model_version="facebook/sam3",
        backend="fixture",
        decision="segmentation_ready",
        source_context=source_context,
        prompts=["container yard"],
        masks=[
            Sam3EvidenceMask(
                label="damaged port apron",
                prompt="container yard",
                score=0.74,
                bbox_norm=(0.2, 0.2, 0.42, 0.44),
                area_ratio=0.04,
            )
        ],
        visual_evidence_tags=["damaged_port_or_logistics_apron"],
        triage_action="defer",
        summary="SAM3 fixture evidence shows one candidate disruption mask.",
    )
