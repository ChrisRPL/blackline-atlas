from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.asset import Asset  # noqa: E402
from app.schemas.lead import Lead  # noqa: E402
from app.schemas.sam3_eval import Sam3EvalCase  # noqa: E402
from app.schemas.sam3_evidence import Sam3EvidenceMask  # noqa: E402
from app.services.sam3_evidence import (  # noqa: E402
    HttpSam3EvidenceBackend,
    prompts_for_asset,
    score_temporal_change_masks,
    source_context_for_lead,
)
from training.scripts import build_sam3_eval_pack  # noqa: E402


class _FakeHTTPResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def test_sam3_http_output_cannot_promote_absent_upstream_alert(monkeypatch) -> None:
    raw_case = build_sam3_eval_pack.build_sam3_eval_pack(max_cases=2)["cases"][1]
    case = Sam3EvalCase.model_validate(raw_case)
    backend = HttpSam3EvidenceBackend(endpoint="https://example.test/sam3")

    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        return _FakeHTTPResponse(
            json.dumps(
                {
                    "asset_id": case.asset.asset_id,
                    "current_frame_id": case.current_frame.frame.frame_id,
                    "baseline_frame_id": case.baseline_frame.frame.frame_id,
                    "current_image_ref": case.current_frame.frame.image_ref,
                    "baseline_image_ref": case.baseline_frame.frame.image_ref,
                    "model_version": "facebook/sam3",
                    "backend": "sam3_http",
                    "decision": "segmentation_ready",
                    "prompts": case.prompts,
                    "masks": [
                        {
                            "label": "flooded or breached water works",
                            "prompt": "flooded or breached water works",
                            "score": 0.96,
                            "bbox_norm": [0.43, 0.0, 1.0, 0.99],
                            "area_ratio": 0.56,
                        }
                    ],
                    "visual_evidence_tags": ["damaged_water_or_power_facility"],
                    "triage_action": "downlink_now",
                    "summary": "Remote SAM3 over-fired on a no-change site.",
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.sam3_evidence.urlopen", fake_urlopen)

    report = backend.analyze(
        asset=case.asset,
        current=case.current_frame,
        baseline=case.baseline_frame,
        alert=None,
        prompts=case.prompts,
        source_context=None,
        model_version="facebook/sam3",
    )

    assert report.decision == "no_evidence"
    assert report.triage_action == "discard"
    assert report.masks == []
    assert report.visual_evidence_tags == []
    assert "suppressed" in report.summary


def test_sam3_prompt_bank_uses_short_visual_concepts() -> None:
    cases = [
        Sam3EvalCase.model_validate(row)
        for row in build_sam3_eval_pack.build_sam3_eval_pack()["cases"]
    ]
    all_prompts = [prompt for case in cases for prompt in prompts_for_asset(case.asset, None)]

    assert "water tank" in all_prompts
    assert "warehouse" in all_prompts
    assert "rubble pile" in all_prompts
    assert "flooded or breached water works" not in all_prompts
    assert "damaged water facility" not in all_prompts
    assert all(len(prompt.split()) <= 3 for prompt in all_prompts)


def test_sam3_prompt_bank_uses_live_conflict_context() -> None:
    asset = Asset(
        asset_id="live_kramatorsk_shelling",
        asset_name="Russian shelling kills two in Kramatorsk residential area",
        asset_type="civilian_building_cluster",
        region="Kramatorsk, Donetsk, Ukraine",
        latitude=48.72,
        longitude=37.56,
    )

    prompts = prompts_for_asset(asset, None)

    assert prompts[:4] == [
        "collapsed building",
        "rubble pile",
        "debris field",
        "crater",
    ]
    assert "civilian building" in prompts
    assert "container yard" not in prompts
    assert all(len(prompt.split()) <= 3 for prompt in prompts)


def test_sam3_prompt_bank_uses_source_event_context() -> None:
    lead = Lead(
        lead_id="gdelt_kherson_damage",
        title="Russian strike hits residential zone in Kherson",
        region="Kherson, Ukraine",
        latitude=46.63,
        longitude=32.61,
        category_guess="civilian_building_cluster",
        status="lead_only",
        summary=(
            "Source report says nearby shops, a pharmacy, and apartment buildings " "were damaged."
        ),
        source_date="2026-04-06",
    )
    asset = Asset(
        asset_id="live_gdelt_kherson_damage",
        asset_name=lead.title,
        asset_type="civilian_building_cluster",
        region=lead.region,
        latitude=lead.latitude,
        longitude=lead.longitude,
    )

    source_context = source_context_for_lead(lead)
    prompts = prompts_for_asset(asset, None, source_context=source_context)

    assert source_context.satellite_relevance == "high"
    assert source_context.ignore_terms[:3] == ["casualties", "fatalities", "injuries"]
    assert prompts[:5] == [
        "rubble pile",
        "debris field",
        "crater",
        "burn scar",
        "apartment block",
    ]
    assert "commercial building" in prompts
    assert all(len(prompt.split()) <= 3 for prompt in prompts)


def test_sam3_source_context_does_not_prompt_for_casualty_only_clash() -> None:
    lead = Lead(
        lead_id="gdelt_clash_only",
        title="Two soldiers killed during close-range clash",
        region="Southern Lebanon",
        latitude=33.1,
        longitude=35.4,
        category_guess="civilian_building_cluster",
        status="lead_only",
        summary="Source report describes casualties and an armed clash, with no damage site.",
        source_date="2026-04-08",
    )

    source_context = source_context_for_lead(lead)

    assert source_context.satellite_relevance == "low"
    assert source_context.target_prompts == []


def test_temporal_scoring_suppresses_whole_tile_false_positive() -> None:
    current_masks = [
        Sam3EvidenceMask(
            label="reservoir",
            prompt="reservoir",
            score=0.96,
            bbox_norm=(0.43, 0.0, 1.0, 0.99),
            area_ratio=0.56,
        )
    ]

    assert score_temporal_change_masks(current_masks=current_masks, baseline_masks=[]) == []


def test_temporal_scoring_keeps_new_damage_prompt() -> None:
    current_masks = [
        Sam3EvidenceMask(
            label="debris field",
            prompt="debris field",
            score=0.82,
            bbox_norm=(0.2, 0.2, 0.35, 0.36),
            area_ratio=0.024,
        )
    ]

    filtered = score_temporal_change_masks(current_masks=current_masks, baseline_masks=[])

    assert len(filtered) == 1
    assert filtered[0].temporal_change_score == 0.82


def test_temporal_scoring_marks_missing_baseline_structure() -> None:
    baseline_masks = [
        Sam3EvidenceMask(
            label="warehouse",
            prompt="warehouse",
            score=0.9,
            bbox_norm=(0.1, 0.1, 0.3, 0.32),
            area_ratio=0.044,
            frame_role="baseline",
        )
    ]

    filtered = score_temporal_change_masks(current_masks=[], baseline_masks=baseline_masks)

    assert len(filtered) == 1
    assert filtered[0].label == "missing warehouse"
    assert filtered[0].frame_role == "baseline"
