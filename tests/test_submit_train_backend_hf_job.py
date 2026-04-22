from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts import submit_train_backend_hf_job, train_adapter  # noqa: E402


def test_default_bundle_repo_id_uses_hf_username(monkeypatch) -> None:
    monkeypatch.setattr(
        submit_train_backend_hf_job,
        "whoami",
        lambda token=None: {"name": "ChrisRPL"},
    )

    repo_id = submit_train_backend_hf_job.default_bundle_repo_id(token="hf_test")

    assert repo_id == "ChrisRPL/blackline-atlas-training-bundles"


def test_build_bundle_repo_path_uses_run_name_and_archive_name() -> None:
    path_in_repo = submit_train_backend_hf_job.build_bundle_repo_path(
        bundle_prefix="train-bundles",
        run_name="lfm25_vl_sft_train_hf",
        archive_path=Path("/tmp/lfm25_vl_sft_train_hf_trainer_bundle.tar.gz"),
    )

    assert (
        path_in_repo
        == "train-bundles/lfm25_vl_sft_train_hf/lfm25_vl_sft_train_hf_trainer_bundle.tar.gz"
    )


def test_build_remote_job_spec_from_hf_train_config() -> None:
    config = train_adapter.load_train_adapter_config(
        ROOT / "training" / "configs" / "lfm25_vl_sft_train_hf.yaml"
    )

    payload = submit_train_backend_hf_job.build_remote_job_spec(config=config)

    assert payload["run_name"] == "lfm25_vl_sft_train_hf"
    assert payload["model_id"] == "LiquidAI/LFM2.5-VL-450M"
    assert payload["dataset_test_size"] == 0.1
    assert payload["training_config"]["num_train_epochs"] == 2
