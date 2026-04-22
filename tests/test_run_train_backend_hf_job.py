from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts import run_train_backend_hf_job  # noqa: E402


def test_build_leap_config_from_bundle_uses_bundle_paths(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "trainer_bundle"
    bundle_dir.mkdir()
    job_spec = {
        "project_name": "blackline-atlas",
        "model_id": "LiquidAI/LFM2.5-VL-450M",
        "dataset_test_size": 0.1,
        "dataset_limit": 16,
        "training_config": {
            "extends": "DEFAULT_VLM_SFT",
            "num_train_epochs": 2,
        },
        "peft_config": {
            "extends": "DEFAULT_VLM_LORA",
            "use_peft": True,
        },
    }

    payload = run_train_backend_hf_job.build_leap_config_from_bundle(
        job_spec=job_spec,
        bundle_dir=bundle_dir,
    )

    assert payload["dataset"]["path"] == str((bundle_dir / "train.jsonl").resolve())
    assert payload["dataset"]["image_root"] == str(bundle_dir.resolve())
    assert payload["dataset"]["limit"] == 16
    assert payload["training_config"]["extends"] == "DEFAULT_VLM_SFT"
    assert payload["peft_config"]["extends"] == "DEFAULT_VLM_LORA"
