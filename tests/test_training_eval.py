from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts import build_dataset, eval_structured_outputs  # noqa: E402


def test_build_replay_pack_freezes_expected_cases() -> None:
    pack = build_dataset.build_replay_pack()

    assert pack["pack_version"] == "hero-replay-v1"
    assert pack["case_count"] == 2
    assert [case["case_id"] for case in pack["cases"]] == [
        "hero_port_disruption",
        "bridge_access_obstruction",
    ]
    assert pack["cases"][0]["hero"] is True
    assert pack["cases"][0]["expected_candidate"]["event_type"] == "probable_large_scale_disruption"
    assert pack["cases"][0]["expected_action"] == "downlink_now"
    assert pack["cases"][1]["expected_action"] == "defer"


def test_write_replay_pack_writes_manifest_and_eval_jsonl(tmp_path: Path) -> None:
    manifest_path, dataset_path = build_dataset.write_replay_pack(tmp_path)

    assert manifest_path.exists()
    assert dataset_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    lines = dataset_path.read_text(encoding="utf-8").strip().splitlines()

    assert manifest["case_count"] == 2
    assert len(lines) == 2
    assert json.loads(lines[0])["case_id"] == "hero_port_disruption"
    assert json.loads(lines[0])["expected_candidate"]["action"] == "downlink_now"
    assert json.loads(lines[1])["expected_metrics"]["alerts_emitted"] == 2


def test_eval_structured_outputs_self_check_passes(tmp_path: Path) -> None:
    _, dataset_path = build_dataset.write_replay_pack(tmp_path)

    summary = eval_structured_outputs.evaluate_dataset(dataset_path)

    assert summary["passed"] is True
    assert summary["metrics"]["pass_count"] == 2
    assert summary["metrics"]["json_valid"] == 2
    assert summary["metrics"]["schema_valid"] == 2
    assert summary["metrics"]["bbox_valid"] == 2
    assert summary["metrics"]["core_fields_match"] == 2
    assert summary["metrics"]["action_match"] == 2
    assert summary["expected_action_counts"] == {
        "discard": 0,
        "defer": 1,
        "downlink_now": 1,
    }


def test_eval_structured_outputs_flags_invalid_json_and_wrong_action(tmp_path: Path) -> None:
    _, dataset_path = build_dataset.write_replay_pack(tmp_path)
    cases = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    broken_predictions = [
        {
            "case_id": cases[0]["case_id"],
            "raw_output": '{"alert_id":"broken"',
        },
        {
            "case_id": cases[1]["case_id"],
            "output": {
                **cases[1]["expected_candidate"],
                "action": "downlink_now",
                "bbox": [0.9, 0.18, 0.68, 1.1],
            },
        },
    ]
    predictions_path = tmp_path / "predictions.jsonl"
    predictions_path.write_text(
        "".join(json.dumps(entry) + "\n" for entry in broken_predictions),
        encoding="utf-8",
    )

    summary = eval_structured_outputs.evaluate_dataset(
        dataset_path,
        predictions_path=predictions_path,
    )

    assert summary["passed"] is False
    assert summary["metrics"]["missing_predictions"] == 0
    assert summary["metrics"]["json_valid"] == 1
    assert summary["metrics"]["schema_valid"] == 0
    assert summary["metrics"]["bbox_valid"] == 0
    assert summary["metrics"]["action_match"] == 0
    assert summary["metrics"]["false_positive_count"] == 0
    assert summary["predicted_action_counts"] == {
        "discard": 0,
        "defer": 0,
        "downlink_now": 0,
    }


def test_eval_structured_outputs_flags_core_field_drift(tmp_path: Path) -> None:
    _, dataset_path = build_dataset.write_replay_pack(tmp_path)
    cases = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    predictions_path = tmp_path / "predictions.jsonl"
    predictions_path.write_text(
        json.dumps(
            {
                "case_id": cases[0]["case_id"],
                "output": {
                    **cases[0]["expected_candidate"],
                    "event_type": "probable_surface_change",
                },
            }
        )
        + "\n"
        + json.dumps(
            {
                "case_id": cases[1]["case_id"],
                "output": cases[1]["expected_candidate"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = eval_structured_outputs.evaluate_dataset(
        dataset_path,
        predictions_path=predictions_path,
    )

    assert summary["passed"] is False
    assert summary["metrics"]["core_fields_match"] == 1
    assert summary["metrics"]["action_match"] == 2
    assert "event_type expected" in summary["cases"][0]["errors"][0]


def test_eval_structured_outputs_repairs_safe_discard_array_predictions(tmp_path: Path) -> None:
    _, dataset_path = build_dataset.write_replay_pack(tmp_path)
    rows = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows[0]["expected_action"] = "discard"
    rows[0]["expected_candidate"] = {
        "event_type": "no_event",
        "severity": "low",
        "confidence": 0.0,
        "bbox": [0.0, 0.0, 0.1, 0.1],
        "civilian_impact": "no_material_impact",
        "why": "Model returned discard with insufficient disruption evidence.",
        "action": "discard",
    }
    rows[0]["expected_alert"] = {
        **rows[0]["expected_alert"],
        **rows[0]["expected_candidate"],
    }
    dataset_path.write_text(json.dumps(rows[0]) + "\n", encoding="utf-8")
    predictions_path = tmp_path / "predictions.jsonl"
    predictions_path.write_text(
        json.dumps(
            {
                "case_id": rows[0]["case_id"],
                "raw_output": (
                    '[{"bbox":[0.0,0.0,0.1,0.1],"confidence":0.0,' '"action":"discard"}]'
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = eval_structured_outputs.evaluate_dataset(
        dataset_path,
        predictions_path=predictions_path,
    )

    assert summary["passed"] is True
    assert summary["metrics"]["schema_valid"] == 1
    assert summary["metrics"]["action_match"] == 1


def test_eval_structured_outputs_scores_evidence_first_rows(tmp_path: Path) -> None:
    _, dataset_path = build_dataset.write_replay_pack(tmp_path)
    rows = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    evidence = {
        "visual_evidence_tags": ["burn_scar", "damaged_port_or_logistics_apron"],
        "evidence_strength": "strong",
        "damage_mechanism": "fire_or_burn",
        "visibility_quality": "clear",
        "negative_type": "none",
        "bbox_norm": [0.19, 0.26, 0.73, 0.84],
        "bbox_quality": "tight",
        "change_confidence": 0.89,
        "civilian_infrastructure_type": "grain_port",
        "event_type": "probable_large_scale_disruption",
        "severity": "high",
        "civilian_impact": "shipping_or_aid_disruption",
        "rationale": "Large terminal burn scar is visible versus baseline.",
        "triage_action": "downlink_now",
    }
    rows[0]["model_output_text"] = json.dumps(evidence)
    rows[0]["expected_evidence_candidate"] = evidence
    rows[0]["expected_candidate"] = {
        "event_type": "probable_large_scale_disruption",
        "severity": "high",
        "confidence": 0.89,
        "bbox": [0.19, 0.26, 0.73, 0.84],
        "civilian_impact": "shipping_or_aid_disruption",
        "why": "Large terminal burn scar is visible versus baseline.",
        "action": "downlink_now",
    }
    evidence_dataset = tmp_path / "evidence.jsonl"
    evidence_dataset.write_text(
        "".join(json.dumps(row) + "\n" for row in rows[:1]),
        encoding="utf-8",
    )

    summary = eval_structured_outputs.evaluate_dataset(evidence_dataset)

    assert summary["passed"] is True
    assert summary["evidence_case_count"] == 1
    assert summary["metrics"]["evidence_schema_valid"] == 1
    assert summary["metrics"]["evidence_tags_match"] == 1
    assert summary["metrics"]["action_match"] == 1


def test_eval_structured_outputs_uses_runtime_guardrails(tmp_path: Path) -> None:
    _, dataset_path = build_dataset.write_replay_pack(tmp_path)
    rows = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows[0]["expected_action"] = "discard"
    rows[0]["expected_candidate"] = {
        "event_type": "no_event",
        "severity": "low",
        "confidence": 0.35,
        "bbox": [0.0, 0.0, 1.0, 1.0],
        "civilian_impact": "no_material_impact",
        "why": "SAR texture difference could be artifact.",
        "action": "discard",
    }
    rows[0]["expected_alert"] = {
        **rows[0]["expected_alert"],
        **rows[0]["expected_candidate"],
    }
    dataset_path.write_text(json.dumps(rows[0]) + "\n", encoding="utf-8")
    predictions_path = tmp_path / "predictions.jsonl"
    predictions_path.write_text(
        json.dumps(
            {
                "case_id": rows[0]["case_id"],
                "raw_output": (
                    '{"visual_evidence_tags":["sar_speckle_or_modality_artifact"],'
                    '"evidence_strength":"weak","damage_mechanism":"modality_artifact",'
                    '"visibility_quality":"cross_modality",'
                    '"negative_type":"sar_speckle_or_modality_artifact",'
                    '"bbox_norm":[0.10,0.10,0.90,0.90],"bbox_quality":"coarse",'
                    '"change_confidence":0.82,"civilian_infrastructure_type":"grain_port",'
                    '"rationale":"SAR texture difference could be artifact.",'
                    '"triage_action":"downlink_now"}'
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = eval_structured_outputs.evaluate_dataset(
        dataset_path,
        predictions_path=predictions_path,
    )

    assert summary["passed"] is True
    assert summary["metrics"]["schema_valid"] == 1
    assert summary["predicted_action_counts"]["discard"] == 1


def test_eval_structured_outputs_fails_empty_dataset(tmp_path: Path) -> None:
    dataset_path = tmp_path / "empty.jsonl"
    dataset_path.write_text("", encoding="utf-8")

    summary = eval_structured_outputs.evaluate_dataset(dataset_path)

    assert summary["passed"] is False
    assert summary["total_cases"] == 0
    assert summary["metrics"]["pass_count"] == 0
