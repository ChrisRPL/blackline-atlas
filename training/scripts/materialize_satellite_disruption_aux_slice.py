from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.alert import Action, AlertCandidate  # noqa: E402
from app.schemas.asset import Asset  # noqa: E402
from training.scripts.external_benchmark_normalizer import (  # noqa: E402
    build_candidate_eval_record,
    slugify,
    write_external_candidate_eval_slice,
)

DEFAULT_SOURCE_ROOT = Path(
    "/Users/krzysztof/satellite-disruption-triage-v1_1_extracted/output_v1_1"
)
DEFAULT_OUTPUT_DIR = (
    ROOT / "training" / "eval_runs" / "aux-train-inputs" / "satellite_disruption_aux_v1_1"
)
DEFAULT_SUMMARY_NAME = "summary.json"
NO_EVENT_BBOX = (0.01, 0.01, 0.02, 0.02)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize ml-intern's satellite-disruption-triage-v1.1 artifact into "
            "Blackline candidate-eval auxiliary train rows."
        )
    )
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--include-eval-split",
        action="store_true",
        help="Also include the artifact eval_flat.jsonl rows as train rows. Default: train only.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dataset_path, summary_path = materialize_satellite_disruption_aux_slice(
        source_root=args.source_root,
        output_dir=args.output_dir,
        include_eval_split=args.include_eval_split,
    )
    print(f"wrote {dataset_path}")
    print(f"wrote {summary_path}")
    return 0


def materialize_satellite_disruption_aux_slice(
    *,
    source_root: Path,
    output_dir: Path,
    include_eval_split: bool = False,
    summary_name: str = DEFAULT_SUMMARY_NAME,
) -> tuple[Path, Path]:
    flat_files = ["train_flat.jsonl"]
    if include_eval_split:
        flat_files.append("eval_flat.jsonl")

    records = []
    source_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    modality_counts: Counter[str] = Counter()
    event_counts: Counter[str] = Counter()

    for flat_file in flat_files:
        for row in _load_rows(source_root / flat_file):
            action = row["target_output"]["action"]
            records.append(_build_record(source_root=source_root, row=row))
            source_counts[row.get("source_dataset", "unknown")] += 1
            action_counts[action] += 1
            modality_counts[row.get("modality", "unknown")] += 1
            event_counts[row.get("source_event", "unknown")] += 1

    dataset_path = write_external_candidate_eval_slice(records=records, output_dir=output_dir)
    summary_path = output_dir / summary_name
    summary_path.write_text(
        json.dumps(
            {
                "version": "satellite-disruption-aux-v1.1-blackline-v1",
                "source_root": str(source_root),
                "row_count": len(records),
                "included_flat_files": flat_files,
                "split": "train",
                "action_counts": dict(sorted(action_counts.items())),
                "source_counts": dict(sorted(source_counts.items())),
                "modality_counts": dict(sorted(modality_counts.items())),
                "event_counts": dict(sorted(event_counts.items())),
                "notes": [
                    "Auxiliary-train only. Keep separate from core Blackline gold metrics.",
                    "Rows are algorithmically labeled public disaster-transfer examples.",
                    (
                        "Discard rows use a tiny schema-compatible no-event bbox because "
                        "Blackline AlertCandidate requires a positive bbox."
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


def _load_rows(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _build_record(*, source_root: Path, row: dict[str, object]):
    target = row["target_output"]
    action: Action = target["action"]
    bbox = tuple(target["bbox_norm"] or NO_EVENT_BBOX)
    expected_candidate = AlertCandidate(
        event_type=_event_type_for_action(action),
        severity=_severity_for_action(action),
        confidence=_confidence_for_action(action),
        bbox=bbox,
        civilian_impact=_civilian_impact_for_category(str(target["category"])),
        why=str(target["rationale"]),
        action=action,
    )
    example_id = str(row["example_id"])
    source_event = str(row.get("source_event") or "unknown_event")
    asset = Asset(
        asset_id=f"satdis_{slugify(example_id)}",
        asset_name=f"Satellite disruption aux: {source_event}",
        asset_type="civilian_building_cluster",
        region=source_event,
        latitude=0.0,
        longitude=0.0,
        hero=False,
    )
    return build_candidate_eval_record(
        benchmark_source=str(row.get("source_dataset") or "satellite_disruption_triage_v1_1"),
        benchmark_case_id=example_id,
        case_id=slugify(example_id),
        split="train",
        asset=asset,
        current_image_path=str(source_root / str(row["current_image"])),
        baseline_image_path=str(source_root / str(row["baseline_image"])),
        current_captured_at="2020-01-02T00:00:00Z",
        baseline_captured_at="2020-01-01T00:00:00Z",
        current_frame_id=f"cur_{slugify(example_id)}",
        baseline_frame_id=f"base_{slugify(example_id)}",
        expected_candidate=expected_candidate,
        annotation_source="public_aux_satellite_disruption_v1_1",
        current_source=str(row.get("provenance") or row.get("source_dataset") or "public_aux"),
        baseline_source=str(row.get("provenance") or row.get("source_dataset") or "public_aux"),
        model_version="satellite-disruption-triage-v1.1",
    )


def _event_type_for_action(action: Action):
    if action == "discard":
        return "no_event"
    if action == "defer":
        return "probable_surface_change"
    return "probable_large_scale_disruption"


def _severity_for_action(action: Action):
    if action == "discard":
        return "low"
    if action == "defer":
        return "medium"
    return "high"


def _confidence_for_action(action: Action) -> float:
    if action == "discard":
        return 0.74
    if action == "defer":
        return 0.62
    return 0.84


def _civilian_impact_for_category(category: str):
    if category == "no_disruption":
        return "no_material_impact"
    if "flood" in category or "storm" in category:
        return "logistics_delay"
    return "civilian_facility_disruption"


if __name__ == "__main__":
    raise SystemExit(main())
