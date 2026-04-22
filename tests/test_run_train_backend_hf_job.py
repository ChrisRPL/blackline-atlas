from __future__ import annotations

import os
import sys
import types
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

    assert payload["model_name"] == "LFM2.5-VL-450M"
    assert payload["dataset"]["path"] == str((bundle_dir / "train.jsonl").resolve())
    assert payload["dataset"]["image_root"] == str(bundle_dir.resolve())
    assert payload["dataset"]["limit"] == 16
    assert payload["training_config"]["extends"] == "DEFAULT_VLM_SFT"
    assert payload["peft_config"]["extends"] == "DEFAULT_VLM_LORA"


def test_normalize_model_name_for_leap_strips_liquid_prefix() -> None:
    assert (
        run_train_backend_hf_job.normalize_model_name_for_leap("LiquidAI/LFM2.5-VL-450M")
        == "LFM2.5-VL-450M"
    )
    assert (
        run_train_backend_hf_job.normalize_model_name_for_leap("LFM2.5-VL-450M") == "LFM2.5-VL-450M"
    )


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


def test_sanitize_leap_repo_for_hf_jobs_strips_optional_gpu_deps_and_patches_vlm(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "leap-finetune"
    (repo_dir / "src" / "leap_finetune" / "utils").mkdir(parents=True)
    (repo_dir / "src" / "leap_finetune" / "training_configs").mkdir(parents=True)
    pyproject_path = repo_dir / "pyproject.toml"
    pyproject_path.write_text(
        "\n".join(
            [
                "[project]",
                "dependencies = [",
                '    "torch>=2.8.0",',
                '    "deepspeed>=0.18.0; sys_platform == \\"linux\\"",',
                '    "flash-attn>=2.8.0; sys_platform == \\"linux\\"",',
                '    "transformers>=5.0.0",',
                "]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    logging_utils_path = repo_dir / "src" / "leap_finetune" / "utils" / "logging_utils.py"
    logging_utils_path.write_text(
        "try:\n    import deepspeed\nexcept ImportError:\n    pass\n",
        encoding="utf-8",
    )
    vlm_config_path = repo_dir / "src" / "leap_finetune" / "training_configs" / "vlm_sft_config.py"
    vlm_config_path.write_text(
        'DEFAULT_VLM_SFT = {\n    "deepspeed": DEEPSPEED_CONFIG,\n}\n',
        encoding="utf-8",
    )
    lockfile = repo_dir / "uv.lock"
    lockfile.write_text("lock", encoding="utf-8")

    run_train_backend_hf_job.sanitize_leap_repo_for_hf_jobs(repo_dir=repo_dir)

    pyproject = pyproject_path.read_text(encoding="utf-8")
    assert "flash-attn" not in pyproject
    assert "deepspeed" not in pyproject
    assert "torch>=2.8.0" in pyproject
    assert not lockfile.exists()
    assert "except Exception:" in logging_utils_path.read_text(encoding="utf-8")
    assert '"deepspeed": DEEPSPEED_CONFIG' not in vlm_config_path.read_text(encoding="utf-8")


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


def test_find_latest_checkpoint_dir_picks_highest_checkpoint(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-01"
    (run_dir / "checkpoint-3").mkdir(parents=True)
    (run_dir / "checkpoint-5").mkdir()

    checkpoint_dir = run_train_backend_hf_job.find_latest_checkpoint_dir(tmp_path)

    assert checkpoint_dir == run_dir / "checkpoint-5"


def test_maybe_publish_adapter_artifacts_uploads_filtered_checkpoint(
    monkeypatch, tmp_path: Path
) -> None:
    checkpoint_dir = tmp_path / "outputs" / "run-01" / "checkpoint-5"
    checkpoint_dir.mkdir(parents=True)
    (checkpoint_dir / "adapter_config.json").write_text("{}", encoding="utf-8")
    (checkpoint_dir / "adapter_model.safetensors").write_text("weights", encoding="utf-8")
    api_calls: dict[str, object] = {}

    class _FakeApi:
        def create_repo(self, **kwargs) -> None:
            api_calls["create_repo"] = kwargs

        def upload_folder(self, **kwargs) -> None:
            api_calls["upload_folder"] = kwargs

    monkeypatch.setattr(run_train_backend_hf_job, "HfApi", lambda token=None: _FakeApi())
    monkeypatch.setenv("HF_TOKEN", "hf_test")

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    run_train_backend_hf_job.maybe_publish_adapter_artifacts(
        workspace=workspace,
        output_dir=tmp_path / "outputs",
        repo_id="ChrisRPL/blackline-atlas-train-adapter",
        private=True,
        base_model_id="LiquidAI/LFM2.5-VL-450M",
        run_name="lfm25_vl_sft_train_hf",
    )

    publish_dir = workspace / "publish_adapter"
    assert (publish_dir / "adapter_config.json").exists()
    assert (publish_dir / "adapter_model.safetensors").exists()
    assert (publish_dir / "README.md").exists()
    assert (publish_dir / "training_output_manifest.json").exists()
    assert api_calls["create_repo"] == {
        "repo_id": "ChrisRPL/blackline-atlas-train-adapter",
        "repo_type": "model",
        "private": True,
        "exist_ok": True,
    }
    upload_kwargs = types.SimpleNamespace(**api_calls["upload_folder"])
    assert upload_kwargs.repo_id == "ChrisRPL/blackline-atlas-train-adapter"
    assert upload_kwargs.repo_type == "model"
    assert Path(upload_kwargs.folder_path) == publish_dir


def test_maybe_publish_adapter_artifacts_rejects_checkpoint_without_weights(
    monkeypatch, tmp_path: Path
) -> None:
    checkpoint_dir = tmp_path / "outputs" / "run-01" / "checkpoint-5"
    checkpoint_dir.mkdir(parents=True)
    (checkpoint_dir / "adapter_config.json").write_text("{}", encoding="utf-8")

    class _FakeApi:
        def create_repo(self, **kwargs) -> None:
            _ = kwargs

        def upload_folder(self, **kwargs) -> None:
            _ = kwargs

    monkeypatch.setattr(run_train_backend_hf_job, "HfApi", lambda token=None: _FakeApi())
    monkeypatch.setenv("HF_TOKEN", "hf_test")

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    try:
        run_train_backend_hf_job.maybe_publish_adapter_artifacts(
            workspace=workspace,
            output_dir=tmp_path / "outputs",
            repo_id="ChrisRPL/blackline-atlas-train-adapter",
            private=True,
            base_model_id="LiquidAI/LFM2.5-VL-450M",
            run_name="lfm25_vl_sft_train_hf",
        )
    except FileNotFoundError as exc:
        assert "missing weights" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected missing adapter weights to fail publish")
