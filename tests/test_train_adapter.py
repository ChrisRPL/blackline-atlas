from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts import train_adapter  # noqa: E402


def test_load_train_adapter_config_from_checked_in_smoke_yaml() -> None:
    config_path = ROOT / "training" / "configs" / "lfm25_vl_sft_smoke.yaml"

    config = train_adapter.load_train_adapter_config(config_path)

    assert config.run_name == "lfm25_vl_sft_smoke"
    assert config.eval.mode == "smoke"
    assert config.dataset.replay_dataset == "training/replay_pack/train_01.jsonl"
    assert config.trainer is not None
    assert config.trainer.backend == "leap_finetune"
    assert config.trainer.dataset_limit == 12


def test_build_train_adapter_plan_resolves_paths() -> None:
    config_path = ROOT / "training" / "configs" / "lfm25_vl_full_eval.yaml"
    config = train_adapter.load_train_adapter_config(config_path)

    plan = train_adapter.build_train_adapter_plan(config_path=config_path, config=config)

    assert plan.eval_mode == "full_eval"
    assert plan.execution_environment == "hf_jobs"
    assert plan.replay_dataset.endswith("/training/replay_pack/non_demo_eval.jsonl")
    assert plan.capture_manifest.endswith(
        "/training/corpus/lfm25-vl-non-demo/capture/simsat_capture_manifest.json"
    )


def test_load_train_adapter_config_from_checked_in_hf_train_yaml() -> None:
    config_path = ROOT / "training" / "configs" / "lfm25_vl_sft_train_hf.yaml"

    config = train_adapter.load_train_adapter_config(config_path)

    assert config.run_name == "lfm25_vl_sft_train_hf"
    assert config.runtime.execution_environment == "hf_jobs"
    assert config.trainer is not None
    assert config.trainer.training_config.num_train_epochs == 2


def test_prepare_training_artifacts_writes_dataset_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = tmp_path / "mini.yaml"
    config_path.write_text(
        """
version: "2026-04-22"
run_name: "mini"
purpose: "mini"
dataset:
  capture_manifest: "capture/simsat_capture_manifest.json"
  replay_dataset: "training/replay_pack/train_01.jsonl"
  capture_output_dir: "capture"
  corpus_output_dir: "corpus"
  leap_output_dir: "leap"
model:
  model_id: "LiquidAI/LFM2.5-VL-450M"
  task_kind: "candidate_json_sft"
eval:
  mode: "smoke"
  benchmark_on_start: true
  max_eval_cases: 4
  save_full_predictions: false
runtime:
  execution_environment: "local"
  editable_extras: "dev,vlm,train"
  output_dir: "training/eval_runs/mini"
hf_job:
  flavor: "l4x1"
  timeout: "4h"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    capture_dir = tmp_path / "capture"
    capture_dir.mkdir()
    capture_manifest_path = capture_dir / "simsat_capture_manifest.json"
    capture_manifest_path.write_text("{}", encoding="utf-8")

    def fake_write_lfm25_vl_corpus(*, output_dir: Path, **_: object) -> tuple[Path, Path, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        grounding = output_dir / "liquid_grounding.jsonl"
        candidate = output_dir / "blackline_candidate_eval.jsonl"
        splits = output_dir / "splits.json"
        grounding.write_text("{}", encoding="utf-8")
        candidate.write_text("{}", encoding="utf-8")
        splits.write_text("{}", encoding="utf-8")
        return grounding, candidate, splits

    def fake_write_leap_vlm_sft_records(
        *,
        candidate_eval_path: Path,
        output_dir: Path,
        absolute_image_paths: bool = False,
    ) -> tuple[Path, Path, Path]:
        assert absolute_image_paths is False
        assert candidate_eval_path.name == "blackline_candidate_eval.jsonl"
        output_dir.mkdir(parents=True, exist_ok=True)
        train_path = output_dir / "train.jsonl"
        eval_path = output_dir / "eval.jsonl"
        summary_path = output_dir / "summary.json"
        train_path.write_text("{}", encoding="utf-8")
        eval_path.write_text("", encoding="utf-8")
        summary_path.write_text(
            json.dumps(
                {
                    "train_records": 2,
                    "source_split_counts": {
                        "train": 2,
                        "dev": 0,
                        "holdout_geo": 1,
                        "holdout_stress": 0,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return train_path, eval_path, summary_path

    monkeypatch.setattr(train_adapter, "write_lfm25_vl_corpus", fake_write_lfm25_vl_corpus)
    monkeypatch.setattr(
        train_adapter, "write_leap_vlm_sft_records", fake_write_leap_vlm_sft_records
    )

    config = train_adapter.load_train_adapter_config(config_path)
    plan = train_adapter.build_train_adapter_plan(config_path=config_path, config=config)
    artifacts = train_adapter.prepare_training_artifacts(plan=plan, skip_capture=True)

    payload = json.loads(Path(artifacts.dataset_manifest).read_text(encoding="utf-8"))
    assert payload["run_name"] == "mini"
    assert payload["candidate_eval_dataset"].endswith("/corpus/blackline_candidate_eval.jsonl")
    assert payload["image_root"].endswith("/corpus")
    assert payload["source_split_counts"]["train"] == 2
    assert payload["execution_environment"] == "local"
