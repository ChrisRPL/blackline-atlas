from __future__ import annotations

from app.schemas.alert import Alert, AlertSource
from app.services.alert_pipeline import StructuredAlertPipeline


def test_structured_alert_pipeline_builds_canonical_alert_from_candidate_json() -> None:
    pipeline = StructuredAlertPipeline(model_version="lfm2.5-vl-450m-prompted")
    alert_seed = Alert(
        alert_id="blk_00017",
        timestamp="2026-04-14T18:40:00Z",
        asset_id="demo_port_01",
        asset_name="Demo Port 01",
        asset_type="grain_port",
        event_type="probable_large_scale_disruption",
        severity="high",
        confidence=0.89,
        bbox=(0.19, 0.26, 0.73, 0.84),
        civilian_impact="shipping_or_aid_disruption",
        why="placeholder",
        action="downlink_now",
        source=AlertSource(
            current_frame_id="cur_demo_port_01_20260414",
            baseline_frame_id="base_demo_port_01_20250901",
            model_version="fixture",
        ),
    )

    resolution = pipeline.resolve(
        raw_output_text=(
            '{"event_type":"probable_large_scale_disruption","severity":"high","confidence":0.89,'
            '"bbox":[0.19,0.26,0.73,0.84],"civilian_impact":"shipping_or_aid_disruption",'
            '"why":"Large terminal footprint change versus baseline near bulk loading berths.",'
            '"action":"downlink_now"}'
        ),
        alert_seed=alert_seed,
        current_frame_id="cur_demo_port_01_20260414",
        baseline_frame_id="base_demo_port_01_20250901",
    )

    assert resolution.reason == "accepted"
    assert resolution.alert is not None
    assert resolution.alert.alert_id == "blk_00017"
    assert resolution.alert.action == "downlink_now"
    assert resolution.alert.source.model_version == "lfm2.5-vl-450m-prompted"


def test_structured_alert_pipeline_rejects_invalid_or_discard_outputs() -> None:
    pipeline = StructuredAlertPipeline(model_version="lfm2.5-vl-450m-prompted")

    invalid = pipeline.resolve(
        raw_output_text='{"event_type":"probable_large_scale_disruption","severity":"high"}',
        alert_seed=None,
        current_frame_id="cur_demo_port_01_20260414",
        baseline_frame_id="base_demo_port_01_20250901",
    )
    discard = pipeline.resolve(
        raw_output_text=(
            "```json\n"
            '{"event_type":"no_event","severity":"low","confidence":0.11,'
            '"bbox":[0.10,0.10,0.40,0.40],"civilian_impact":"no_material_impact",'
            '"why":"No durable disruption visible.","action":"discard"}\n'
            "```"
        ),
        alert_seed=None,
        current_frame_id="cur_demo_port_01_20260414",
        baseline_frame_id="base_demo_port_01_20250901",
    )

    assert invalid.reason == "invalid_model_output"
    assert invalid.alert is None
    assert discard.reason == "model_discarded"
    assert discard.alert is None


def test_structured_alert_pipeline_accepts_evidence_first_candidate_json() -> None:
    pipeline = StructuredAlertPipeline(model_version="lfm2.5-vl-450m-prompted")

    candidate = pipeline.parse_candidate(
        raw_output_text=(
            '{"visual_evidence_tags":["burn_scar","damaged_port_or_logistics_apron"],'
            '"evidence_strength":"strong","damage_mechanism":"fire_or_burn",'
            '"visibility_quality":"clear","negative_type":"none",'
            '"bbox_norm":[0.19,0.26,0.73,0.84],"bbox_quality":"tight",'
            '"change_confidence":0.89,"civilian_infrastructure_type":"grain_port",'
            '"event_type":"probable_large_scale_disruption","severity":"high",'
            '"civilian_impact":"shipping_or_aid_disruption",'
            '"rationale":"Large terminal burn scar is visible versus baseline.",'
            '"triage_action":"downlink_now"}'
        )
    )

    assert candidate is not None
    assert candidate.action == "downlink_now"
    assert candidate.confidence == 0.89
    assert candidate.bbox == (0.19, 0.26, 0.73, 0.84)
    assert candidate.why == "Large terminal burn scar is visible versus baseline."


def test_structured_alert_pipeline_derives_alert_fields_from_v2_evidence_only_json() -> None:
    pipeline = StructuredAlertPipeline(model_version="lfm2.5-vl-450m-prompted")

    candidate = pipeline.parse_candidate(
        raw_output_text=(
            '{"visual_evidence_tags":["debris_field"],'
            '"evidence_strength":"strong","damage_mechanism":"airstrike_or_artillery",'
            '"visibility_quality":"excellent","negative_type":"none",'
            '"bbox_norm":[0.25,0.49,0.54,0.59],"bbox_quality":"tight",'
            '"change_confidence":0.914,"civilian_infrastructure_type":"apartment_complex",'
            '"rationale":"Visible debris field affects a civilian apartment complex.",'
            '"triage_action":"downlink_now"}'
        )
    )

    assert candidate is not None
    assert candidate.event_type == "probable_large_scale_disruption"
    assert candidate.severity == "high"
    assert candidate.civilian_impact == "civilian_facility_disruption"
    assert candidate.action == "downlink_now"


def test_structured_alert_pipeline_accepts_common_evidence_aliases() -> None:
    pipeline = StructuredAlertPipeline(model_version="lfm2.5-vl-450m-prompted")

    candidate = pipeline.parse_candidate(
        raw_output_text=(
            '{"visual_evidence_tags":["no_visible_change"],'
            '"evidence_strength":"weak","damage_mechanism":"construction_non_conflict",'
            '"visibility_quality":"weak","negative_type":"construction_non_conflict",'
            '"bbox_norm":null,"bbox_quality":"weak_whole_tile",'
            '"change_confidence":0.31,"civilian_infrastructure_type":"none",'
            '"rationale":"Visible change looks non-conflict and weak.",'
            '"triage_action":"discard"}'
        )
    )

    assert candidate is not None
    assert candidate.action == "discard"
    assert candidate.event_type == "no_event"
    assert candidate.bbox == (0.0, 0.0, 1.0, 1.0)


def test_structured_alert_pipeline_repairs_qualitative_confidence_strings() -> None:
    pipeline = StructuredAlertPipeline(model_version="lfm2.5-vl-450m-prompted")

    candidate = pipeline.parse_candidate(
        raw_output_text=(
            '{"event_type":"no_event","severity":"low","confidence":"high",'
            '"bbox":[0.10,0.10,0.40,0.40],"civilian_impact":"no_material_impact",'
            '"why":"No durable disruption visible.","action":"discard"}'
        )
    )

    assert candidate is not None
    assert candidate.confidence == 0.9
    assert candidate.action == "discard"


def test_structured_alert_pipeline_repairs_single_item_discard_arrays() -> None:
    pipeline = StructuredAlertPipeline(model_version="lfm2.5-vl-450m-prompted")

    candidate = pipeline.parse_candidate(
        raw_output_text=('[{"bbox":[0.0,0.0,0.1,0.1],"confidence":0.0,"action":"discard"}]')
    )

    assert candidate is not None
    assert candidate.event_type == "no_event"
    assert candidate.severity == "low"
    assert candidate.civilian_impact == "no_material_impact"
    assert candidate.action == "discard"
