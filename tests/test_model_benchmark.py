from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts import run_model_benchmark  # noqa: E402


def test_run_benchmark_skips_planned_and_missing_endpoint(tmp_path: Path, monkeypatch) -> None:
    dataset_path = tmp_path / "non_demo_eval.jsonl"
    image_dir = tmp_path / "images" / "internal"
    image_dir.mkdir(parents=True)
    (image_dir / "current.png").write_bytes(b"current")
    (image_dir / "baseline.png").write_bytes(b"baseline")
    dataset_path.write_text(
        json.dumps(
            {
                "case_id": "internal_case",
                "split": "holdout_geo",
                "asset": {
                    "asset_id": "internal_asset_01",
                    "asset_name": "Internal Asset",
                    "asset_type": "bridge",
                    "region": "Test Harbor",
                    "latitude": 1.0,
                    "longitude": 2.0,
                    "hero": False,
                },
                "current_image_path": "images/internal/current.png",
                "baseline_image_path": "images/internal/baseline.png",
                "prompt": {"system": "sys", "user": "user"},
                "model_output_text": (
                    '{"event_type":"no_event","severity":"low","confidence":0.9,'
                    '"bbox":[0.1,0.1,0.2,0.2],"civilian_impact":"no_material_impact",'
                    '"why":"No event.","action":"discard"}'
                ),
                "expected_candidate": {
                    "event_type": "no_event",
                    "severity": "low",
                    "confidence": 0.9,
                    "bbox": [0.1, 0.1, 0.2, 0.2],
                    "civilian_impact": "no_material_impact",
                    "why": "No event.",
                    "action": "discard",
                },
                "expected_action": "discard",
                "expected_alert": {
                    "alert_id": "blk_test_00001",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "asset_id": "internal_asset_01",
                    "asset_name": "Internal Asset",
                    "asset_type": "bridge",
                    "event_type": "no_event",
                    "severity": "low",
                    "confidence": 0.9,
                    "bbox": [0.1, 0.1, 0.2, 0.2],
                    "civilian_impact": "no_material_impact",
                    "why": "No event.",
                    "action": "discard",
                    "source": {
                        "current_frame_id": "cur_internal_asset_01",
                        "baseline_frame_id": "base_internal_asset_01",
                        "model_version": "lfm2.5-vl-450m-prompted",
                    },
                    "mapbox_context_ref": None,
                },
                "expected_metrics": {
                    "frames_scanned": 10,
                    "alerts_emitted": 0,
                    "raw_frames_suppressed": 10,
                    "downlink_rate": 0.0,
                },
                "simsat": {
                    "current": {
                        "requested_timestamp": "2026-01-01T00:00:00Z",
                        "request_url": "images/internal/current.png",
                        "image_available": True,
                        "datetime": "2026-01-01T00:00:00Z",
                        "cloud_cover": 0.0,
                        "footprint": [],
                        "spectral_bands": [],
                        "size_km": None,
                        "window_seconds": None,
                    },
                    "baseline": {
                        "requested_timestamp": "2025-12-01T00:00:00Z",
                        "request_url": "images/internal/baseline.png",
                        "image_available": True,
                        "datetime": "2025-12-01T00:00:00Z",
                        "cloud_cover": 0.0,
                        "footprint": [],
                        "spectral_bands": [],
                        "size_km": None,
                        "window_seconds": None,
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": "2026-04-20",
                "default_output_dir": "training/eval_runs/model-benchmark",
                "models": [
                    {
                        "model_key": "liquid_http",
                        "title": "Liquid HTTP",
                        "model_id": "LiquidAI/LFM2.5-VL-450M",
                        "runner_kind": "openai_chat_completions_http",
                        "enabled": True,
                        "provider_id": "openai_chat_completions_http",
                        "endpoint_env": "TEST_LIQUID_ENDPOINT",
                    }
                ],
                "slices": [
                    {
                        "slice_id": "internal",
                        "title": "Internal",
                        "tier": "internal",
                        "status": "ready",
                        "dataset_path": str(dataset_path),
                    },
                    {
                        "slice_id": "planned_external",
                        "title": "Planned external",
                        "tier": "external_task_fit",
                        "status": "planned",
                        "dataset_path": (
                            "training/external_benchmarks/" "xbd/blackline_candidate_eval.jsonl"
                        ),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv("TEST_LIQUID_ENDPOINT", raising=False)

    results, skipped, scorecard_json, scorecard_md = run_model_benchmark.run_benchmark(
        manifest_path=manifest_path,
        output_dir=tmp_path / "out",
    )

    assert results == []
    assert len(skipped) == 2
    assert any("missing endpoint env" in item.reason for item in skipped)
    assert any("slice status is planned" in item.reason for item in skipped)
    assert scorecard_json.exists()
    assert scorecard_md.exists()


def test_render_scorecard_markdown_includes_rates() -> None:
    result = run_model_benchmark.BenchmarkRunResult(
        model_key="liquid",
        model_title="Liquid",
        model_id="LiquidAI/LFM2.5-VL-450M",
        slice_id="internal",
        slice_title="Internal",
        tier="internal",
        predictions_path=Path("/tmp/predictions.jsonl"),
        summary_path=Path("/tmp/summary.json"),
        summary={
            "total_cases": 10,
            "metrics": {
                "false_positive_count": 1,
            },
            "rates": {
                "pass_rate": 0.6,
                "action_match_rate": 0.8,
                "schema_valid_rate": 0.9,
            },
            "predicted_action_counts": {
                "discard": 6,
                "defer": 2,
                "downlink_now": 2,
            },
        },
    )

    markdown = run_model_benchmark.render_scorecard_markdown(
        results=[result],
        skipped=[
            run_model_benchmark.BenchmarkSkip(
                model_key="smol",
                slice_id="xbd",
                reason="missing endpoint env BLACKLINE_SMOLVLM2_ENDPOINT",
            )
        ],
    )

    assert "| Liquid | Internal | internal | 10 | 60.0% | 80.0% | 90.0% | 1 | 2 |" in markdown
    assert "`smol` on `xbd`" in markdown
