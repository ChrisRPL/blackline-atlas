from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts import run_evidence_vlm_sft_eval as evidence_eval  # noqa: E402


class SequenceGenerator:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = iter(outputs)

    def generate(self, case: evidence_eval.EvidenceSFTCase) -> str:
        return next(self.outputs)


def test_run_evidence_sft_eval_scores_schema_action_and_false_positive(tmp_path: Path) -> None:
    dataset_path, positive_payload, negative_payload = _write_sft_dataset(tmp_path)
    false_positive = dict(positive_payload)
    false_positive["rationale"] = "False positive used for evaluator coverage."

    _, summary_path, summary = evidence_eval.run_evidence_sft_eval(
        dataset_path=dataset_path,
        output_dir=tmp_path / "eval",
        generator=SequenceGenerator(
            [
                json.dumps(positive_payload),
                "```json\n" + json.dumps(false_positive) + "\n```",
            ]
        ),
    )

    assert summary_path.exists()
    assert summary["passed"] is False
    assert summary["total_cases"] == 2
    assert summary["metrics"]["json_valid"] == 2
    assert summary["metrics"]["schema_valid"] == 2
    assert summary["metrics"]["evidence_schema_valid"] == 2
    assert summary["metrics"]["action_match"] == 1
    assert summary["metrics"]["false_positive_count"] == 1
    assert summary["expected_action_counts"] == {
        "discard": 1,
        "defer": 0,
        "downlink_now": 1,
    }
    assert summary["predicted_action_counts"]["downlink_now"] == 2
    assert "action mismatch: expected discard, got downlink_now" in summary["cases"][1]["errors"]
    assert negative_payload["triage_action"] == "discard"


def test_run_evidence_sft_eval_passes_on_exact_actions(tmp_path: Path) -> None:
    dataset_path, positive_payload, negative_payload = _write_sft_dataset(tmp_path)

    _, _, summary = evidence_eval.run_evidence_sft_eval(
        dataset_path=dataset_path,
        output_dir=tmp_path / "eval",
        generator=SequenceGenerator([json.dumps(positive_payload), json.dumps(negative_payload)]),
    )

    assert summary["passed"] is True
    assert summary["metrics"]["pass_count"] == 2
    assert summary["rates"]["action_match_rate"] == 1.0


def test_evidence_sft_eval_parse_args_accepts_adapter_and_limit() -> None:
    args = evidence_eval.parse_args(
        [
            "--adapter-ref",
            "ChrisRPL/adapter",
            "--limit",
            "3",
            "--max-new-tokens",
            "128",
        ]
    )

    assert args.adapter_ref == "ChrisRPL/adapter"
    assert args.limit == 3
    assert args.max_new_tokens == 128


def _write_sft_dataset(tmp_path: Path) -> tuple[Path, dict[str, object], dict[str, object]]:
    image_dir = tmp_path / "images"
    (image_dir / "baseline").mkdir(parents=True)
    (image_dir / "current").mkdir(parents=True)
    for image_name in (
        "baseline/positive_baseline.png",
        "current/positive_current.png",
        "baseline/negative_baseline.png",
        "current/negative_current.png",
    ):
        (image_dir / image_name).write_bytes(b"placeholder")

    positive_payload: dict[str, object] = {
        "visual_evidence_tags": ["blast_or_crater_scarring"],
        "evidence_strength": "strong",
        "damage_mechanism": "explosion_blast",
        "visibility_quality": "good",
        "negative_type": "none",
        "bbox_norm": [0.1, 0.2, 0.5, 0.6],
        "bbox_quality": "tight",
        "change_confidence": 0.82,
        "civilian_infrastructure_type": "port_logistics_apron",
        "rationale": "Strong blast evidence with tight localization.",
        "triage_action": "downlink_now",
    }
    negative_payload: dict[str, object] = {
        "visual_evidence_tags": ["no_visible_change"],
        "evidence_strength": "none",
        "damage_mechanism": "none",
        "visibility_quality": "good",
        "negative_type": "unchanged_control",
        "bbox_norm": None,
        "bbox_quality": "null",
        "change_confidence": 0.05,
        "civilian_infrastructure_type": "none",
        "rationale": "No visible disruption compared with baseline.",
        "triage_action": "discard",
    }
    rows = [
        _sft_row(
            row_id="positive",
            images=[
                "images/baseline/positive_baseline.png",
                "images/current/positive_current.png",
            ],
            payload=positive_payload,
        ),
        _sft_row(
            row_id="negative",
            images=[
                "images/baseline/negative_baseline.png",
                "images/current/negative_current.png",
            ],
            payload=negative_payload,
        ),
    ]
    dataset_path = tmp_path / "eval_gold_sft.jsonl"
    dataset_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return dataset_path, positive_payload, negative_payload


def _sft_row(
    *,
    row_id: str,
    images: list[str],
    payload: dict[str, object],
) -> dict[str, object]:
    return {
        "row_id": row_id,
        "images": images,
        "messages": [
            {"role": "system", "content": "Evidence-first satellite triage."},
            {"role": "user", "content": "Compare baseline and current."},
            {"role": "assistant", "content": json.dumps(payload)},
        ],
        "source_event": "unit-test",
        "location_name": "test-site",
    }
