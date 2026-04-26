from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.alert import Action, AlertCandidate  # noqa: E402
from app.schemas.asset import Asset, AssetType  # noqa: E402
from training.scripts.external_benchmark_normalizer import (  # noqa: E402
    build_candidate_eval_record,
    slugify,
    write_external_candidate_eval_slice,
)

DEFAULT_OUTPUT_DIR = (
    ROOT / "training" / "eval_runs" / "aux-train-inputs" / "satellite_disruption_aux_v1_3"
)
DEFAULT_SUMMARY_NAME = "summary.json"
DEFAULT_REPORT_NAME = "validation_report.md"
FLAT_FILES = {"train": "train_flat.jsonl", "eval": "eval_flat.jsonl"}
SFT_FILES = {"train": "train_sft.jsonl", "eval": "eval_sft.jsonl"}
VALID_ACTIONS = {"discard", "defer", "downlink_now"}
VALID_CATEGORIES = {
    "conflict_building_damage",
    "conflict_hospital_damage",
    "conflict_food_logistics_damage",
    "conflict_water_infrastructure_damage",
    "conflict_bridge_or_access_damage",
    "conflict_port_or_silo_damage",
    "conflict_urban_area_damage",
    "explosion_damage",
    "no_visible_disruption",
    "ambiguous_or_low_visibility",
    "other_conflict_civilian_disruption",
}
VALID_MODALITIES = {"optical-to-optical", "optical-to-SAR", "SAR-to-SAR", "other"}
NO_EVENT_BBOX = (0.01, 0.01, 0.02, 0.02)
AMBIGUOUS_REVIEW_BBOX = (0.05, 0.05, 0.95, 0.95)
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and materialize ML-intern's conflict-focused satellite-disruption "
            "auxiliary artifact into Blackline candidate-eval train rows."
        )
    )
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--include-eval-split",
        action="store_true",
        help="Also materialize eval_flat.jsonl as train rows. Default: train only.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate the artifact and write validation_report.md.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    validation = validate_conflict_aux_artifact(source_root=args.source_root)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / DEFAULT_REPORT_NAME
    report_path.write_text(render_validation_report(validation), encoding="utf-8")
    print(f"wrote {report_path}")
    if not validation["valid"]:
        print(json.dumps(validation["issue_counts"], sort_keys=True))
        return 1
    if args.validate_only:
        return 0

    dataset_path, summary_path = materialize_conflict_disruption_aux_slice(
        source_root=args.source_root,
        output_dir=args.output_dir,
        include_eval_split=args.include_eval_split,
        validation=validation,
    )
    print(f"wrote {dataset_path}")
    print(f"wrote {summary_path}")
    return 0


def materialize_conflict_disruption_aux_slice(
    *,
    source_root: Path,
    output_dir: Path,
    include_eval_split: bool = False,
    validation: dict[str, Any] | None = None,
    summary_name: str = DEFAULT_SUMMARY_NAME,
) -> tuple[Path, Path]:
    validation = validation or validate_conflict_aux_artifact(source_root=source_root)
    if not validation["valid"]:
        raise ValueError("conflict auxiliary artifact failed validation")

    flat_files = ["train_flat.jsonl"]
    if include_eval_split:
        flat_files.append("eval_flat.jsonl")

    records = []
    action_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    country_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    modality_counts: Counter[str] = Counter()

    for flat_file in flat_files:
        for row in _load_rows(source_root / flat_file):
            records.append(_build_record(source_root=source_root, row=row))
            target = row["target_output"]
            action_counts[str(target["action"])] += 1
            category_counts[str(target["category"])] += 1
            country_counts[str(row.get("country") or "unknown")] += 1
            source_counts[str(row.get("source_dataset") or "unknown")] += 1
            modality_counts[str(row.get("modality") or "unknown")] += 1

    dataset_path = write_external_candidate_eval_slice(records=records, output_dir=output_dir)
    summary_path = output_dir / summary_name
    summary_path.write_text(
        json.dumps(
            {
                "version": "satellite-disruption-conflict-aux-v1.3-blackline-v1",
                "source_root": str(source_root),
                "row_count": len(records),
                "included_flat_files": flat_files,
                "split": "train",
                "action_counts": dict(sorted(action_counts.items())),
                "category_counts": dict(sorted(category_counts.items())),
                "country_counts": dict(sorted(country_counts.items())),
                "source_counts": dict(sorted(source_counts.items())),
                "modality_counts": dict(sorted(modality_counts.items())),
                "validation": {
                    "valid": validation["valid"],
                    "issue_counts": validation["issue_counts"],
                    "split_overlap_count": len(validation["split_event_overlap"]),
                },
                "notes": [
                    "Auxiliary-train only. Keep separate from core Blackline gold metrics.",
                    "Conflict-focused public transfer data, not canonical Blackline truth.",
                    (
                        "Rows are accepted only after schema, image, bbox, and event-held-out "
                        "validation pass."
                    ),
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return dataset_path, summary_path


def validate_conflict_aux_artifact(*, source_root: Path) -> dict[str, Any]:
    issues: list[dict[str, object]] = []
    flat_rows: dict[str, list[dict[str, object]]] = {}
    sft_rows: dict[str, list[dict[str, object]]] = {}
    split_events: dict[str, set[str]] = {"train": set(), "eval": set()}
    action_counts: dict[str, Counter[str]] = {"train": Counter(), "eval": Counter()}
    category_counts: dict[str, Counter[str]] = {"train": Counter(), "eval": Counter()}
    country_counts: dict[str, Counter[str]] = {"train": Counter(), "eval": Counter()}
    modality_counts: dict[str, Counter[str]] = {"train": Counter(), "eval": Counter()}

    for split, filename in FLAT_FILES.items():
        path = source_root / filename
        if not path.exists():
            _add_issue(issues, "error", filename, None, "missing required flat JSONL")
            flat_rows[split] = []
            continue
        rows = _load_rows(path)
        flat_rows[split] = rows
        seen_ids: set[str] = set()
        for row_index, row in enumerate(rows, start=1):
            _validate_flat_row(
                source_root=source_root,
                split=split,
                row=row,
                row_index=row_index,
                seen_ids=seen_ids,
                split_events=split_events,
                action_counts=action_counts,
                category_counts=category_counts,
                country_counts=country_counts,
                modality_counts=modality_counts,
                issues=issues,
            )

    for split, filename in SFT_FILES.items():
        path = source_root / filename
        if not path.exists():
            _add_issue(issues, "error", filename, None, "missing required SFT JSONL")
            sft_rows[split] = []
            continue
        rows = _load_rows(path)
        sft_rows[split] = rows
        _validate_sft_rows(
            split=split,
            rows=rows,
            flat_rows=flat_rows.get(split, []),
            filename=filename,
            issues=issues,
        )

    overlap = sorted(split_events["train"] & split_events["eval"])
    for event in overlap:
        _add_issue(issues, "error", "train/eval", None, f"event split overlap: {event}")

    issue_counts = Counter(str(issue["severity"]) for issue in issues)
    return {
        "valid": issue_counts["error"] == 0,
        "issue_counts": dict(sorted(issue_counts.items())),
        "issues": issues,
        "row_counts": {split: len(rows) for split, rows in flat_rows.items()},
        "action_counts": _nested_counter_dict(action_counts),
        "category_counts": _nested_counter_dict(category_counts),
        "country_counts": _nested_counter_dict(country_counts),
        "modality_counts": _nested_counter_dict(modality_counts),
        "split_event_counts": {split: len(events) for split, events in split_events.items()},
        "split_event_overlap": overlap,
    }


def render_validation_report(validation: dict[str, Any]) -> str:
    lines = [
        "# Conflict Auxiliary Dataset Validation",
        "",
        f"- valid: `{str(validation['valid']).lower()}`",
        f"- row_counts: `{json.dumps(validation['row_counts'], sort_keys=True)}`",
        f"- action_counts: `{json.dumps(validation['action_counts'], sort_keys=True)}`",
        f"- category_counts: `{json.dumps(validation['category_counts'], sort_keys=True)}`",
        f"- country_counts: `{json.dumps(validation['country_counts'], sort_keys=True)}`",
        f"- modality_counts: `{json.dumps(validation['modality_counts'], sort_keys=True)}`",
        f"- split_event_counts: `{json.dumps(validation['split_event_counts'], sort_keys=True)}`",
        f"- split_event_overlap: `{json.dumps(validation['split_event_overlap'])}`",
        "",
        "## Issues",
        "",
    ]
    if not validation["issues"]:
        lines.append("- none")
    else:
        for issue in validation["issues"]:
            row = issue["row"] if issue["row"] is not None else "-"
            lines.append(
                f"- `{issue['severity']}` `{issue['file']}` row `{row}`: {issue['message']}"
            )
    return "\n".join(lines) + "\n"


def _validate_flat_row(
    *,
    source_root: Path,
    split: str,
    row: dict[str, Any],
    row_index: int,
    seen_ids: set[str],
    split_events: dict[str, set[str]],
    action_counts: dict[str, Counter[str]],
    category_counts: dict[str, Counter[str]],
    country_counts: dict[str, Counter[str]],
    modality_counts: dict[str, Counter[str]],
    issues: list[dict[str, object]],
) -> None:
    filename = FLAT_FILES[split]
    example_id = row.get("example_id")
    if not isinstance(example_id, str) or not example_id:
        _add_issue(issues, "error", filename, row_index, "example_id must be a non-empty string")
    elif example_id in seen_ids:
        _add_issue(issues, "error", filename, row_index, f"duplicate example_id: {example_id}")
    else:
        seen_ids.add(example_id)

    target = row.get("target_output")
    if not isinstance(target, dict):
        _add_issue(issues, "error", filename, row_index, "target_output must be an object")
        return

    action = target.get("action")
    category = target.get("category")
    bbox = target.get("bbox_norm")
    if action not in VALID_ACTIONS:
        _add_issue(issues, "error", filename, row_index, f"invalid action: {action}")
    else:
        action_counts[split][str(action)] += 1
    if category not in VALID_CATEGORIES:
        _add_issue(issues, "error", filename, row_index, f"invalid category: {category}")
    else:
        category_counts[split][str(category)] += 1
    if not isinstance(target.get("rationale"), str) or not target.get("rationale"):
        _add_issue(issues, "error", filename, row_index, "rationale must be non-empty")
    if action != "discard" and bbox is None:
        _add_issue(
            issues,
            "warning",
            filename,
            row_index,
            "non-discard row has null bbox_norm; materializer will use review bbox",
        )
    if bbox is not None and not _bbox_is_valid(bbox):
        _add_issue(issues, "error", filename, row_index, "bbox_norm must be normalized x1< x2")

    for key in ("baseline_image", "current_image"):
        value = row.get(key)
        if not isinstance(value, str) or not value:
            _add_issue(issues, "error", filename, row_index, f"{key} must be a path string")
            continue
        path = source_root / value
        if not path.exists():
            _add_issue(issues, "error", filename, row_index, f"missing image: {value}")
        elif not _looks_like_image(path):
            _add_issue(issues, "error", filename, row_index, f"invalid image header: {value}")

    source_event = str(row.get("source_event") or "").strip()
    if not source_event:
        _add_issue(issues, "error", filename, row_index, "source_event must be non-empty")
    else:
        split_events[split].add(source_event.lower())

    country = str(row.get("country") or "unknown")
    modality = str(row.get("modality") or "unknown")
    country_counts[split][country] += 1
    if modality not in VALID_MODALITIES:
        _add_issue(issues, "error", filename, row_index, f"invalid modality: {modality}")
    else:
        modality_counts[split][modality] += 1

    for key in ("source_dataset", "provenance", "location_name", "country", "conflict_context"):
        if not isinstance(row.get(key), str) or not row.get(key):
            _add_issue(issues, "error", filename, row_index, f"{key} must be non-empty")

    baseline_date = row.get("baseline_date")
    current_date = row.get("current_date")
    if baseline_date is not None and not _date_is_valid(baseline_date):
        _add_issue(issues, "error", filename, row_index, "baseline_date must be YYYY-MM-DD or null")
    if current_date is not None and not _date_is_valid(current_date):
        _add_issue(issues, "error", filename, row_index, "current_date must be YYYY-MM-DD or null")
    if (
        isinstance(baseline_date, str)
        and isinstance(current_date, str)
        and _date_is_valid(baseline_date)
        and _date_is_valid(current_date)
        and baseline_date > current_date
    ):
        _add_issue(
            issues, "error", filename, row_index, "baseline_date must not exceed current_date"
        )


def _validate_sft_rows(
    *,
    split: str,
    rows: list[dict[str, Any]],
    flat_rows: list[dict[str, Any]],
    filename: str,
    issues: list[dict[str, object]],
) -> None:
    flat_by_id = {str(row.get("example_id")): row for row in flat_rows}
    if len(rows) != len(flat_rows):
        _add_issue(
            issues,
            "error",
            filename,
            None,
            f"SFT row count {len(rows)} does not match {split}_flat count {len(flat_rows)}",
        )
    for row_index, row in enumerate(rows, start=1):
        example_id = row.get("example_id")
        if not isinstance(example_id, str) or example_id not in flat_by_id:
            _add_issue(
                issues, "error", filename, row_index, "SFT example_id missing from flat rows"
            )
            continue
        flat = flat_by_id[example_id]
        if row.get("images") != [flat.get("baseline_image"), flat.get("current_image")]:
            _add_issue(issues, "error", filename, row_index, "SFT images must match flat row order")
        messages = row.get("messages")
        if not isinstance(messages, list) or len(messages) < 3:
            _add_issue(
                issues, "error", filename, row_index, "SFT messages must contain 3+ messages"
            )
            continue
        assistant = messages[-1]
        if not isinstance(assistant, dict) or assistant.get("role") != "assistant":
            _add_issue(issues, "error", filename, row_index, "last SFT message must be assistant")
            continue
        try:
            assistant_payload = json.loads(str(assistant.get("content") or ""))
        except json.JSONDecodeError:
            _add_issue(issues, "error", filename, row_index, "assistant content must parse as JSON")
            continue
        expected = flat.get("target_output")
        if assistant_payload != expected:
            _add_issue(
                issues, "error", filename, row_index, "assistant JSON must equal target_output"
            )


def _build_record(*, source_root: Path, row: dict[str, Any]) -> Any:
    target = row["target_output"]
    action: Action = target["action"]
    category = str(target["category"])
    bbox = _bbox_for_target(target)
    expected_candidate = AlertCandidate(
        event_type=_event_type_for_category(category=category, action=action),
        severity=_severity_for_action(action),
        confidence=_confidence_for_action(action),
        bbox=bbox,
        civilian_impact=_civilian_impact_for_category(category=category, action=action),
        why=str(target["rationale"]),
        action=action,
    )
    example_id = str(row["example_id"])
    source_event = str(row.get("source_event") or "unknown_event")
    country = str(row.get("country") or "unknown_country")
    location_name = str(row.get("location_name") or source_event)
    baseline_date = _as_timestamp(row.get("baseline_date"), fallback="2020-01-01T00:00:00Z")
    current_date = _as_timestamp(row.get("current_date"), fallback="2020-01-02T00:00:00Z")
    asset = Asset(
        asset_id=f"conflict_aux_{slugify(example_id)}",
        asset_name=f"{location_name} conflict disruption",
        asset_type=_asset_type_for_category(category),
        region=f"{location_name}, {country}",
        latitude=float(row.get("latitude") or 0.0),
        longitude=float(row.get("longitude") or 0.0),
        hero=False,
    )
    return build_candidate_eval_record(
        benchmark_source=str(row.get("source_dataset") or "conflict_aux_v1_3"),
        benchmark_case_id=example_id,
        case_id=slugify(example_id),
        split="train",
        asset=asset,
        current_image_path=str(source_root / str(row["current_image"])),
        baseline_image_path=str(source_root / str(row["baseline_image"])),
        current_captured_at=current_date,
        baseline_captured_at=baseline_date,
        current_frame_id=f"cur_{slugify(example_id)}",
        baseline_frame_id=f"base_{slugify(example_id)}",
        expected_candidate=expected_candidate,
        annotation_source="public_conflict_aux_v1_3",
        current_source=str(row.get("provenance") or row.get("source_dataset") or "public_aux"),
        baseline_source=str(row.get("provenance") or row.get("source_dataset") or "public_aux"),
        model_version="satellite-disruption-triage-aux-v1.3",
    )


def _event_type_for_category(*, category: str, action: str) -> str:
    if action == "discard":
        return "no_event"
    if category == "conflict_bridge_or_access_damage":
        return "probable_access_obstruction"
    if action == "defer" or category == "ambiguous_or_low_visibility":
        return "probable_surface_change"
    return "probable_large_scale_disruption"


def _severity_for_action(action: str) -> str:
    if action == "discard":
        return "low"
    if action == "defer":
        return "medium"
    return "high"


def _confidence_for_action(action: str) -> float:
    if action == "discard":
        return 0.76
    if action == "defer":
        return 0.64
    return 0.88


def _bbox_for_target(target: dict[str, Any]) -> tuple[float, float, float, float]:
    bbox = target.get("bbox_norm")
    if bbox is not None:
        return tuple(float(component) for component in bbox)
    if target.get("action") == "discard":
        return NO_EVENT_BBOX
    return AMBIGUOUS_REVIEW_BBOX


def _civilian_impact_for_category(*, category: str, action: str) -> str:
    if category == "no_visible_disruption" or action == "discard":
        return "no_material_impact"
    if category == "ambiguous_or_low_visibility":
        return "civilian_facility_disruption"
    if category == "conflict_water_infrastructure_damage":
        return "water_service_disruption"
    if category == "conflict_bridge_or_access_damage":
        return "public_mobility_disruption"
    if category == "conflict_food_logistics_damage":
        return "trade_disruption"
    if category == "conflict_port_or_silo_damage":
        return "shipping_or_aid_disruption"
    return "civilian_facility_disruption"


def _asset_type_for_category(category: str) -> AssetType:
    if category == "conflict_hospital_damage":
        return "medical_aid_node"
    if category == "conflict_food_logistics_damage":
        return "logistics_hub"
    if category == "conflict_water_infrastructure_damage":
        return "water_infrastructure"
    if category == "conflict_bridge_or_access_damage":
        return "bridge"
    if category == "conflict_port_or_silo_damage":
        return "grain_port"
    return "civilian_building_cluster"


def _load_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _add_issue(
    issues: list[dict[str, object]],
    severity: str,
    file: str,
    row: int | None,
    message: str,
) -> None:
    issues.append({"severity": severity, "file": file, "row": row, "message": message})


def _bbox_is_valid(value: object) -> bool:
    if not isinstance(value, list | tuple) or len(value) != 4:
        return False
    if not all(isinstance(component, int | float) for component in value):
        return False
    x1, y1, x2, y2 = (float(component) for component in value)
    return all(0.0 <= component <= 1.0 for component in (x1, y1, x2, y2)) and x1 < x2 and y1 < y2


def _looks_like_image(path: Path) -> bool:
    header = path.read_bytes()[:12]
    return (
        header.startswith(b"\x89PNG\r\n\x1a\n")
        or header.startswith(b"\xff\xd8\xff")
        or header.startswith(b"RIFF")
        and header[8:12] == b"WEBP"
    )


def _date_is_valid(value: object) -> bool:
    return isinstance(value, str) and DATE_PATTERN.match(value) is not None


def _as_timestamp(value: object, *, fallback: str) -> str:
    if isinstance(value, str) and _date_is_valid(value):
        return f"{value}T00:00:00Z"
    return fallback


def _nested_counter_dict(counters: dict[str, Counter[str]]) -> dict[str, dict[str, int]]:
    return {split: dict(sorted(counter.items())) for split, counter in counters.items()}


if __name__ == "__main__":
    raise SystemExit(main())
