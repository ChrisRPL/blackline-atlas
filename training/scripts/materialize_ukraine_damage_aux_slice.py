from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from huggingface_hub import hf_hub_download
from PIL import Image

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

DEFAULT_REPO_ID = "KOlegaBB/damage_assessment_ukraine"
DEFAULT_OUTPUT_DIR = (
    ROOT / "training" / "eval_runs" / "aux-train-inputs" / "ukraine_damage_public_v0"
)
DEFAULT_SUMMARY_NAME = "summary.json"
DAMAGE_ORDER = ("no-damage", "minor-damage", "major-damage", "destroyed")

LOCATION_METADATA: dict[str, dict[str, object]] = {
    "kamianka_data": {
        "label": "Kamianka",
        "region": "Kamianka, Kharkiv Oblast, Ukraine",
        "latitude": 49.1217429,
        "longitude": 37.2976150,
        "baseline_captured_at": "2020-07-09T00:00:00Z",
        "current_captured_at": "2022-08-29T00:00:00Z",
    },
    "popasna_data": {
        "label": "Popasna",
        "region": "Popasna, Luhansk Oblast, Ukraine",
        "latitude": 48.6322687,
        "longitude": 38.3777033,
        "baseline_captured_at": "2020-10-15T00:00:00Z",
        "current_captured_at": "2023-07-04T00:00:00Z",
    },
    "yakovlivka_data": {
        "label": "Yakovlivka",
        "region": "Yakovlivka, Donetsk Oblast, Ukraine",
        "latitude": 48.7065806,
        "longitude": 38.1486373,
        "baseline_captured_at": "2019-09-06T00:00:00Z",
        "current_captured_at": "2022-08-01T00:00:00Z",
    },
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize a deterministic auxiliary-train slice from the public "
            "KOlegaBB/damage_assessment_ukraine dataset."
        ),
    )
    parser.add_argument("--repo-id", default=DEFAULT_REPO_ID)
    parser.add_argument(
        "--location-root",
        action="append",
        dest="location_roots",
        default=None,
        help="Location root like kamianka_data. Repeat for multiple.",
    )
    parser.add_argument("--fold", type=int, default=0)
    parser.add_argument("--max-per-damage", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dataset_path, summary_path = materialize_ukraine_damage_aux_slice(
        repo_id=args.repo_id,
        output_dir=args.output_dir,
        location_roots=tuple(args.location_roots or tuple(LOCATION_METADATA)),
        fold=args.fold,
        max_per_damage=args.max_per_damage,
    )
    print(f"wrote {dataset_path}")
    print(f"wrote {summary_path}")
    return 0


def materialize_ukraine_damage_aux_slice(
    *,
    repo_id: str,
    output_dir: Path,
    location_roots: tuple[str, ...] = tuple(LOCATION_METADATA),
    fold: int = 0,
    max_per_damage: int = 1,
    summary_name: str = DEFAULT_SUMMARY_NAME,
) -> tuple[Path, Path]:
    records = []
    summary_rows: list[dict[str, object]] = []

    for location_root in location_roots:
        rows = _load_fold_rows(repo_id=repo_id, location_root=location_root, fold=fold)
        selected = _select_rows(rows=rows, max_per_damage=max_per_damage)
        summary_rows.append(
            {
                "location_root": location_root,
                "selected_count": len(selected),
                "selected_damages": dict(Counter(row["damage"] for row in selected)),
            }
        )
        for row in selected:
            records.append(
                _build_record(
                    repo_id=repo_id,
                    location_root=location_root,
                    fold=fold,
                    row=row,
                )
            )

    dataset_path = write_external_candidate_eval_slice(records=records, output_dir=output_dir)
    summary_path = output_dir / summary_name
    summary_path.write_text(
        json.dumps(
            {
                "version": "ukraine-damage-public-v0",
                "repo_id": repo_id,
                "fold": fold,
                "max_per_damage": max_per_damage,
                "row_count": len(records),
                "location_roots": list(location_roots),
                "locations": summary_rows,
                "notes": [
                    "Auxiliary-train only. Keep separate from core Blackline gold metrics.",
                    "Rows are selected deterministically from one public fold per location.",
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return dataset_path, summary_path


def _load_fold_rows(*, repo_id: str, location_root: str, fold: int) -> list[dict[str, str]]:
    csv_path = hf_hub_download(
        repo_id=repo_id,
        repo_type="dataset",
        filename=f"classification/{location_root}/fold_{fold}/fold_{fold}.csv",
    )
    with open(csv_path, "r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _select_rows(*, rows: list[dict[str, str]], max_per_damage: int) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    for damage in DAMAGE_ORDER:
        for row in rows:
            if row["damage"] != damage:
                continue
            if counts[damage] >= max_per_damage:
                break
            selected.append(row)
            counts[damage] += 1
    return selected


def _build_record(
    *,
    repo_id: str,
    location_root: str,
    fold: int,
    row: dict[str, str],
):
    metadata = LOCATION_METADATA[location_root]
    stem = Path(row["pre_image"]).stem
    pre_path = hf_hub_download(
        repo_id=repo_id,
        repo_type="dataset",
        filename=f"classification/{location_root}/fold_{fold}/pre/{row['pre_image']}",
    )
    post_path = hf_hub_download(
        repo_id=repo_id,
        repo_type="dataset",
        filename=f"classification/{location_root}/fold_{fold}/post/{row['post_image']}",
    )
    mask_path = hf_hub_download(
        repo_id=repo_id,
        repo_type="dataset",
        filename=f"classification/{location_root}/fold_{fold}/mask/{row['mask_image']}",
    )
    asset_id = f"ukraine_damage_{slugify(stem)}"
    damage = row["damage"]
    asset = Asset(
        asset_id=asset_id,
        asset_name=f"{metadata['label']} Building {stem}",
        asset_type="civilian_building_cluster",
        region=str(metadata["region"]),
        latitude=float(metadata["latitude"]),
        longitude=float(metadata["longitude"]),
        hero=False,
    )
    return build_candidate_eval_record(
        benchmark_source="UkraineDamageAssessment",
        benchmark_case_id=stem,
        case_id=f"{slugify(location_root)}_{slugify(stem)}",
        split="train",
        asset=asset,
        current_image_path=post_path,
        baseline_image_path=pre_path,
        current_captured_at=str(metadata["current_captured_at"]),
        baseline_captured_at=str(metadata["baseline_captured_at"]),
        current_frame_id=f"cur_{asset_id}",
        baseline_frame_id=f"base_{asset_id}",
        current_source="ukraine_damage_post_seed",
        baseline_source="ukraine_damage_pre_seed",
        expected_candidate=_candidate_for_damage(
            damage=damage, bbox=_bbox_from_mask(Path(mask_path))
        ),
        annotation_source=None,
    )


def _candidate_for_damage(
    *, damage: str, bbox: tuple[float, float, float, float]
) -> AlertCandidate:
    if damage == "no-damage":
        return AlertCandidate(
            event_type="no_event",
            severity="low",
            confidence=0.95,
            bbox=bbox,
            civilian_impact="no_material_impact",
            why=(
                "The building-scale crop remains materially stable versus baseline, "
                "with no defendable macro-visible damage."
            ),
            action="discard",
        )
    if damage == "minor-damage":
        return AlertCandidate(
            event_type="probable_surface_change",
            severity="low",
            confidence=0.72,
            bbox=bbox,
            civilian_impact="civilian_facility_disruption",
            why=(
                "Limited but visible building damage appears in the post-disaster crop "
                "versus baseline."
            ),
            action="defer",
        )
    if damage == "major-damage":
        return AlertCandidate(
            event_type="probable_large_scale_disruption",
            severity="high",
            confidence=0.88,
            bbox=bbox,
            civilian_impact="civilian_facility_disruption",
            why=("The building crop shows major visible structural damage versus baseline."),
            action="downlink_now",
        )
    if damage == "destroyed":
        return AlertCandidate(
            event_type="probable_large_scale_disruption",
            severity="high",
            confidence=0.94,
            bbox=bbox,
            civilian_impact="civilian_facility_disruption",
            why=(
                "The building crop is catastrophically damaged versus baseline, "
                "with broad structural loss."
            ),
            action="downlink_now",
        )
    raise ValueError(f"unsupported damage label: {damage}")


def _bbox_from_mask(mask_path: Path) -> tuple[float, float, float, float]:
    with Image.open(mask_path) as image:
        bbox = image.convert("L").getbbox()
        if bbox is None:
            raise ValueError(f"mask has no positive bbox: {mask_path}")
        width, height = image.size
    left, top, right, bottom = bbox
    return (
        round(left / width, 4),
        round(top / height, 4),
        round(right / width, 4),
        round(bottom / height, 4),
    )


if __name__ == "__main__":
    raise SystemExit(main())
