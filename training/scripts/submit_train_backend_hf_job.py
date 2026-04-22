from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from huggingface_hub import HfApi, get_token, whoami
from huggingface_hub.errors import HfHubHTTPError

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.training_run import TrainBundleManifest  # noqa: E402
from training.scripts import run_train_backend, train_adapter  # noqa: E402

DEFAULT_CONFIG_PATH = ROOT / "training" / "configs" / "lfm25_vl_sft_train_hf.yaml"
DEFAULT_BUNDLE_PREFIX = "train-bundles"
DEFAULT_BUNDLE_REPO_SUFFIX = "blackline-atlas-training-bundles"
DEFAULT_ADAPTER_REPO_PREFIX = "blackline-atlas"
DEFAULT_REMOTE_SCRIPT = ROOT / "training" / "scripts" / "run_train_backend_hf_job.py"
DEFAULT_LEAP_REF = "d017458"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a Blackline train bundle, upload it to HF, and optionally submit "
            "the remote LEAP VLM training job."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"HF train config. Default: {DEFAULT_CONFIG_PATH}",
    )
    parser.add_argument(
        "--bundle-repo-id",
        default=None,
        help="Dataset repo id for uploaded train bundles. Default: derived from HF username.",
    )
    parser.add_argument(
        "--bundle-prefix",
        default=DEFAULT_BUNDLE_PREFIX,
        help=f'Path prefix inside the dataset repo. Default: "{DEFAULT_BUNDLE_PREFIX}".',
    )
    parser.add_argument(
        "--bundle-public",
        action="store_true",
        help="Create the bundle dataset repo as public. Default: private.",
    )
    parser.add_argument(
        "--skip-capture",
        action="store_true",
        help="Reuse the resolved capture manifest if it already exists.",
    )
    parser.add_argument(
        "--skip-prepare",
        action="store_true",
        help="Reuse the resolved dataset manifest and exported LEAP files.",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Actually submit the HF job. Without this flag, only print the plan.",
    )
    parser.add_argument(
        "--remote-script",
        type=Path,
        default=DEFAULT_REMOTE_SCRIPT,
        help=f"Remote HF runner script path. Default: {DEFAULT_REMOTE_SCRIPT}",
    )
    parser.add_argument(
        "--leap-ref",
        default=DEFAULT_LEAP_REF,
        help=f'Leap git ref for the remote job install. Default: "{DEFAULT_LEAP_REF}".',
    )
    parser.add_argument(
        "--publish-adapter-repo-id",
        default=None,
        help=(
            "Optional Hub model repo id for published adapter artifacts. "
            "Default: derived from HF username + run name."
        ),
    )
    parser.add_argument(
        "--publish-adapter-public",
        action="store_true",
        help="Publish the adapter model repo as public. Default: private.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    token = get_token()
    if not token:
        raise RuntimeError("HF token missing. Run `hf auth login` first.")
    config = train_adapter.load_train_adapter_config(args.config)
    if config.trainer is None:
        raise ValueError(f"missing trainer section in config: {args.config}")
    bundle_repo_id = args.bundle_repo_id or default_bundle_repo_id(token=token)
    publish_adapter_repo_id = (
        args.publish_adapter_repo_id
        or config.hf_job.publish_adapter_repo_id
        or default_adapter_repo_id(token=token, run_name=config.run_name)
    )
    publish_adapter_private = (
        config.hf_job.publish_adapter_private and not args.publish_adapter_public
    )
    plan, bundle_manifest = run_train_backend.materialize_train_backend(
        config_path=args.config,
        skip_capture=args.skip_capture,
        skip_prepare=args.skip_prepare,
    )
    path_in_repo = build_bundle_repo_path(
        bundle_prefix=args.bundle_prefix,
        run_name=config.run_name,
        archive_path=Path(bundle_manifest.bundle_archive),
    )
    job_spec = build_remote_job_spec(config=config)

    if not args.submit:
        print(f"bundle_repo_id={bundle_repo_id}")
        print(f"bundle_path={path_in_repo}")
        print(f"remote_script={args.remote_script}")
        print(f"publish_adapter_repo_id={publish_adapter_repo_id}")
        print(json.dumps(job_spec, indent=2, sort_keys=True))
        return 0

    api = HfApi(token=token)
    api.create_repo(
        repo_id=bundle_repo_id,
        repo_type="dataset",
        private=not args.bundle_public,
        exist_ok=True,
    )
    api.upload_file(
        path_or_fileobj=bundle_manifest.bundle_archive,
        path_in_repo=path_in_repo,
        repo_id=bundle_repo_id,
        repo_type="dataset",
        token=token,
        commit_message=f"Upload Blackline train bundle for {config.run_name}",
    )
    try:
        job_info = api.run_uv_job(
            script=str(args.remote_script),
            script_args=[
                "--job-spec",
                json.dumps(job_spec, separators=(",", ":")),
                "--bundle-repo-id",
                bundle_repo_id,
                "--bundle-path",
                path_in_repo,
                "--bundle-repo-type",
                "dataset",
                "--output-dir",
                config.runtime.output_dir,
                "--leap-ref",
                args.leap_ref,
                "--publish-adapter-repo-id",
                publish_adapter_repo_id,
                "--publish-adapter-private",
                json.dumps(publish_adapter_private),
            ],
            dependencies=[
                "huggingface-hub>=0.35.0",
                "PyYAML>=6.0.3",
            ],
            python="3.12",
            flavor=config.hf_job.flavor,
            timeout=config.hf_job.timeout,
            env={"PYTHONUNBUFFERED": "1"},
            secrets={"HF_TOKEN": token},
        )
    except HfHubHTTPError as exc:
        if _is_hf_jobs_credit_error(exc):
            _write_bundle_submit_status(
                bundle_manifest=bundle_manifest,
                bundle_repo_id=bundle_repo_id,
                bundle_path=path_in_repo,
                submit_status="upload_succeeded_submit_failed",
                submit_error="hf_jobs_insufficient_credits",
            )
            print("status=upload_succeeded_submit_failed")
            print("failure_reason=hf_jobs_insufficient_credits")
            print(f"bundle_repo_id={bundle_repo_id}")
            print(f"bundle_path={path_in_repo}")
            print(f"generated_config={plan.generated_config_path}")
            print(
                "next_step=add Hugging Face Jobs credits, then rerun the same command "
                "with --skip-prepare --submit"
            )
            return 2
        raise

    _write_bundle_submit_status(
        bundle_manifest=bundle_manifest,
        bundle_repo_id=bundle_repo_id,
        bundle_path=path_in_repo,
        submit_status="submitted",
        submit_error=None,
    )
    job_url = getattr(job_info, "url", None) or f"https://huggingface.co/jobs/{job_info.id}"
    print(f"job_id={job_info.id}")
    print(f"job_url={job_url}")
    print(f"bundle_repo_id={bundle_repo_id}")
    print(f"bundle_path={path_in_repo}")
    print(f"publish_adapter_repo_id={publish_adapter_repo_id}")
    print(f"generated_config={plan.generated_config_path}")
    return 0


def default_bundle_repo_id(*, token: str) -> str:
    payload = whoami(token=token)
    username = payload.get("name") or payload.get("fullname")
    if not username:
        raise RuntimeError("failed to resolve HF username for bundle repo")
    return f"{username}/{DEFAULT_BUNDLE_REPO_SUFFIX}"


def default_adapter_repo_id(*, token: str, run_name: str) -> str:
    payload = whoami(token=token)
    username = payload.get("name") or payload.get("fullname")
    if not username:
        raise RuntimeError("failed to resolve HF username for adapter repo")
    slug = run_name.replace("_", "-")
    return f"{username}/{DEFAULT_ADAPTER_REPO_PREFIX}-{slug}-adapter"


def build_bundle_repo_path(*, bundle_prefix: str, run_name: str, archive_path: Path) -> str:
    return f"{bundle_prefix}/{run_name}/{archive_path.name}"


def build_remote_job_spec(*, config) -> dict[str, object]:
    trainer = config.trainer
    if trainer is None:
        raise ValueError("trainer config is required")
    return {
        "run_name": config.run_name,
        "project_name": trainer.project_name,
        "model_id": config.model.model_id,
        "dataset_test_size": trainer.dataset_test_size,
        "dataset_limit": trainer.dataset_limit,
        "authoritative_eval_note": trainer.authoritative_eval_note,
        "training_config": trainer.training_config.model_dump(mode="json"),
        "peft_config": trainer.peft_config.model_dump(mode="json"),
    }


def _bundle_manifest_path(bundle_manifest: TrainBundleManifest) -> Path:
    return Path(bundle_manifest.bundle_dir) / run_train_backend.LEAP_BUNDLE_MANIFEST_NAME


def _write_bundle_submit_status(
    *,
    bundle_manifest: TrainBundleManifest,
    bundle_repo_id: str,
    bundle_path: str,
    submit_status: str,
    submit_error: str | None,
) -> None:
    manifest_path = _bundle_manifest_path(bundle_manifest)
    updated_manifest = bundle_manifest.model_copy(
        update={
            "uploaded_bundle_repo_id": bundle_repo_id,
            "uploaded_bundle_path": bundle_path,
            "last_submit_status": submit_status,
            "last_submit_error": submit_error,
        }
    )
    manifest_path.write_text(
        json.dumps(updated_manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _is_hf_jobs_credit_error(exc: HfHubHTTPError) -> bool:
    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    message = str(exc).lower()
    return status_code == 402 or ("credit" in message and "insufficient" in message)


if __name__ == "__main__":
    raise SystemExit(main())
