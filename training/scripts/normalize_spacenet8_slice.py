from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.alert import AlertCandidate  # noqa: E402
from app.schemas.asset import Asset  # noqa: E402
from training.scripts.external_benchmark_normalizer import (  # noqa: E402
    build_candidate_eval_record,
    slugify,
    write_external_candidate_eval_slice,
)

DEFAULT_OUTPUT_DIR = ROOT / "training" / "external_benchmarks" / "spacenet8"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize curated SpaceNet 8 seeds into Blackline " "candidate-eval slice format."
        ),
    )
    parser.add_argument("--seed-dataset", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    records = build_spacenet8_slice(seed_dataset_path=args.seed_dataset)
    dataset_path = write_external_candidate_eval_slice(records=records, output_dir=args.output_dir)
    print(f"wrote {dataset_path}")
    return 0


def build_spacenet8_slice(*, seed_dataset_path: Path) -> list:
    rows = [
        json.loads(line)
        for line in seed_dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    base_dir = seed_dataset_path.parent.resolve()
    return [_normalize_seed(row=row, base_dir=base_dir) for row in rows]


def _normalize_seed(*, row: dict[str, object], base_dir: Path):
    case_id = str(row["case_id"])
    asset_kind = str(row["asset_kind"])
    flooded = bool(row["flooded"])
    asset_id = f"sn8_{slugify(case_id)}"
    asset_type = (
        "road_access_corridor" if asset_kind == "road_segment" else "civilian_building_cluster"
    )
    asset = Asset(
        asset_id=asset_id,
        asset_name=str(row["asset_name"]),
        asset_type=asset_type,
        region=str(row["region"]),
        latitude=float(row["latitude"]),
        longitude=float(row["longitude"]),
        hero=False,
    )
    candidate = _normalize_candidate(
        asset_kind=asset_kind,
        flooded=flooded,
        bbox=tuple(row["bbox"]),
    )
    split = str(row.get("split", "holdout_geo"))
    return build_candidate_eval_record(
        benchmark_source="SpaceNet8",
        benchmark_case_id=str(row.get("source_case_id") or case_id),
        case_id=case_id,
        split=(
            split if split in {"train", "dev", "holdout_geo", "holdout_stress"} else "holdout_geo"
        ),
        asset=asset,
        current_image_path=str((base_dir / str(row["current_image_path"])).resolve()),
        baseline_image_path=str((base_dir / str(row["baseline_image_path"])).resolve()),
        current_captured_at=str(row["current_captured_at"]),
        baseline_captured_at=str(row["baseline_captured_at"]),
        current_frame_id=str(row.get("current_frame_id") or f"cur_{asset_id}"),
        baseline_frame_id=str(row.get("baseline_frame_id") or f"base_{asset_id}"),
        current_cloud_cover=_optional_float(row.get("current_cloud_cover")),
        baseline_cloud_cover=_optional_float(row.get("baseline_cloud_cover")),
        current_source="spacenet8_current_seed",
        baseline_source="spacenet8_baseline_seed",
        expected_candidate=candidate,
    )


def _normalize_candidate(
    *,
    asset_kind: str,
    flooded: bool,
    bbox: tuple[float, float, float, float],
) -> AlertCandidate:
    if not flooded:
        why = (
            "The corridor remains materially stable versus baseline, with no "
            "defendable flood obstruction."
            if asset_kind == "road_segment"
            else "The civilian building cluster remains materially stable versus "
            "baseline, with no defendable flood-driven disruption."
        )
        return AlertCandidate(
            event_type="no_event",
            severity="low",
            confidence=0.95,
            bbox=bbox,
            civilian_impact="no_material_impact",
            why=why,
            action="discard",
        )

    if asset_kind == "road_segment":
        return AlertCandidate(
            event_type="probable_access_obstruction",
            severity="high",
            confidence=0.9,
            bbox=bbox,
            civilian_impact="public_mobility_disruption",
            why=(
                "Flood water materially obstructs the road-access corridor versus "
                "the dry baseline."
            ),
            action="downlink_now",
        )

    if asset_kind == "building_cluster":
        return AlertCandidate(
            event_type="probable_surface_change",
            severity="high",
            confidence=0.87,
            bbox=bbox,
            civilian_impact="civilian_facility_disruption",
            why=(
                "Flood water visibly covers the civilian building cluster versus "
                "baseline, indicating a macro-scale facility disruption."
            ),
            action="downlink_now",
        )

    raise ValueError(f"unsupported SpaceNet8 asset_kind: {asset_kind}")


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


if __name__ == "__main__":
    raise SystemExit(main())
