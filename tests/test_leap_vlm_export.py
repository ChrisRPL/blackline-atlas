from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts import export_leap_vlm_sft  # noqa: E402


def test_write_leap_vlm_sft_records_splits_train_and_eval(tmp_path: Path) -> None:
    dataset_path = _write_candidate_eval_fixture(tmp_path / "candidate_eval.jsonl")

    train_path, eval_path, summary_path = export_leap_vlm_sft.write_leap_vlm_sft_records(
        candidate_eval_path=dataset_path,
        output_dir=tmp_path / "leap",
    )

    train_rows = _read_jsonl(train_path)
    eval_rows = _read_jsonl(eval_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert len(train_rows) == 1
    assert len(eval_rows) == 1
    assert train_rows[0]["target_split"] == "train"
    assert eval_rows[0]["target_split"] == "eval"
    assert train_rows[0]["messages"][0]["role"] == "system"
    assert train_rows[0]["messages"][0]["content"] == [
        {"type": "text", "text": "You are Blackline Atlas candidate generation."}
    ]
    assert (
        train_rows[0]["messages"][1]["content"][0]["text"]
        == "Compare current frame against baseline."
    )
    assert train_rows[0]["messages"][1]["content"][1]["image"] == "images/current.png"
    assert train_rows[0]["messages"][1]["content"][2]["image"] == "images/base.png"
    assert train_rows[0]["messages"][2]["content"] == [
        {
            "type": "text",
            "text": (
                '{"event_type":"probable_access_obstruction","severity":"high",'
                '"confidence":0.95,"bbox":[0.1,0.2,0.8,0.9],'
                '"civilian_impact":"public_mobility_disruption",'
                '"why":"Bridge span is broken.","action":"downlink_now"}'
            ),
        }
    ]
    assert summary["image_root"] == str(dataset_path.parent.resolve())
    assert summary["train_records"] == 1
    assert summary["eval_records"] == 1
    assert summary["source_split_counts"] == {
        "train": 1,
        "dev": 0,
        "holdout_geo": 1,
        "holdout_stress": 0,
    }


def _write_candidate_eval_fixture(path: Path) -> Path:
    image_dir = path.parent / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    (image_dir / "base.png").write_bytes(b"base")
    (image_dir / "current.png").write_bytes(b"current")

    rows = [
        _candidate_row(
            case_id="train_case",
            split="train",
            current_image_path="images/current.png",
            baseline_image_path="images/base.png",
        ),
        _candidate_row(
            case_id="holdout_case",
            split="holdout_geo",
            current_image_path="images/current.png",
            baseline_image_path="images/base.png",
        ),
    ]
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _candidate_row(
    *,
    case_id: str,
    split: str,
    current_image_path: str,
    baseline_image_path: str,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "split": split,
        "asset": {
            "asset_id": "asset_01",
            "asset_name": "Asset",
            "asset_type": "bridge",
            "region": "Test Region",
            "latitude": 1.0,
            "longitude": 2.0,
            "hero": False,
        },
        "current_image_path": current_image_path,
        "baseline_image_path": baseline_image_path,
        "prompt": {
            "system": "You are Blackline Atlas candidate generation.",
            "user": "Compare current frame against baseline.",
        },
        "model_output_text": (
            '{"event_type":"probable_access_obstruction","severity":"high",'
            '"confidence":0.95,"bbox":[0.1,0.2,0.8,0.9],'
            '"civilian_impact":"public_mobility_disruption",'
            '"why":"Bridge span is broken.","action":"downlink_now"}'
        ),
        "expected_candidate": {
            "event_type": "probable_access_obstruction",
            "severity": "high",
            "confidence": 0.95,
            "bbox": [0.1, 0.2, 0.8, 0.9],
            "civilian_impact": "public_mobility_disruption",
            "why": "Bridge span is broken.",
            "action": "downlink_now",
        },
        "expected_action": "downlink_now",
        "expected_alert": {
            "alert_id": "blk_test_00001",
            "timestamp": "2026-01-01T00:00:00Z",
            "asset_id": "asset_01",
            "asset_name": "Asset",
            "asset_type": "bridge",
            "event_type": "probable_access_obstruction",
            "severity": "high",
            "confidence": 0.95,
            "bbox": [0.1, 0.2, 0.8, 0.9],
            "civilian_impact": "public_mobility_disruption",
            "why": "Bridge span is broken.",
            "action": "downlink_now",
            "source": {
                "current_frame_id": "cur_asset_01",
                "baseline_frame_id": "base_asset_01",
                "model_version": "lfm2.5-vl-450m-prompted",
            },
            "mapbox_context_ref": None,
        },
        "expected_metrics": {
            "frames_scanned": 10,
            "alerts_emitted": 1,
            "raw_frames_suppressed": 9,
            "downlink_rate": 0.1,
        },
        "simsat": {
            "current": {
                "requested_timestamp": "2026-01-01T00:00:00Z",
                "request_url": "https://example.test/current",
                "image_available": True,
                "datetime": "2026-01-01T00:00:00Z",
                "cloud_cover": 0.0,
                "footprint": [],
                "spectral_bands": ["red", "green", "blue"],
                "size_km": 1.0,
                "window_seconds": 864000.0,
            },
            "baseline": {
                "requested_timestamp": "2025-12-01T00:00:00Z",
                "request_url": "https://example.test/baseline",
                "image_available": True,
                "datetime": "2025-12-01T00:00:00Z",
                "cloud_cover": 0.0,
                "footprint": [],
                "spectral_bands": ["red", "green", "blue"],
                "size_km": 1.0,
                "window_seconds": 864000.0,
            },
        },
    }


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
