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

DEFAULT_OUTPUT_DIR = ROOT / "training" / "external_benchmarks" / "xbd"


class XbdSliceSeed(dict):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize curated xBD seeds into Blackline candidate-eval slice format.",
    )
    parser.add_argument("--seed-dataset", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    records = build_xbd_slice(seed_dataset_path=args.seed_dataset)
    dataset_path = write_external_candidate_eval_slice(records=records, output_dir=args.output_dir)
    print(f"wrote {dataset_path}")
    return 0


def build_xbd_slice(*, seed_dataset_path: Path) -> list:
    rows = _load_seed_rows(seed_dataset_path)
    base_dir = seed_dataset_path.parent.resolve()
    return [_normalize_seed(row=row, base_dir=base_dir) for row in rows]


def _load_seed_rows(seed_dataset_path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in seed_dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _normalize_seed(*, row: dict[str, object], base_dir: Path):
    case_id = str(row["case_id"])
    damage_class = str(row["damage_class"])
    split = str(row.get("split", "holdout_geo"))
    asset_id = f"xbd_{slugify(case_id)}"
    asset = Asset(
        asset_id=asset_id,
        asset_name=str(row["asset_name"]),
        asset_type="civilian_building_cluster",
        region=str(row["region"]),
        latitude=float(row["latitude"]),
        longitude=float(row["longitude"]),
        hero=False,
    )
    candidate = _normalize_candidate(
        damage_class=damage_class,
        bbox=tuple(row["bbox"]),
        disaster_type=str(row.get("disaster_type") or "disaster"),
    )
    return build_candidate_eval_record(
        benchmark_source="xBD",
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
        current_source="xbd_current_seed",
        baseline_source="xbd_baseline_seed",
        expected_candidate=candidate,
    )


def _normalize_candidate(
    *,
    damage_class: str,
    bbox: tuple[float, float, float, float],
    disaster_type: str,
) -> AlertCandidate:
    if damage_class == "no_damage":
        return AlertCandidate(
            event_type="no_event",
            severity="low",
            confidence=0.96,
            bbox=bbox,
            civilian_impact="no_material_impact",
            why=(
                "The civilian building cluster remains materially stable versus baseline, "
                "with no defendable macro-scale disaster damage."
            ),
            action="discard",
        )
    if damage_class == "minor_damage":
        return AlertCandidate(
            event_type="probable_surface_change",
            severity="low",
            confidence=0.72,
            bbox=bbox,
            civilian_impact="civilian_facility_disruption",
            why=(
                f"Limited but visible {disaster_type} damage appears on the civilian "
                "building cluster versus baseline."
            ),
            action="defer",
        )
    if damage_class == "major_damage":
        return AlertCandidate(
            event_type="probable_large_scale_disruption",
            severity="high",
            confidence=0.88,
            bbox=bbox,
            civilian_impact="civilian_facility_disruption",
            why=(
                f"The civilian building cluster shows major {disaster_type} damage "
                "and visible structural loss versus baseline."
            ),
            action="downlink_now",
        )
    if damage_class == "destroyed":
        return AlertCandidate(
            event_type="probable_large_scale_disruption",
            severity="high",
            confidence=0.94,
            bbox=bbox,
            civilian_impact="civilian_facility_disruption",
            why=(
                "The civilian building cluster is catastrophically damaged versus "
                f"baseline, with broad structural loss after the {disaster_type}."
            ),
            action="downlink_now",
        )
    raise ValueError(f"unsupported xBD damage_class: {damage_class}")


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


if __name__ == "__main__":
    raise SystemExit(main())
