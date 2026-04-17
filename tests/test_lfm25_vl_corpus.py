from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts import build_dataset, build_lfm25_vl_corpus  # noqa: E402


def test_write_lfm25_vl_corpus_joins_capture_and_replay_sources(tmp_path: Path) -> None:
    _, replay_dataset_path = build_dataset.write_replay_pack(tmp_path / "replay")
    capture_manifest_path = _write_capture_manifest(
        tmp_path / "simsat_capture",
        replay_dataset_path,
    )

    grounding_path, candidate_eval_path, splits_path = build_lfm25_vl_corpus.write_lfm25_vl_corpus(
        output_dir=tmp_path / "corpus",
        capture_manifest_path=capture_manifest_path,
        replay_dataset_path=replay_dataset_path,
    )

    grounding_rows = _read_jsonl(grounding_path)
    candidate_rows = _read_jsonl(candidate_eval_path)
    splits = json.loads(splits_path.read_text(encoding="utf-8"))

    assert len(grounding_rows) == 2
    assert len(candidate_rows) == 2
    assert grounding_rows[0]["record_id"] == "hero_port_disruption__grounding"
    assert (
        grounding_rows[0]["messages"][0]["content"][0]["image"]
        == "hero_port_disruption/current.png"
    )
    assert grounding_rows[0]["targets"][0]["label"] == "probable_large_scale_disruption"
    assert candidate_rows[0]["current_image_path"] == "hero_port_disruption/current.png"
    assert candidate_rows[0]["baseline_image_path"] == "hero_port_disruption/baseline.png"
    assert candidate_rows[0]["prompt"]["system"].startswith(
        "You are Blackline Atlas candidate generation."
    )
    assert candidate_rows[0]["simsat"]["current"]["window_seconds"] == 864000.0
    assert splits["policy"].startswith("Hold out hero/demo AOIs")
    assert splits["split_counts"] == {
        "dev": 0,
        "holdout_geo": 2,
        "holdout_stress": 0,
        "train": 0,
    }
    assert {case["holdout_reason"] for case in splits["cases"]} == {"hero_demo"}


def test_build_lfm25_vl_corpus_skips_cases_without_real_capture_images(tmp_path: Path) -> None:
    _, replay_dataset_path = build_dataset.write_replay_pack(tmp_path / "replay")
    capture_manifest_path = _write_capture_manifest(
        tmp_path / "simsat_capture",
        replay_dataset_path,
        missing_current_case_id="bridge_access_obstruction",
    )

    grounding_rows, candidate_rows, splits = build_lfm25_vl_corpus.build_lfm25_vl_corpus(
        capture_manifest_path=capture_manifest_path,
        replay_dataset_path=replay_dataset_path,
    )

    assert [row["case_id"] for row in grounding_rows] == ["hero_port_disruption"]
    assert [row["case_id"] for row in candidate_rows] == ["hero_port_disruption"]
    assert splits["split_counts"]["holdout_geo"] == 2


def _write_capture_manifest(
    capture_root: Path,
    replay_dataset_path: Path,
    *,
    missing_current_case_id: str | None = None,
) -> Path:
    cases = _read_jsonl(replay_dataset_path)
    records = []
    for case in cases:
        case_dir = capture_root / case["case_id"]
        case_dir.mkdir(parents=True, exist_ok=True)
        current_image = case_dir / "current.png"
        baseline_image = case_dir / "baseline.png"
        if case["case_id"] != missing_current_case_id:
            current_image.write_bytes(b"current")
        baseline_image.write_bytes(b"baseline")

        current_metadata_path = case_dir / "current-metadata.json"
        baseline_metadata_path = case_dir / "baseline-metadata.json"
        current_metadata_path.write_text("{}", encoding="utf-8")
        baseline_metadata_path.write_text("{}", encoding="utf-8")

        records.append(
            {
                "case_id": case["case_id"],
                "pack_version": "simsat-capture-v1",
                "asset": case["asset"],
                "current": {
                    "frame_id": case["current_frame"]["frame"]["frame_id"],
                    "requested_timestamp": case["current_frame"]["frame"]["captured_at"],
                    "request_url": (
                        "https://example.test/data/image/sentinel?"
                        "lon=1.0&lat=2.0&timestamp=2026-04-14T18:40:00Z"
                        "&spectral_bands=red&spectral_bands=green&spectral_bands=blue"
                        "&size_km=5.0&window_seconds=864000&return_type=png"
                    ),
                    "image_path": (
                        None
                        if case["case_id"] == missing_current_case_id
                        else str(current_image.resolve())
                    ),
                    "metadata_path": str(current_metadata_path.resolve()),
                    "response_metadata": {
                        "image_available": case["case_id"] != missing_current_case_id,
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
                    "request_url": (
                        "https://example.test/data/image/sentinel?"
                        "lon=1.0&lat=2.0&timestamp=2025-09-01T10:00:00Z"
                        "&spectral_bands=red&spectral_bands=green&spectral_bands=blue"
                        "&size_km=5.0&window_seconds=864000&return_type=png"
                    ),
                    "image_path": str(baseline_image.resolve()),
                    "metadata_path": str(baseline_metadata_path.resolve()),
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
        )

    manifest_path = capture_root / "simsat_capture_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "pack_version": "simsat-capture-v1",
                "case_count": len(records),
                "cases": records,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
