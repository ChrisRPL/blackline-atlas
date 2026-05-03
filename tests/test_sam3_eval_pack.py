from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.sam3_eval import Sam3EvalCase  # noqa: E402
from training.scripts import build_sam3_eval_pack, package_sam3_eval_hf_dataset  # noqa: E402


def test_build_sam3_eval_pack_freezes_mixed_eval_cases() -> None:
    pack = build_sam3_eval_pack.build_sam3_eval_pack()

    assert pack["pack_version"] == "sam3-eval-v2"
    assert pack["case_count"] == 22
    assert pack["action_counts"]["downlink_now"] == 12
    assert pack["action_counts"]["discard"] == 10

    cases = [Sam3EvalCase.model_validate(row) for row in pack["cases"]]
    positive = next(case for case in cases if case.expected_action == "downlink_now")
    negative = next(case for case in cases if case.expected_action == "discard")

    assert positive.prompts
    assert positive.expected_bbox_norm is not None
    assert positive.expected_visual_evidence_tags
    assert negative.expected_bbox_norm is None
    assert negative.expected_visual_evidence_tags == []
    assert negative.hard_negative_reason is not None


def test_write_sam3_eval_pack_writes_manifest_and_jsonl(tmp_path: Path) -> None:
    manifest_path, dataset_path = build_sam3_eval_pack.write_sam3_eval_pack(
        output_dir=tmp_path,
        max_cases=6,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = [
        Sam3EvalCase.model_validate(json.loads(line))
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert manifest["case_count"] == 6
    assert len(rows) == 6
    assert {row.expected_action for row in rows} == {"discard", "downlink_now"}


def test_write_sam3_eval_pack_materializes_capture_image_refs(tmp_path: Path) -> None:
    source_pack = build_sam3_eval_pack.build_sam3_eval_pack(max_cases=2)
    source_case_ids = [case["source_case_id"] for case in source_pack["cases"]]
    capture_manifest = tmp_path / "capture_manifest.json"
    capture_manifest.write_text(
        json.dumps(
            {
                "pack_version": "simsat-capture-v1",
                "case_count": 2,
                "cases": [
                    _capture_record(case_id, tmp_path / case_id) for case_id in source_case_ids
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest_path, dataset_path = build_sam3_eval_pack.write_sam3_eval_pack(
        output_dir=tmp_path / "materialized",
        capture_manifest=capture_manifest,
        require_images=True,
        max_cases=2,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = [
        Sam3EvalCase.model_validate(json.loads(line))
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert manifest["image_counts"] == {"baseline": 2, "current": 2, "pairs": 2}
    assert all(not row.current_frame.frame.image_ref.startswith("pending://") for row in rows)
    assert all(not row.baseline_frame.frame.image_ref.startswith("pending://") for row in rows)


def test_package_sam3_eval_hf_dataset_rewrites_relative_image_refs(tmp_path: Path) -> None:
    capture_manifest = _write_capture_manifest(tmp_path, max_cases=2)
    manifest_path, dataset_path = build_sam3_eval_pack.write_sam3_eval_pack(
        output_dir=tmp_path / "materialized",
        capture_manifest=capture_manifest,
        require_images=True,
        max_cases=2,
    )

    metadata = package_sam3_eval_hf_dataset.package_sam3_eval_hf_dataset(
        input_dataset=dataset_path,
        input_manifest=manifest_path,
        output_dir=tmp_path / "hf_dataset",
    )
    rows = [
        Sam3EvalCase.model_validate(json.loads(line))
        for line in (tmp_path / "hf_dataset" / "sam3_eval_pack.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]

    assert metadata["case_count"] == 2
    assert metadata["image_count"] == 4
    assert rows[0].current_frame.frame.image_ref.startswith("images/")
    assert (tmp_path / "hf_dataset" / rows[0].current_frame.frame.image_ref).exists()


def _capture_record(case_id: str, case_dir: Path) -> dict[str, object]:
    current_path = case_dir / "current.png"
    baseline_path = case_dir / "baseline.png"
    current_path.parent.mkdir(parents=True, exist_ok=True)
    current_path.write_bytes(b"current")
    baseline_path.write_bytes(b"baseline")
    metadata = {
        "image_available": True,
        "source": "sentinel-2b",
        "spectral_bands": ["red", "green", "blue"],
        "footprint": [],
        "size_km": 5.0,
        "cloud_cover": 0.0,
        "datetime": "2026-01-01T00:00:00Z",
    }
    return {
        "case_id": case_id,
        "pack_version": "simsat-capture-v1",
        "asset": {
            "asset_id": f"{case_id}_asset",
            "asset_name": case_id,
            "asset_type": "logistics_hub",
            "latitude": 0.0,
            "longitude": 0.0,
            "region": "fixture",
            "hero": False,
        },
        "current": {
            "frame_id": f"{case_id}_current",
            "requested_timestamp": "2026-01-01T00:00:00Z",
            "request_url": "http://localhost/current",
            "image_path": str(current_path),
            "metadata_path": str(case_dir / "current-metadata.json"),
            "response_metadata": metadata,
        },
        "baseline": {
            "frame_id": f"{case_id}_baseline",
            "requested_timestamp": "2025-01-01T00:00:00Z",
            "request_url": "http://localhost/baseline",
            "image_path": str(baseline_path),
            "metadata_path": str(case_dir / "baseline-metadata.json"),
            "response_metadata": metadata,
        },
    }


def _write_capture_manifest(tmp_path: Path, *, max_cases: int) -> Path:
    source_pack = build_sam3_eval_pack.build_sam3_eval_pack(max_cases=max_cases)
    source_case_ids = [case["source_case_id"] for case in source_pack["cases"]]
    capture_manifest = tmp_path / "capture_manifest.json"
    capture_manifest.write_text(
        json.dumps(
            {
                "pack_version": "simsat-capture-v1",
                "case_count": max_cases,
                "cases": [
                    _capture_record(case_id, tmp_path / case_id) for case_id in source_case_ids
                ],
            }
        ),
        encoding="utf-8",
    )
    return capture_manifest
