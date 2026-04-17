from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts import run_lfm25_vl_prompted_eval  # noqa: E402


class _FakeGenerator:
    def generate(self, case) -> str:
        _ = case
        return (
            '{"event_type":"probable_access_obstruction","severity":"high",'
            '"confidence":0.95,"bbox":[0.31,0.28,0.72,0.66],'
            '"civilian_impact":"public_mobility_disruption",'
            '"why":"Bridge span is broken.","action":"downlink_now"}'
        )


def test_run_prompted_eval_writes_predictions_and_summary(tmp_path: Path) -> None:
    image_root = tmp_path / "images" / "baltimore_bridge_collapse"
    image_root.mkdir(parents=True)
    (image_root / "current.png").write_bytes(b"png")
    (image_root / "baseline.png").write_bytes(b"png")

    dataset_path = tmp_path / "blackline_candidate_eval.jsonl"
    dataset_path.write_text(
        json.dumps(
            {
                "case_id": "baltimore_bridge_collapse",
                "split": "dev",
                "asset": {
                    "asset_id": "baltimore_bridge_01",
                    "asset_name": "Francis Scott Key Bridge",
                    "asset_type": "bridge",
                    "region": "Baltimore Harbor",
                    "latitude": 39.218,
                    "longitude": -76.531,
                    "hero": False,
                },
                "current_image_path": "images/baltimore_bridge_collapse/current.png",
                "baseline_image_path": "images/baltimore_bridge_collapse/baseline.png",
                "prompt": {
                    "system": "You are Blackline Atlas candidate generation.",
                    "user": "Compare current and baseline.",
                },
                "model_output_text": (
                    '{"event_type":"probable_access_obstruction","severity":"high",'
                    '"confidence":0.95,"bbox":[0.31,0.28,0.72,0.66],'
                    '"civilian_impact":"public_mobility_disruption",'
                    '"why":"Bridge span is broken.","action":"downlink_now"}'
                ),
                "expected_candidate": {
                    "event_type": "probable_access_obstruction",
                    "severity": "high",
                    "confidence": 0.95,
                    "bbox": [0.31, 0.28, 0.72, 0.66],
                    "civilian_impact": "public_mobility_disruption",
                    "why": "Bridge span is broken.",
                    "action": "downlink_now",
                },
                "expected_action": "downlink_now",
                "expected_alert": {
                    "alert_id": "blk_nd_00002",
                    "timestamp": "2024-04-15T15:00:00Z",
                    "asset_id": "baltimore_bridge_01",
                    "asset_name": "Francis Scott Key Bridge",
                    "asset_type": "bridge",
                    "event_type": "probable_access_obstruction",
                    "severity": "high",
                    "confidence": 0.95,
                    "bbox": [0.31, 0.28, 0.72, 0.66],
                    "civilian_impact": "public_mobility_disruption",
                    "why": "Bridge span is broken.",
                    "action": "downlink_now",
                    "source": {
                        "current_frame_id": "cur_baltimore_bridge_01_20240415",
                        "baseline_frame_id": "base_baltimore_bridge_01_20240326",
                        "model_version": "lfm2.5-vl-450m-prompted",
                    },
                    "mapbox_context_ref": None,
                },
                "expected_metrics": {
                    "frames_scanned": 61,
                    "alerts_emitted": 1,
                    "raw_frames_suppressed": 57,
                    "downlink_rate": 0.028,
                },
                "simsat": {
                    "current": {
                        "requested_timestamp": "2024-04-15T15:00:00Z",
                        "request_url": "https://example.test/current",
                        "image_available": True,
                        "datetime": "2024-04-14T16:02:24Z",
                        "cloud_cover": 4.72,
                        "footprint": [],
                        "spectral_bands": ["red", "green", "blue"],
                        "size_km": 5.0,
                        "window_seconds": 864000.0,
                    },
                    "baseline": {
                        "requested_timestamp": "2024-03-26T15:00:00Z",
                        "request_url": "https://example.test/baseline",
                        "image_available": True,
                        "datetime": "2024-03-25T16:02:24Z",
                        "cloud_cover": 0.02,
                        "footprint": [],
                        "spectral_bands": ["red", "green", "blue"],
                        "size_km": 5.0,
                        "window_seconds": 864000.0,
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    predictions_path, summary_path, summary = run_lfm25_vl_prompted_eval.run_prompted_eval(
        dataset_path=dataset_path,
        output_dir=tmp_path / "out",
        generator=_FakeGenerator(),
    )

    assert predictions_path.exists()
    assert summary_path.exists()
    assert summary["passed"] is True
    prediction = json.loads(predictions_path.read_text(encoding="utf-8").strip())
    assert prediction["case_id"] == "baltimore_bridge_collapse"


def test_load_candidate_eval_cases_resolves_paths_against_dataset_root(tmp_path: Path) -> None:
    image_root = tmp_path / "images" / "hero_port_disruption"
    image_root.mkdir(parents=True)
    (image_root / "current.png").write_bytes(b"png")
    (image_root / "baseline.png").write_bytes(b"png")

    dataset_path = tmp_path / "blackline_candidate_eval.jsonl"
    dataset_path.write_text(
        json.dumps(
            {
                "case_id": "hero_port_disruption",
                "split": "holdout_geo",
                "asset": {
                    "asset_id": "demo_port_01",
                    "asset_name": "Demo Grain Port",
                    "asset_type": "grain_port",
                    "region": "Black Sea",
                    "latitude": 46.501,
                    "longitude": 30.747,
                    "hero": True,
                },
                "current_image_path": "images/hero_port_disruption/current.png",
                "baseline_image_path": "images/hero_port_disruption/baseline.png",
                "prompt": {"system": "sys", "user": "usr"},
                "model_output_text": (
                    '{"event_type":"probable_large_scale_disruption","severity":"high",'
                    '"confidence":0.89,"bbox":[0.19,0.26,0.73,0.84],'
                    '"civilian_impact":"shipping_or_aid_disruption",'
                    '"why":"Port disrupted.","action":"downlink_now"}'
                ),
                "expected_candidate": {
                    "event_type": "probable_large_scale_disruption",
                    "severity": "high",
                    "confidence": 0.89,
                    "bbox": [0.19, 0.26, 0.73, 0.84],
                    "civilian_impact": "shipping_or_aid_disruption",
                    "why": "Port disrupted.",
                    "action": "downlink_now",
                },
                "expected_action": "downlink_now",
                "expected_alert": {
                    "alert_id": "blk_00017",
                    "timestamp": "2026-04-14T18:40:00Z",
                    "asset_id": "demo_port_01",
                    "asset_name": "Demo Grain Port",
                    "asset_type": "grain_port",
                    "event_type": "probable_large_scale_disruption",
                    "severity": "high",
                    "confidence": 0.89,
                    "bbox": [0.19, 0.26, 0.73, 0.84],
                    "civilian_impact": "shipping_or_aid_disruption",
                    "why": "Port disrupted.",
                    "action": "downlink_now",
                    "source": {
                        "current_frame_id": "cur_demo_port_01_20260414",
                        "baseline_frame_id": "base_demo_port_01_20250901",
                        "model_version": "lfm2.5-vl-450m-prompted",
                    },
                    "mapbox_context_ref": None,
                },
                "expected_metrics": {
                    "frames_scanned": 143,
                    "alerts_emitted": 5,
                    "raw_frames_suppressed": 138,
                    "downlink_rate": 0.035,
                },
                "simsat": {
                    "current": {
                        "requested_timestamp": "2026-04-14T18:40:00Z",
                        "request_url": "https://example.test/current",
                        "image_available": True,
                        "datetime": "2026-04-13T08:57:26Z",
                        "cloud_cover": 25.78,
                        "footprint": [],
                        "spectral_bands": ["red", "green", "blue"],
                        "size_km": 5.0,
                        "window_seconds": 864000.0,
                    },
                    "baseline": {
                        "requested_timestamp": "2025-09-01T10:00:00Z",
                        "request_url": "https://example.test/baseline",
                        "image_available": True,
                        "datetime": "2025-08-29T09:07:44Z",
                        "cloud_cover": 0.01,
                        "footprint": [],
                        "spectral_bands": ["red", "green", "blue"],
                        "size_km": 5.0,
                        "window_seconds": 864000.0,
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    case = run_lfm25_vl_prompted_eval.load_candidate_eval_cases(dataset_path)[0]
    assert case.current_image_path == str(
        (tmp_path / "images/hero_port_disruption/current.png").resolve()
    )
    assert case.baseline_image_path == str(
        (tmp_path / "images/hero_port_disruption/baseline.png").resolve()
    )
