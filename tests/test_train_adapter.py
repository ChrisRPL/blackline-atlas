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


def test_load_train_adapter_config_from_checked_in_hf_aux_yaml() -> None:
    config_path = ROOT / "training" / "configs" / "lfm25_vl_sft_train_hf_aux_v4.yaml"

    config = train_adapter.load_train_adapter_config(config_path)

    assert config.run_name == "lfm25_vl_sft_train_hf_aux_v4"
    assert config.dataset.aux_candidate_eval_datasets == [
        "training/eval_runs/aux-train-inputs/aux_public_seed_v4/blackline_candidate_eval.jsonl"
    ]


def test_load_train_adapter_config_from_checked_in_hf_aux_v5_yaml() -> None:
    config_path = ROOT / "training" / "configs" / "lfm25_vl_sft_train_hf_aux_v5.yaml"

    config = train_adapter.load_train_adapter_config(config_path)

    assert config.run_name == "lfm25_vl_sft_train_hf_aux_v5"
    assert config.dataset.aux_candidate_eval_datasets == [
        "training/eval_runs/aux-train-inputs/aux_public_seed_v5/blackline_candidate_eval.jsonl"
    ]


def test_build_train_adapter_plan_resolves_aux_candidate_eval_paths(tmp_path: Path) -> None:
    aux_path = (
        ROOT
        / "training"
        / "eval_runs"
        / "aux-train-inputs"
        / "aux_public_seed_v4"
        / "blackline_candidate_eval.jsonl"
    )
    config_path = tmp_path / "with_aux.yaml"
    config_path.write_text(
        f"""
version: "2026-04-23"
run_name: "with_aux"
purpose: "with aux"
dataset:
  historical_endpoint: "http://localhost:9005/data/image/sentinel"
  replay_dataset: "training/replay_pack/train_01.jsonl"
  aux_candidate_eval_datasets:
    - "{aux_path}"
  capture_overrides: "training/replay_pack/train_01_capture_overrides.json"
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
  execution_environment: "hf_jobs"
  editable_extras: "dev,vlm,train"
  output_dir: "training/eval_runs/with_aux"
hf_job:
  flavor: "l4x1"
  timeout: "4h"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = train_adapter.load_train_adapter_config(config_path)
    plan = train_adapter.build_train_adapter_plan(config_path=config_path, config=config)

    assert plan.replay_dataset.endswith("/training/replay_pack/train_01.jsonl")
    assert plan.aux_candidate_eval_datasets == [str(aux_path)]


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


def test_prepare_training_artifacts_merges_aux_candidate_eval_before_leap_export(
    tmp_path: Path,
    monkeypatch,
) -> None:
    aux_dataset_path = tmp_path / "aux" / "blackline_candidate_eval.jsonl"
    aux_dataset_path.parent.mkdir(parents=True)
    aux_dataset_path.write_text("{}", encoding="utf-8")

    config_path = tmp_path / "with_aux.yaml"
    config_path.write_text(
        f"""
version: "2026-04-23"
run_name: "with_aux"
purpose: "with aux"
dataset:
  capture_manifest: "capture/simsat_capture_manifest.json"
  replay_dataset: "training/replay_pack/train_01.jsonl"
  aux_candidate_eval_datasets:
    - "{aux_dataset_path}"
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
  output_dir: "training/eval_runs/with_aux"
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

    internal_candidate_eval_path = tmp_path / "corpus" / "blackline_candidate_eval.jsonl"
    merged_candidate_eval_path = (
        tmp_path / "corpus" / "merged_candidate_eval" / "blackline_candidate_eval.jsonl"
    )

    def fake_write_lfm25_vl_corpus(*, output_dir: Path, **_: object) -> tuple[Path, Path, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        grounding = output_dir / "liquid_grounding.jsonl"
        candidate = output_dir / "blackline_candidate_eval.jsonl"
        splits = output_dir / "splits.json"
        grounding.write_text("{}", encoding="utf-8")
        candidate.write_text("{}", encoding="utf-8")
        splits.write_text("{}", encoding="utf-8")
        return grounding, candidate, splits

    def fake_materialize_aux_train_slice(
        *,
        source_datasets: tuple[Path, ...],
        output_dir: Path,
        **_: object,
    ) -> tuple[Path, Path]:
        assert source_datasets == (internal_candidate_eval_path, aux_dataset_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        merged = output_dir / "blackline_candidate_eval.jsonl"
        summary = output_dir / "summary.json"
        merged.write_text("{}", encoding="utf-8")
        summary.write_text("{}", encoding="utf-8")
        return merged, summary

    def fake_write_leap_vlm_sft_records(
        *,
        candidate_eval_path: Path,
        output_dir: Path,
        absolute_image_paths: bool = False,
    ) -> tuple[Path, Path, Path]:
        assert absolute_image_paths is False
        assert candidate_eval_path == merged_candidate_eval_path
        output_dir.mkdir(parents=True, exist_ok=True)
        train_path = output_dir / "train.jsonl"
        eval_path = output_dir / "eval.jsonl"
        summary_path = output_dir / "summary.json"
        train_path.write_text("{}", encoding="utf-8")
        eval_path.write_text("", encoding="utf-8")
        summary_path.write_text(
            json.dumps(
                {
                    "train_records": 5,
                    "source_split_counts": {
                        "train": 5,
                        "dev": 0,
                        "holdout_geo": 0,
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
        train_adapter,
        "materialize_aux_train_slice",
        fake_materialize_aux_train_slice,
    )
    monkeypatch.setattr(
        train_adapter, "write_leap_vlm_sft_records", fake_write_leap_vlm_sft_records
    )

    config = train_adapter.load_train_adapter_config(config_path)
    plan = train_adapter.build_train_adapter_plan(config_path=config_path, config=config)
    artifacts = train_adapter.prepare_training_artifacts(plan=plan, skip_capture=True)

    payload = json.loads(Path(artifacts.dataset_manifest).read_text(encoding="utf-8"))
    assert payload["source_replay_dataset"].endswith("/training/replay_pack/train_01.jsonl")
    assert payload["source_aux_candidate_eval_datasets"] == [str(aux_dataset_path)]
    assert payload["source_internal_candidate_eval_dataset"].endswith(
        "/corpus/blackline_candidate_eval.jsonl"
    )
    assert payload["candidate_eval_dataset"].endswith(
        "/corpus/merged_candidate_eval/blackline_candidate_eval.jsonl"
    )
