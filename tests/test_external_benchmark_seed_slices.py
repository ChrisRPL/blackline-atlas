from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_xbd_public_seed_slice_is_materialized() -> None:
    dataset_path = ROOT / "training" / "external_benchmarks" / "xbd_public_seed"
    dataset_path = dataset_path / "blackline_candidate_eval.jsonl"
    rows = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(rows) == 4
    assert {row["benchmark_source"] for row in rows} == {"xBD"}
    assert {row["expected_action"] for row in rows} == {"discard", "defer", "downlink_now"}
    for row in rows:
        assert (dataset_path.parent / row["current_image_path"]).exists()
        assert (dataset_path.parent / row["baseline_image_path"]).exists()


def test_spacenet8_public_seed_slice_is_materialized() -> None:
    dataset_path = ROOT / "training" / "external_benchmarks" / "spacenet8_public_seed"
    dataset_path = dataset_path / "blackline_candidate_eval.jsonl"
    rows = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(rows) == 4
    assert {row["benchmark_source"] for row in rows} == {"SpaceNet8"}
    assert {row["expected_action"] for row in rows} == {"discard", "downlink_now"}
    for row in rows:
        assert (dataset_path.parent / row["current_image_path"]).exists()
        assert (dataset_path.parent / row["baseline_image_path"]).exists()


def test_internal_public_seed_slice_is_materialized() -> None:
    dataset_path = ROOT / "training" / "internal_benchmarks" / "blackline_public_seed"
    dataset_path = dataset_path / "blackline_candidate_eval.jsonl"
    rows = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(rows) == 1
    assert {row["benchmark_source"] for row in rows} == {"BlacklineInternalPublicSeed"}
    assert {row["expected_action"] for row in rows} == {"downlink_now"}
    for row in rows:
        assert (dataset_path.parent / row["current_image_path"]).exists()
        assert (dataset_path.parent / row["baseline_image_path"]).exists()
