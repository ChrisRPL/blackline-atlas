from __future__ import annotations

import json
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.training_run import TrainAdapterDatasetManifest  # noqa: E402
from training.scripts import run_train_backend, train_adapter  # noqa: E402


def test_build_leap_job_config_payload_from_smoke_config(tmp_path: Path) -> None:
    dataset_manifest = TrainAdapterDatasetManifest(
        version="blackline-train-adapter-v1",
        run_name="lfm25_vl_sft_smoke",
        purpose="smoke",
        model_id="LiquidAI/LFM2.5-VL-450M",
        task_kind="candidate_json_sft",
        source_replay_dataset="training/replay_pack/train_01.jsonl",
        capture_manifest=str(tmp_path / "capture.json"),
        liquid_grounding_dataset=str(tmp_path / "liquid_grounding.jsonl"),
        candidate_eval_dataset=str(tmp_path / "blackline_candidate_eval.jsonl"),
        splits_manifest=str(tmp_path / "splits.json"),
        image_root=str(tmp_path / "corpus"),
        leap_train_dataset=str(tmp_path / "train.jsonl"),
        leap_eval_dataset=str(tmp_path / "eval.jsonl"),
        leap_summary=str(tmp_path / "summary.json"),
        source_split_counts={"train": 3, "dev": 0, "holdout_geo": 1, "holdout_stress": 0},
        eval_mode="smoke",
        benchmark_on_start=True,
        max_eval_cases=8,
        save_full_predictions=False,
        execution_environment="local",
        output_dir="training/eval_runs/lfm25-vl-sft-smoke",
        hf_flavor="l4x1",
        hf_timeout="4h",
    )
    config = train_adapter.load_train_adapter_config(
        ROOT / "training" / "configs" / "lfm25_vl_sft_smoke.yaml"
    )

    payload = run_train_backend.build_leap_job_config_payload(
        config=config,
        dataset_manifest=dataset_manifest,
    )

    assert payload["model_name"] == "LiquidAI/LFM2.5-VL-450M"
    assert payload["dataset"]["path"].endswith("/train.jsonl")
    assert payload["dataset"]["image_root"].endswith("/corpus")
    assert payload["dataset"]["limit"] == 12
    assert payload["training_config"]["extends"] == "DEFAULT_VLM_SFT"
    assert payload["training_config"]["gradient_accumulation_steps"] == 4
    assert payload["peft_config"]["extends"] == "DEFAULT_VLM_LORA"
    assert payload["peft_config"]["use_peft"] is True


def test_resolve_output_dir_uses_repo_stage_dir_for_hf_jobs() -> None:
    config = train_adapter.load_train_adapter_config(
        ROOT / "training" / "configs" / "lfm25_vl_sft_train_hf.yaml"
    )

    output_dir = run_train_backend.resolve_output_dir(
        config_path=ROOT / "training" / "configs" / "lfm25_vl_sft_train_hf.yaml",
        config=config,
    )

    assert output_dir == (ROOT / "training" / "eval_runs" / "lfm25_vl_sft_train_hf").resolve()


def test_package_train_bundle_copies_only_referenced_images(tmp_path: Path) -> None:
    image_root = tmp_path / "corpus"
    image_dir = image_root / "images" / "port_case"
    image_dir.mkdir(parents=True)
    (image_dir / "baseline.png").write_bytes(b"baseline")
    (image_dir / "current.png").write_bytes(b"current")
    (image_dir / "unused.png").write_bytes(b"unused")

    train_path = tmp_path / "train.jsonl"
    eval_path = tmp_path / "eval.jsonl"
    summary_path = tmp_path / "summary.json"
    dataset_manifest_path = tmp_path / "dataset_manifest.json"

    record = {
        "record_id": "port_case__candidate_sft",
        "case_id": "port_case",
        "asset_id": "port_01",
        "source_split": "train",
        "target_split": "train",
        "task_kind": "candidate_json_sft",
        "messages": [
            {"role": "system", "content": "sys"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "prompt"},
                    {"type": "image", "image": "images/port_case/baseline.png"},
                    {"type": "image", "image": "images/port_case/current.png"},
                ],
            },
            {"role": "assistant", "content": '{"action":"discard"}'},
        ],
    }
    train_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    eval_path.write_text("", encoding="utf-8")
    summary_path.write_text(
        json.dumps(
            {
                "train_records": 1,
                "eval_records": 0,
                "source_split_counts": {
                    "train": 1,
                    "dev": 0,
                    "holdout_geo": 0,
                    "holdout_stress": 0,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    dataset_manifest = TrainAdapterDatasetManifest(
        version="blackline-train-adapter-v1",
        run_name="smoke",
        purpose="smoke",
        model_id="LiquidAI/LFM2.5-VL-450M",
        task_kind="candidate_json_sft",
        source_replay_dataset="training/replay_pack/train_01.jsonl",
        capture_manifest=str(tmp_path / "capture.json"),
        liquid_grounding_dataset=str(tmp_path / "liquid_grounding.jsonl"),
        candidate_eval_dataset=str(tmp_path / "blackline_candidate_eval.jsonl"),
        splits_manifest=str(tmp_path / "splits.json"),
        image_root=str(image_root),
        leap_train_dataset=str(train_path),
        leap_eval_dataset=str(eval_path),
        leap_summary=str(summary_path),
        source_split_counts={"train": 1, "dev": 0, "holdout_geo": 0, "holdout_stress": 0},
        eval_mode="smoke",
        benchmark_on_start=True,
        max_eval_cases=8,
        save_full_predictions=False,
        execution_environment="local",
        output_dir="training/eval_runs/smoke",
        hf_flavor="l4x1",
        hf_timeout="4h",
    )
    dataset_manifest_path.write_text(
        json.dumps(dataset_manifest.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )

    bundle_manifest = run_train_backend.package_train_bundle(
        dataset_manifest_path=dataset_manifest_path,
        dataset_manifest=dataset_manifest,
        run_name="smoke",
        output_dir=tmp_path / "bundle",
        backend="leap_finetune",
        authoritative_eval_note="Frozen eval stays separate.",
    )

    bundle_dir = Path(bundle_manifest.bundle_dir)
    assert (bundle_dir / "train.jsonl").exists()
    assert (bundle_dir / "dataset_manifest.json").exists()
    assert (bundle_dir / "images" / "port_case" / "baseline.png").exists()
    assert (bundle_dir / "images" / "port_case" / "current.png").exists()
    assert not (bundle_dir / "images" / "port_case" / "unused.png").exists()

    archive_path = Path(bundle_manifest.bundle_archive)
    assert archive_path.exists()
    with tarfile.open(archive_path, mode="r:gz") as tar:
        names = tar.getnames()
    assert any(name.endswith("train.jsonl") for name in names)
