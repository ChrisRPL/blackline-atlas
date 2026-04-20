from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts.external_benchmark_normalizer import (  # noqa: E402
    write_external_candidate_eval_slice,
)
from training.scripts.normalize_spacenet8_slice import build_spacenet8_slice  # noqa: E402
from training.scripts.normalize_xbd_slice import build_xbd_slice  # noqa: E402


def test_build_xbd_slice_normalizes_damage_classes(tmp_path: Path) -> None:
    _write_image(tmp_path / "images/xbd/base.png")
    _write_image(tmp_path / "images/xbd/current.png")
    seed_path = tmp_path / "xbd_seed.jsonl"
    seed_path.write_text(
        json.dumps(
            {
                "case_id": "haiti_cluster_destroyed",
                "source_case_id": "hurricane_matthew_0001",
                "split": "holdout_geo",
                "asset_name": "Haiti Civilian Building Cluster",
                "region": "Les Cayes, Haiti",
                "latitude": 18.2,
                "longitude": -73.75,
                "baseline_image_path": "images/xbd/base.png",
                "current_image_path": "images/xbd/current.png",
                "baseline_captured_at": "2016-10-01T10:00:00Z",
                "current_captured_at": "2016-10-08T10:00:00Z",
                "bbox": [0.12, 0.18, 0.88, 0.84],
                "damage_class": "destroyed",
                "disaster_type": "hurricane",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    records = build_xbd_slice(seed_dataset_path=seed_path)
    dataset_path = write_external_candidate_eval_slice(records=records, output_dir=tmp_path / "out")
    row = _read_jsonl(dataset_path)[0]

    assert row["benchmark_source"] == "xBD"
    assert row["asset"]["asset_type"] == "civilian_building_cluster"
    assert row["expected_candidate"]["civilian_impact"] == "civilian_facility_disruption"
    assert row["expected_candidate"]["event_type"] == "probable_large_scale_disruption"
    assert row["expected_action"] == "downlink_now"
    assert (dataset_path.parent / row["current_image_path"]).exists()


def test_build_spacenet8_slice_normalizes_flooded_road_segment(tmp_path: Path) -> None:
    _write_image(tmp_path / "images/sn8/base.png")
    _write_image(tmp_path / "images/sn8/current.png")
    seed_path = tmp_path / "spacenet8_seed.jsonl"
    seed_path.write_text(
        json.dumps(
            {
                "case_id": "sn8_road_flooded",
                "source_case_id": "sn8_tile_0004",
                "split": "holdout_geo",
                "asset_name": "Louisiana Flooded Road Segment",
                "region": "Louisiana",
                "latitude": 29.9,
                "longitude": -90.1,
                "baseline_image_path": "images/sn8/base.png",
                "current_image_path": "images/sn8/current.png",
                "baseline_captured_at": "2020-08-20T10:00:00Z",
                "current_captured_at": "2020-09-02T10:00:00Z",
                "bbox": [0.05, 0.24, 0.95, 0.54],
                "asset_kind": "road_segment",
                "flooded": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    records = build_spacenet8_slice(seed_dataset_path=seed_path)
    dataset_path = write_external_candidate_eval_slice(records=records, output_dir=tmp_path / "out")
    row = _read_jsonl(dataset_path)[0]

    assert row["benchmark_source"] == "SpaceNet8"
    assert row["asset"]["asset_type"] == "road_access_corridor"
    assert row["expected_candidate"]["civilian_impact"] == "public_mobility_disruption"
    assert row["expected_candidate"]["event_type"] == "probable_access_obstruction"
    assert row["expected_action"] == "downlink_now"
    assert row["prompt"]["system"].startswith("You are Blackline Atlas candidate generation.")


def _write_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"png")


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
