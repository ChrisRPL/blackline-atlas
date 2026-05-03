from __future__ import annotations

import json
from pathlib import Path

from training.scripts import (
    build_sam3_eval_pack,
    eval_sam3_reports,
    run_sam3_inference,
)


def test_sam3_fixture_inference_and_eval_pass(tmp_path: Path) -> None:
    _, dataset_path = build_sam3_eval_pack.write_sam3_eval_pack(
        output_dir=tmp_path,
        max_cases=8,
    )
    reports_path = tmp_path / "reports.jsonl"

    inference_summary = run_sam3_inference.run_sam3_inference(
        dataset_path=dataset_path,
        output_path=reports_path,
        backend="fixture",
        model_id="facebook/sam3.1",
    )
    eval_summary = eval_sam3_reports.evaluate_sam3_reports(
        dataset_path=dataset_path,
        reports_path=reports_path,
    )

    assert inference_summary["case_count"] == 8
    assert inference_summary["segmentation_ready"] == 4
    assert inference_summary["no_evidence"] == 4
    assert eval_summary["passed"] is True
    assert eval_summary["metrics"]["pass_count"] == 8
    assert eval_summary["metrics"]["false_positive_count"] == 0


def test_sam3_eval_flags_false_positive_masks(tmp_path: Path) -> None:
    _, dataset_path = build_sam3_eval_pack.write_sam3_eval_pack(
        output_dir=tmp_path,
        max_cases=2,
    )
    rows = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    negative = next(row for row in rows if row["expected_action"] == "discard")
    reports_path = tmp_path / "reports.jsonl"
    reports_path.write_text(
        json.dumps(
            {
                "asset_id": negative["asset"]["asset_id"],
                "current_frame_id": negative["current_frame"]["frame"]["frame_id"],
                "baseline_frame_id": negative["baseline_frame"]["frame"]["frame_id"],
                "model_version": "facebook/sam3.1",
                "backend": "fixture",
                "decision": "segmentation_ready",
                "prompts": negative["prompts"],
                "masks": [
                    {
                        "label": "debris field",
                        "prompt": "debris field",
                        "score": 0.9,
                        "bbox_norm": [0.1, 0.1, 0.4, 0.4],
                        "area_ratio": 0.09,
                    }
                ],
                "visual_evidence_tags": ["debris_field"],
                "triage_action": "downlink_now",
                "summary": "Bad false positive.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = eval_sam3_reports.evaluate_sam3_reports(
        dataset_path=dataset_path,
        reports_path=reports_path,
    )

    assert summary["passed"] is False
    assert summary["metrics"]["false_positive_count"] == 1
    assert summary["metrics"]["missing_reports"] == 1
