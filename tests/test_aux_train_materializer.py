from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts import materialize_aux_train_slice  # noqa: E402


def test_materialize_aux_train_slice_rewrites_split_and_image_refs(tmp_path: Path) -> None:
    source_root = tmp_path / "source_slice"
    images_dir = source_root / "images" / "demo_case"
    images_dir.mkdir(parents=True)
    (images_dir / "baseline.png").write_bytes(b"baseline")
    (images_dir / "current.png").write_bytes(b"current")

    dataset_path = source_root / "blackline_candidate_eval.jsonl"
    row = {
        "case_id": "demo_case",
        "split": "holdout_geo",
        "benchmark_source": "xBD",
        "benchmark_case_id": "xbd_demo_case",
        "asset": {
            "asset_id": "xbd_demo_case",
            "asset_name": "Demo Cluster",
            "asset_type": "civilian_building_cluster",
            "region": "Demo Region",
            "latitude": 1.0,
            "longitude": 2.0,
            "hero": False,
            "evidence_available": False,
            "evidence_state": None,
        },
        "current_image_path": "images/demo_case/current.png",
        "baseline_image_path": "images/demo_case/baseline.png",
        "prompt": {
            "system": "system prompt",
            "user": (
                "Current frame\n"
                "- image_ref: /tmp/old_current.png\n"
                "Baseline frame\n"
                "- image_ref: /tmp/old_baseline.png\n"
            ),
        },
        "model_output_text": '{"event_type":"no_event","severity":"low","confidence":0.9,'
        '"bbox":[0.0,0.0,1.0,1.0],"civilian_impact":"no_material_impact",'
        '"why":"No change.","action":"discard"}',
        "expected_candidate": {
            "event_type": "no_event",
            "severity": "low",
            "confidence": 0.9,
            "bbox": [0.0, 0.0, 1.0, 1.0],
            "civilian_impact": "no_material_impact",
            "why": "No change.",
            "action": "discard",
        },
        "expected_action": "discard",
        "expected_alert": {
            "alert_id": "ext_demo_case",
            "asset_id": "xbd_demo_case",
            "asset_name": "Demo Cluster",
            "asset_type": "civilian_building_cluster",
            "timestamp": "2020-01-01T00:00:00Z",
            "event_type": "no_event",
            "severity": "low",
            "confidence": 0.9,
            "bbox": [0.0, 0.0, 1.0, 1.0],
            "civilian_impact": "no_material_impact",
            "why": "No change.",
            "action": "discard",
            "source": {
                "current_frame_id": "cur_demo_case",
                "baseline_frame_id": "base_demo_case",
                "model_version": "external",
            },
            "mapbox_context_ref": None,
        },
        "expected_metrics": {
            "frames_scanned": 48,
            "alerts_emitted": 0,
            "downlink_rate": 0.0,
            "raw_frames_suppressed": 48,
        },
        "simsat": {
            "current": {
                "requested_timestamp": "2020-01-01T00:00:00Z",
                "request_url": "images/demo_case/current.png",
                "image_available": True,
                "datetime": "2020-01-01T00:00:00Z",
                "cloud_cover": None,
                "footprint": [],
                "spectral_bands": [],
                "size_km": None,
                "window_seconds": None,
            },
            "baseline": {
                "requested_timestamp": "2019-01-01T00:00:00Z",
                "request_url": "images/demo_case/baseline.png",
                "image_available": True,
                "datetime": "2019-01-01T00:00:00Z",
                "cloud_cover": None,
                "footprint": [],
                "spectral_bands": [],
                "size_km": None,
                "window_seconds": None,
            },
        },
    }
    dataset_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    output_dir = tmp_path / "aux_train"
    candidate_eval_path, summary_path = materialize_aux_train_slice.materialize_aux_train_slice(
        source_datasets=(dataset_path,),
        output_dir=output_dir,
    )

    rows = [
        json.loads(line)
        for line in candidate_eval_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["case_id"] == "source_slice__demo_case"
    assert rows[0]["split"] == "train"
    assert rows[0]["current_image_path"] == "images/source_slice__demo_case/current.png"
    assert rows[0]["baseline_image_path"] == "images/source_slice__demo_case/baseline.png"
    assert "- image_ref: images/source_slice__demo_case/current.png" in rows[0]["prompt"]["user"]
    assert "- image_ref: images/source_slice__demo_case/baseline.png" in rows[0]["prompt"]["user"]
    assert (
        output_dir / "images" / "source_slice__demo_case" / "current.png"
    ).read_bytes() == b"current"
    assert (
        output_dir / "images" / "source_slice__demo_case" / "baseline.png"
    ).read_bytes() == b"baseline"

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["row_count"] == 1
    assert summary["split"] == "train"
    assert summary["source_datasets"][0]["benchmark_sources"] == ["xBD"]


def test_materialize_aux_train_slice_real_public_seed_counts(tmp_path: Path) -> None:
    candidate_eval_path, summary_path = materialize_aux_train_slice.materialize_aux_train_slice(
        source_datasets=materialize_aux_train_slice.DEFAULT_SOURCE_DATASETS,
        output_dir=tmp_path / "aux_public_seed_v0",
    )

    rows = [
        json.loads(line)
        for line in candidate_eval_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 8
    assert all(row["split"] == "train" for row in rows)
    assert {row["benchmark_source"] for row in rows} == {"SpaceNet8", "xBD"}
    for row in rows:
        assert (candidate_eval_path.parent / row["current_image_path"]).exists()
        assert (candidate_eval_path.parent / row["baseline_image_path"]).exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["row_count"] == 8
    assert summary["source_dataset_count"] == 2
