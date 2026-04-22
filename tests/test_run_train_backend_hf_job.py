from __future__ import annotations

import os
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


def test_clone_leap_finetune_uses_git_clone(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], check: bool) -> None:
        assert check is True
        calls.append(command)

    monkeypatch.setattr(run_train_backend_hf_job.subprocess, "run", fake_run)

    repo_dir = run_train_backend_hf_job.clone_leap_finetune(
        workspace=tmp_path,
        repo_url="https://github.com/Liquid4All/leap-finetune.git",
        ref="main",
    )

    assert repo_dir == tmp_path / "leap-finetune"
    assert calls == [
        [
            "git",
            "clone",
            "--depth",
            "1",
            "https://github.com/Liquid4All/leap-finetune.git",
            str(tmp_path / "leap-finetune"),
        ],
        ["git", "-C", str(tmp_path / "leap-finetune"), "checkout", "main"],
    ]


def test_run_leap_train_uses_uv_project_run(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict[str, str]]] = []

    def fake_run(command: list[str], check: bool, env: dict[str, str]) -> None:
        assert check is True
        calls.append((command, env))

    monkeypatch.setattr(run_train_backend_hf_job.subprocess, "run", fake_run)
    monkeypatch.setenv("PATH", os.environ.get("PATH", ""))

    run_train_backend_hf_job.run_leap_train(
        repo_dir=tmp_path / "leap-finetune",
        config_path=tmp_path / "job.yaml",
        output_dir="/outputs/blackline-train",
    )

    command, env = calls[0]
    assert command == [
        "uv",
        "run",
        "--directory",
        str(tmp_path / "leap-finetune"),
        "leap-finetune",
        str(tmp_path / "job.yaml"),
    ]
    assert env["OUTPUT_DIR"] == "/outputs/blackline-train"


def test_run_leap_train_retries_with_source_fallback(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict[str, str]]] = []

    def fake_run(command: list[str], check: bool, env: dict[str, str]) -> None:
        assert check is True
        calls.append((command, env))
        if len(calls) == 1:
            raise run_train_backend_hf_job.subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(run_train_backend_hf_job.subprocess, "run", fake_run)
    monkeypatch.setenv("PATH", os.environ.get("PATH", ""))

    run_train_backend_hf_job.run_leap_train(
        repo_dir=tmp_path / "leap-finetune",
        config_path=tmp_path / "job.yaml",
        output_dir="/outputs/blackline-train",
    )

    first_command, first_env = calls[0]
    second_command, second_env = calls[1]
    assert first_command == [
        "uv",
        "run",
        "--directory",
        str(tmp_path / "leap-finetune"),
        "leap-finetune",
        str(tmp_path / "job.yaml"),
    ]
    assert first_env["OUTPUT_DIR"] == "/outputs/blackline-train"
    assert second_command == [
        "uv",
        "run",
        "--directory",
        str(tmp_path / "leap-finetune"),
        "python",
        "-c",
        "from leap_finetune import main; main()",
        str(tmp_path / "job.yaml"),
    ]
    assert second_env["OUTPUT_DIR"] == "/outputs/blackline-train"
    assert second_env["PYTHONPATH"] == str((tmp_path / "leap-finetune" / "src").resolve())
