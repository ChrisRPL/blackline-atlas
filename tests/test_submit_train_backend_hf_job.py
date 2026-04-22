from __future__ import annotations

import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.training_run import TrainBundleManifest  # noqa: E402
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


def test_default_leap_ref_is_pinned() -> None:
    args = submit_train_backend_hf_job.parse_args([])

    assert args.leap_ref == "d017458"


def test_main_reports_credit_failure_after_bundle_upload(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    class _FakeHfHubHTTPError(Exception):
        def __init__(self, message: str, status_code: int) -> None:
            super().__init__(message)
            self.response = types.SimpleNamespace(status_code=status_code)

    class _FakeApi:
        def create_repo(self, **kwargs) -> None:
            _ = kwargs

        def upload_file(self, **kwargs) -> None:
            _ = kwargs

        def run_uv_job(self, **kwargs):
            _ = kwargs
            raise _FakeHfHubHTTPError(
                "Pre-paid credit balance is insufficient - add more credits.",
                402,
            )

    bundle_dir = tmp_path / "trainer_bundle"
    bundle_dir.mkdir()
    bundle_archive = tmp_path / "bundle.tar.gz"
    bundle_archive.write_bytes(b"tar")
    bundle_manifest = TrainBundleManifest(
        version="blackline-train-bundle-v1",
        run_name="lfm25_vl_sft_train_hf",
        backend="leap_finetune",
        dataset_manifest=str(bundle_dir / "dataset_manifest.json"),
        train_jsonl=str(bundle_dir / "train.jsonl"),
        eval_jsonl=str(bundle_dir / "eval.jsonl"),
        summary_json=str(bundle_dir / "summary.json"),
        image_root=str(bundle_dir),
        bundle_dir=str(bundle_dir),
        bundle_archive=str(bundle_archive),
        train_records=23,
        eval_records=0,
        authoritative_eval_note="Frozen eval stays separate.",
    )
    (bundle_dir / "bundle_manifest.json").write_text(
        json.dumps(bundle_manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(submit_train_backend_hf_job, "HfApi", lambda token: _FakeApi())
    monkeypatch.setattr(submit_train_backend_hf_job, "HfHubHTTPError", _FakeHfHubHTTPError)
    monkeypatch.setattr(submit_train_backend_hf_job, "get_token", lambda: "hf_test")
    monkeypatch.setattr(
        submit_train_backend_hf_job.run_train_backend,
        "materialize_train_backend",
        lambda **kwargs: (
            types.SimpleNamespace(generated_config_path="/tmp/generated.yaml"),
            bundle_manifest,
        ),
    )

    exit_code = submit_train_backend_hf_job.main(
        [
            "--config",
            str(ROOT / "training" / "configs" / "lfm25_vl_sft_train_hf.yaml"),
            "--bundle-repo-id",
            "ChrisRPL/blackline-atlas-training-bundles",
            "--submit",
            "--skip-prepare",
        ]
    )

    output = capsys.readouterr().out
    manifest_payload = json.loads((bundle_dir / "bundle_manifest.json").read_text(encoding="utf-8"))

    assert exit_code == 2
    assert "status=upload_succeeded_submit_failed" in output
    assert "failure_reason=hf_jobs_insufficient_credits" in output
    assert "bundle_repo_id=ChrisRPL/blackline-atlas-training-bundles" in output
    assert (
        manifest_payload["uploaded_bundle_repo_id"] == "ChrisRPL/blackline-atlas-training-bundles"
    )
    assert manifest_payload["last_submit_status"] == "upload_succeeded_submit_failed"
    assert manifest_payload["last_submit_error"] == "hf_jobs_insufficient_credits"
