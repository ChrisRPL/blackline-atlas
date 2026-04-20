from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts import materialize_internal_benchmark_slice, run_model_benchmark  # noqa: E402


class EchoGenerator:
    def generate(self, case) -> str:
        return case.model_output_text


def test_materialize_internal_benchmark_slice_from_capture_manifest(tmp_path: Path) -> None:
    annotated_dataset_path = _write_annotated_dataset(tmp_path / "non_demo_eval.jsonl")
    capture_manifest_path = _write_capture_manifest(
        tmp_path / "simsat_capture",
        annotated_dataset_path,
    )

    candidate_eval_path = materialize_internal_benchmark_slice.materialize_internal_benchmark_slice(
        annotated_dataset_path=annotated_dataset_path,
        output_dir=tmp_path / "prepared",
        capture_manifest_path=capture_manifest_path,
    )

    rows = _read_jsonl(candidate_eval_path)
    assert len(rows) == 1
    assert rows[0]["case_id"] == "baltimore_bridge_collapse"
    assert rows[0]["current_image_path"] == "images/baltimore_bridge_collapse/current.png"
    assert candidate_eval_path.parent.joinpath(rows[0]["current_image_path"]).exists()
    assert rows[0]["prompt"]["system"].startswith("You are Blackline Atlas candidate generation.")


def test_run_benchmark_materializes_internal_slice_with_capture_manifest_env(
    tmp_path: Path,
    monkeypatch,
) -> None:
    annotated_dataset_path = _write_annotated_dataset(tmp_path / "non_demo_eval.jsonl")
    capture_manifest_path = _write_capture_manifest(
        tmp_path / "simsat_capture",
        annotated_dataset_path,
    )
    manifest_path = _write_internal_manifest(tmp_path / "manifest.json", annotated_dataset_path)

    monkeypatch.setenv(
        "BLACKLINE_INTERNAL_BENCHMARK_CAPTURE_MANIFEST",
        str(capture_manifest_path),
    )
    monkeypatch.setattr(run_model_benchmark, "_build_generator", lambda model: EchoGenerator())

    results, skipped, scorecard_json, scorecard_md = run_model_benchmark.run_benchmark(
        manifest_path=manifest_path,
        output_dir=tmp_path / "out",
    )

    assert len(results) == 1
    assert skipped == []
    assert results[0].summary["metrics"]["pass_count"] == 1
    assert scorecard_json.exists()
    assert scorecard_md.exists()
    assert (
        tmp_path / "out" / "_prepared" / "internal_non_demo" / "blackline_candidate_eval.jsonl"
    ).exists()


def test_run_benchmark_skips_internal_slice_without_capture_source(
    tmp_path: Path,
    monkeypatch,
) -> None:
    annotated_dataset_path = _write_annotated_dataset(tmp_path / "non_demo_eval.jsonl")
    manifest_path = _write_internal_manifest(tmp_path / "manifest.json", annotated_dataset_path)

    monkeypatch.delenv("BLACKLINE_INTERNAL_BENCHMARK_CAPTURE_MANIFEST", raising=False)
    monkeypatch.delenv("BLACKLINE_INTERNAL_BENCHMARK_HISTORICAL_ENDPOINT", raising=False)
    monkeypatch.delenv("SIMSAT_BASELINE_ENDPOINT", raising=False)

    results, skipped, _, _ = run_model_benchmark.run_benchmark(
        manifest_path=manifest_path,
        output_dir=tmp_path / "out",
    )

    assert results == []
    assert len(skipped) == 1
    assert "BLACKLINE_INTERNAL_BENCHMARK_CAPTURE_MANIFEST" in skipped[0].reason


def _write_internal_manifest(path: Path, dataset_path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "version": "2026-04-20",
                "default_output_dir": "training/eval_runs/model-benchmark",
                "models": [
                    {
                        "model_key": "liquid_local",
                        "title": "Liquid Local",
                        "model_id": "LiquidAI/LFM2.5-VL-450M",
                        "runner_kind": "transformers_local",
                        "enabled": True,
                    }
                ],
                "slices": [
                    {
                        "slice_id": "internal_non_demo",
                        "title": "Internal non-demo",
                        "tier": "internal",
                        "status": "ready",
                        "dataset_path": str(dataset_path),
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_annotated_dataset(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "case_id": "baltimore_bridge_collapse",
                "asset": {
                    "asset_id": "baltimore_bridge_01",
                    "asset_name": "Francis Scott Key Bridge",
                    "asset_type": "bridge",
                    "region": "Baltimore Harbor",
                    "latitude": 39.218,
                    "longitude": -76.531,
                    "hero": False,
                },
                "hero": False,
                "current_frame": {
                    "frame": {
                        "frame_id": "cur_baltimore_bridge_01_20240415",
                        "asset_id": "baltimore_bridge_01",
                        "captured_at": "2024-04-15T15:00:00Z",
                        "image_ref": "pending://baltimore/current.png",
                        "cloud_cover": 4.72,
                        "source": "seed",
                    },
                    "baseline_frame_id": "base_baltimore_bridge_01_20240326",
                },
                "baseline_frame": {
                    "frame": {
                        "frame_id": "base_baltimore_bridge_01_20240326",
                        "asset_id": "baltimore_bridge_01",
                        "captured_at": "2024-03-26T15:00:00Z",
                        "image_ref": "pending://baltimore/baseline.png",
                        "cloud_cover": 0.02,
                        "source": "seed",
                    }
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
                "expected_action": "downlink_now",
                "expected_metrics": {
                    "frames_scanned": 61,
                    "alerts_emitted": 1,
                    "raw_frames_suppressed": 57,
                    "downlink_rate": 0.028,
                },
                "split": "dev",
                "annotation_source": "manual_public_satellite_event",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_capture_manifest(capture_root: Path, annotated_dataset_path: Path) -> Path:
    case = _read_jsonl(annotated_dataset_path)[0]
    case_dir = capture_root / case["case_id"]
    case_dir.mkdir(parents=True, exist_ok=True)
    current_image = case_dir / "current.png"
    baseline_image = case_dir / "baseline.png"
    current_image.write_bytes(b"current")
    baseline_image.write_bytes(b"baseline")
    current_metadata = case_dir / "current-metadata.json"
    baseline_metadata = case_dir / "baseline-metadata.json"
    current_metadata.write_text("{}", encoding="utf-8")
    baseline_metadata.write_text("{}", encoding="utf-8")

    manifest_path = capture_root / "simsat_capture_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "pack_version": "simsat-capture-v1",
                "case_count": 1,
                "cases": [
                    {
                        "case_id": case["case_id"],
                        "pack_version": "simsat-capture-v1",
                        "asset": case["asset"],
                        "current": {
                            "frame_id": case["current_frame"]["frame"]["frame_id"],
                            "requested_timestamp": case["current_frame"]["frame"]["captured_at"],
                            "request_url": "https://example.test/current.png?window_seconds=864000",
                            "image_path": str(current_image.resolve()),
                            "metadata_path": str(current_metadata.resolve()),
                            "response_metadata": {
                                "image_available": True,
                                "source": "sentinel",
                                "spectral_bands": ["red", "green", "blue"],
                                "footprint": [1.0, 2.0, 3.0, 4.0],
                                "size_km": 5.0,
                                "cloud_cover": 0.05,
                                "datetime": case["current_frame"]["frame"]["captured_at"],
                                "satellite_position": [0.0, 0.0, 0.0],
                                "timestamp": case["current_frame"]["frame"]["captured_at"],
                            },
                        },
                        "baseline": {
                            "frame_id": case["baseline_frame"]["frame"]["frame_id"],
                            "requested_timestamp": case["baseline_frame"]["frame"]["captured_at"],
                            "request_url": "https://example.test/baseline.png?window_seconds=864000",
                            "image_path": str(baseline_image.resolve()),
                            "metadata_path": str(baseline_metadata.resolve()),
                            "response_metadata": {
                                "image_available": True,
                                "source": "sentinel",
                                "spectral_bands": ["red", "green", "blue"],
                                "footprint": [1.0, 2.0, 3.0, 4.0],
                                "size_km": 5.0,
                                "cloud_cover": 0.03,
                                "datetime": case["baseline_frame"]["frame"]["captured_at"],
                                "satellite_position": [0.0, 0.0, 0.0],
                                "timestamp": case["baseline_frame"]["frame"]["captured_at"],
                            },
                        },
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
