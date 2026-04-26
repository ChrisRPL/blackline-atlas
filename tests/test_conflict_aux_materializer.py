from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts.materialize_conflict_disruption_aux_slice import (  # noqa: E402
    materialize_conflict_disruption_aux_slice,
    render_validation_report,
    validate_conflict_aux_artifact,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-image"
DEFAULT_BBOX = object()


def test_conflict_aux_materializer_validates_and_writes_blackline_rows(tmp_path: Path) -> None:
    source_root = _write_artifact(
        tmp_path,
        train_events=("ukraine-hospital-strike", "gaza-control"),
        eval_events=("sudan-hospital-strike",),
    )

    validation = validate_conflict_aux_artifact(source_root=source_root)
    report = render_validation_report(validation)

    assert validation["valid"] is True
    assert validation["row_counts"] == {"eval": 1, "train": 2}
    assert validation["action_counts"]["train"] == {"discard": 1, "downlink_now": 1}
    assert "split_event_overlap: `[]`" in report

    dataset_path, summary_path = materialize_conflict_disruption_aux_slice(
        source_root=source_root,
        output_dir=tmp_path / "out",
    )

    rows = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines()]
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert len(rows) == 2
    assert rows[0]["split"] == "train"
    assert rows[0]["expected_action"] == "downlink_now"
    assert rows[0]["expected_candidate"]["event_type"] == "probable_large_scale_disruption"
    assert rows[0]["asset"]["asset_type"] == "medical_aid_node"
    assert (dataset_path.parent / rows[0]["current_image_path"]).exists()
    assert summary["row_count"] == 2
    assert summary["validation"]["valid"] is True


def test_conflict_aux_validator_rejects_event_overlap(tmp_path: Path) -> None:
    source_root = _write_artifact(
        tmp_path,
        train_events=("shared-event", "train-control"),
        eval_events=("shared-event",),
    )

    validation = validate_conflict_aux_artifact(source_root=source_root)

    assert validation["valid"] is False
    assert validation["split_event_overlap"] == ["shared-event"]
    assert any("event split overlap" in issue["message"] for issue in validation["issues"])


def test_conflict_aux_materializer_allows_null_bbox_for_defer_rows(tmp_path: Path) -> None:
    source_root = _write_artifact(
        tmp_path,
        train_events=("train-ambiguous", "train-control"),
        eval_events=("eval-positive",),
        first_action="defer",
        first_category="ambiguous_or_low_visibility",
        first_bbox=None,
    )

    validation = validate_conflict_aux_artifact(source_root=source_root)
    dataset_path, _ = materialize_conflict_disruption_aux_slice(
        source_root=source_root,
        output_dir=tmp_path / "out",
        validation=validation,
    )

    rows = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines()]
    assert validation["valid"] is True
    assert validation["issue_counts"] == {"warning": 1}
    assert rows[0]["expected_action"] == "defer"
    assert rows[0]["expected_candidate"]["bbox"] == [0.05, 0.05, 0.95, 0.95]
    assert rows[0]["expected_candidate"]["civilian_impact"] == "civilian_facility_disruption"


def _write_artifact(
    tmp_path: Path,
    *,
    train_events: tuple[str, str],
    eval_events: tuple[str],
    first_action: str = "downlink_now",
    first_category: str = "conflict_hospital_damage",
    first_bbox: object = DEFAULT_BBOX,
) -> Path:
    source_root = tmp_path / "artifact"
    for directory in ("images/baseline", "images/current"):
        (source_root / directory).mkdir(parents=True)

    train_rows = [
        _row(
            example_id="train_positive",
            source_event=train_events[0],
            action=first_action,
            category=first_category,
            bbox=[0.2, 0.2, 0.8, 0.8] if first_bbox is DEFAULT_BBOX else first_bbox,
        ),
        _row(
            example_id="train_control",
            source_event=train_events[1],
            action="discard",
            category="no_visible_disruption",
            bbox=None,
        ),
    ]
    eval_rows = [
        _row(
            example_id="eval_positive",
            source_event=eval_events[0],
            action="downlink_now",
            category="conflict_building_damage",
            bbox=[0.1, 0.1, 0.7, 0.7],
        )
    ]
    for row in [*train_rows, *eval_rows]:
        (source_root / row["baseline_image"]).write_bytes(PNG_BYTES)
        (source_root / row["current_image"]).write_bytes(PNG_BYTES)

    _write_jsonl(source_root / "train_flat.jsonl", train_rows)
    _write_jsonl(source_root / "eval_flat.jsonl", eval_rows)
    _write_jsonl(source_root / "train_sft.jsonl", [_sft_row(row) for row in train_rows])
    _write_jsonl(source_root / "eval_sft.jsonl", [_sft_row(row) for row in eval_rows])
    return source_root


def _row(
    *,
    example_id: str,
    source_event: str,
    action: str,
    category: str,
    bbox: list[float] | None,
) -> dict[str, object]:
    return {
        "example_id": example_id,
        "baseline_image": f"images/baseline/{example_id}_baseline.png",
        "current_image": f"images/current/{example_id}_current.png",
        "target_output": {
            "action": action,
            "category": category,
            "rationale": "Conflict damage is visible at civilian scale.",
            "bbox_norm": bbox,
        },
        "source_dataset": "unit-test-conflict-source",
        "source_event": source_event,
        "source_image_name": f"{example_id}.png",
        "provenance": "https://example.test/source",
        "modality": "optical-to-optical",
        "location_name": "Example City",
        "country": "Ukraine",
        "conflict_context": "Reported strike damage to civilian infrastructure.",
        "baseline_date": "2021-01-01",
        "current_date": "2022-01-01",
        "license": "test-only",
        "label_method": "manual-review",
        "damage_ratio": 0.5,
        "destruction_ratio": 0.2,
    }


def _sft_row(row: dict[str, object]) -> dict[str, object]:
    return {
        "example_id": row["example_id"],
        "images": [row["baseline_image"], row["current_image"]],
        "messages": [
            {"role": "system", "content": "Return strict JSON only."},
            {"role": "user", "content": "Compare baseline and current."},
            {"role": "assistant", "content": json.dumps(row["target_output"], sort_keys=True)},
        ],
        "source_dataset": row["source_dataset"],
        "provenance": row["provenance"],
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
