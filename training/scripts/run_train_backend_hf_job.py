from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path
from shutil import copy2

from huggingface_hub import HfApi, hf_hub_download

DEFAULT_LEAP_REPO = "https://github.com/Liquid4All/leap-finetune.git"
DEFAULT_LEAP_REF = "d017458"
DEFAULT_OUTPUT_DIR = "/outputs/blackline-train"
ADAPTER_REQUIRED_FILES = ("adapter_config.json",)
ADAPTER_WEIGHT_FILES = ("adapter_model.safetensors", "adapter_model.bin")
ADAPTER_PUBLISH_FILES = (
    "adapter_config.json",
    "adapter_model.safetensors",
    "adapter_model.bin",
    "trainer_state.json",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "HF Jobs runner for the Blackline LEAP VLM backend. Downloads a packaged "
            "train bundle, materializes a LEAP config, installs leap-finetune, and runs it."
        ),
    )
    parser.add_argument("--job-spec", required=True, help="Serialized backend spec JSON.")
    parser.add_argument("--bundle-repo-id", required=True, help="HF repo holding the bundle.")
    parser.add_argument("--bundle-path", required=True, help="Path in repo to the bundle tar.gz.")
    parser.add_argument(
        "--bundle-repo-type",
        default="dataset",
        help='HF repo type for the bundle. Default: "dataset".',
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Training output root. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--leap-repo",
        default=DEFAULT_LEAP_REPO,
        help=f"Leap git repo to install from. Default: {DEFAULT_LEAP_REPO}",
    )
    parser.add_argument(
        "--leap-ref",
        default=DEFAULT_LEAP_REF,
        help=f'Leap git ref to install. Default: "{DEFAULT_LEAP_REF}".',
    )
    parser.add_argument(
        "--publish-adapter-repo-id",
        default=None,
        help="Optional Hub model repo id for published PEFT adapter artifacts.",
    )
    parser.add_argument(
        "--publish-adapter-private",
        default="true",
        help='Whether the published adapter repo should be private. Default: "true".',
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    job_spec = json.loads(args.job_spec)
    with tempfile.TemporaryDirectory(prefix="blackline-train-job-") as temp_dir:
        workspace = Path(temp_dir)
        bundle_dir = download_and_extract_bundle(
            workspace=workspace,
            repo_id=args.bundle_repo_id,
            path_in_repo=args.bundle_path,
            repo_type=args.bundle_repo_type,
        )
        leap_config_path = workspace / "leap_vlm_job.yaml"
        write_yaml(
            leap_config_path,
            build_leap_config_from_bundle(
                job_spec=job_spec,
                bundle_dir=bundle_dir,
            ),
        )
        leap_repo_dir = clone_leap_finetune(
            workspace=workspace,
            repo_url=args.leap_repo,
            ref=args.leap_ref,
        )
        sanitize_leap_repo_for_hf_jobs(repo_dir=leap_repo_dir)
        run_leap_train(
            repo_dir=leap_repo_dir,
            config_path=leap_config_path,
            output_dir=args.output_dir,
        )
        maybe_publish_adapter_artifacts(
            workspace=workspace,
            output_dir=Path(args.output_dir),
            repo_id=args.publish_adapter_repo_id,
            private=parse_bool_arg(args.publish_adapter_private),
            base_model_id=str(job_spec["model_id"]),
            run_name=str(job_spec["run_name"]),
        )
        print(f"bundle_dir={bundle_dir}")
        print(f"generated_config={leap_config_path}")
        print(f"output_dir={args.output_dir}")
    return 0


def download_and_extract_bundle(
    *,
    workspace: Path,
    repo_id: str,
    path_in_repo: str,
    repo_type: str,
) -> Path:
    archive_path = Path(
        hf_hub_download(
            repo_id=repo_id,
            filename=path_in_repo,
            repo_type=repo_type,
            token=os.environ.get("HF_TOKEN"),
        )
    )
    extract_dir = workspace / "bundle"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, mode="r:gz") as tar:
        tar.extractall(extract_dir)
    children = [child for child in extract_dir.iterdir() if child.is_dir()]
    if len(children) != 1:
        raise RuntimeError(f"expected exactly one bundle dir, found {len(children)}")
    return children[0]


def build_leap_config_from_bundle(
    *,
    job_spec: dict[str, object],
    bundle_dir: Path,
) -> dict[str, object]:
    dataset_limit = job_spec.get("dataset_limit")
    payload: dict[str, object] = {
        "project_name": job_spec["project_name"],
        "model_name": normalize_model_name_for_leap(str(job_spec["model_id"])),
        "training_type": "vlm_sft",
        "dataset": {
            "path": str((bundle_dir / "train.jsonl").resolve()),
            "type": "vlm_sft",
            "test_size": job_spec["dataset_test_size"],
            "image_root": str(bundle_dir.resolve()),
        },
        "training_config": dict(job_spec["training_config"]),
        "peft_config": dict(job_spec["peft_config"]),
    }
    if dataset_limit is not None:
        payload["dataset"]["limit"] = dataset_limit
    return payload


def normalize_model_name_for_leap(model_id: str) -> str:
    if model_id.startswith("LiquidAI/"):
        return model_id.split("/", 1)[1]
    return model_id


def parse_bool_arg(value: str) -> bool:
    return value.strip().lower() not in {"0", "false", "no", "off"}


def write_yaml(path: Path, payload: dict[str, object]) -> None:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PyYAML missing inside HF job") from exc
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def clone_leap_finetune(*, workspace: Path, repo_url: str, ref: str) -> Path:
    repo_dir = workspace / "leap-finetune"
    subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(repo_dir)],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_dir), "checkout", ref],
        check=True,
    )
    return repo_dir


def sanitize_leap_repo_for_hf_jobs(*, repo_dir: Path) -> None:
    pyproject_path = repo_dir / "pyproject.toml"
    pyproject = pyproject_path.read_text(encoding="utf-8")
    sanitized = pyproject
    for dependency_name in ("flash-attn", "deepspeed"):
        sanitized = re.sub(
            rf'^\s*"{re.escape(dependency_name)}>=.*\n',
            "",
            sanitized,
            flags=re.MULTILINE,
        )
    if sanitized != pyproject:
        pyproject_path.write_text(sanitized, encoding="utf-8")
        print("hf_job_dependency_sanitized=1", flush=True)
    lockfile = repo_dir / "uv.lock"
    if lockfile.exists():
        lockfile.unlink()
        print("uv_lock_removed=1", flush=True)
    patch_text_file(
        path=repo_dir / "src" / "leap_finetune" / "utils" / "logging_utils.py",
        before="except ImportError:",
        after="except Exception:",
        log_token="deepspeed_import_guard_widened=1",
    )
    patch_text_file(
        path=repo_dir / "src" / "leap_finetune" / "training_configs" / "vlm_sft_config.py",
        before='    "deepspeed": DEEPSPEED_CONFIG,\n',
        after="",
        log_token="vlm_deepspeed_removed=1",
    )
    patch_text_file(
        path=repo_dir / "src" / "leap_finetune" / "utils" / "checkpoint_callback.py",
        before="from ray import train\n",
        after="from ray import train\nfrom ray.train import Checkpoint\n",
        log_token="ray_checkpoint_import_added=1",
    )
    patch_text_file(
        path=repo_dir / "src" / "leap_finetune" / "utils" / "checkpoint_callback.py",
        before="    ) -> None:\n        if train.get_context().get_world_rank() == 0:\n",
        after=(
            "    ) -> None:\n"
            "        checkpoint_path = None\n"
            "        if train.get_context().get_world_rank() == 0:\n"
        ),
        log_token="ray_checkpoint_path_init_added=1",
    )
    patch_text_file(
        path=repo_dir / "src" / "leap_finetune" / "utils" / "checkpoint_callback.py",
        before=(
            "        # Report metrics only — HF Trainer already saved checkpoint to output_dir.\n"
            "        # Passing checkpoint=None avoids Ray duplicating files into ray_logs/.\n"
            "        train.report(metrics=report_metrics, checkpoint=None)\n"
        ),
        after=(
            "        checkpoint = None\n"
            "        if checkpoint_path and pathlib.Path(checkpoint_path).exists():\n"
            "            checkpoint = Checkpoint.from_directory(checkpoint_path)\n"
            "        train.report(metrics=report_metrics, checkpoint=checkpoint)\n"
        ),
        log_token="ray_checkpoint_reporting_enabled=1",
    )


def patch_text_file(*, path: Path, before: str, after: str, log_token: str) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    patched = text.replace(before, after)
    if patched != text:
        path.write_text(patched, encoding="utf-8")
        print(log_token, flush=True)


def maybe_publish_adapter_artifacts(
    *,
    workspace: Path,
    output_dir: Path,
    repo_id: str | None,
    private: bool,
    base_model_id: str,
    run_name: str,
) -> None:
    if not repo_id:
        return
    checkpoint_dir = find_latest_checkpoint_dir(output_dir)
    publish_dir = workspace / "publish_adapter"
    publish_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for filename in ADAPTER_PUBLISH_FILES:
        source = checkpoint_dir / filename
        if not source.exists():
            continue
        copy2(source, publish_dir / filename)
        copied += 1
    if copied == 0:
        raise FileNotFoundError(f"no adapter files found in checkpoint dir: {checkpoint_dir}")
    validate_published_adapter_dir(publish_dir=publish_dir, checkpoint_dir=checkpoint_dir)
    readme_path = publish_dir / "README.md"
    readme_path.write_text(
        build_adapter_model_card(
            repo_id=repo_id,
            base_model_id=base_model_id,
            run_name=run_name,
            checkpoint_dir=checkpoint_dir,
        ),
        encoding="utf-8",
    )
    manifest_path = publish_dir / "training_output_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "run_name": run_name,
                "base_model_id": base_model_id,
                "adapter_repo_id": repo_id,
                "checkpoint_name": checkpoint_dir.name,
                "source_output_dir": str(output_dir),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    token = os.environ.get("HF_TOKEN")
    api = HfApi(token=token)
    print(f"adapter_publish_repo_id={repo_id}", flush=True)
    try:
        api.create_repo(repo_id=repo_id, repo_type="model", private=private, exist_ok=True)
        api.upload_folder(
            repo_id=repo_id,
            repo_type="model",
            folder_path=str(publish_dir),
            token=token,
            commit_message=f"Upload Blackline adapter artifacts for {run_name}",
        )
    except Exception as exc:
        print("adapter_publish_failed=1", flush=True)
        print(f"adapter_publish_error={type(exc).__name__}", flush=True)
        raise RuntimeError(f"failed to publish adapter artifacts to {repo_id}") from exc
    print(f"published_adapter_repo_id={repo_id}", flush=True)
    print(f"published_adapter_checkpoint={checkpoint_dir}", flush=True)


def validate_published_adapter_dir(*, publish_dir: Path, checkpoint_dir: Path) -> None:
    missing_required = [
        filename for filename in ADAPTER_REQUIRED_FILES if not (publish_dir / filename).exists()
    ]
    if missing_required:
        raise FileNotFoundError(
            "adapter checkpoint missing required files: "
            f"{', '.join(missing_required)} in {checkpoint_dir}"
        )
    if not any((publish_dir / filename).exists() for filename in ADAPTER_WEIGHT_FILES):
        raise FileNotFoundError(f"adapter checkpoint missing weights in {checkpoint_dir}")


def find_latest_checkpoint_dir(output_dir: Path) -> Path:
    if not output_dir.exists():
        raise FileNotFoundError(f"training output dir missing or empty: {output_dir}")
    checkpoint_dirs = sorted(
        [path for path in output_dir.rglob("checkpoint*") if path.is_dir()],
        key=lambda path: (checkpoint_sort_key(path), path.stat().st_mtime),
        reverse=True,
    )
    if checkpoint_dirs:
        return checkpoint_dirs[0]
    # Fallback: any directory containing adapter_config.json
    adapter_dirs = sorted(
        [path.parent for path in output_dir.rglob("adapter_config.json") if path.parent.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if adapter_dirs:
        return adapter_dirs[0]
    raise FileNotFoundError(f"no checkpoint directories found under {output_dir}")


def checkpoint_sort_key(path: Path) -> int:
    match = re.search(r"(\d+)$", path.name)
    if not match:
        return -1
    return int(match.group(1))


def build_adapter_model_card(
    *,
    repo_id: str,
    base_model_id: str,
    run_name: str,
    checkpoint_dir: Path,
) -> str:
    return "\n".join(
        [
            "---",
            "library_name: peft",
            f"base_model: {base_model_id}",
            "tags:",
            "- blackline-atlas",
            "- peft",
            "- lora",
            "---",
            "",
            f"# {repo_id}",
            "",
            f"PEFT adapter artifacts for `{run_name}`.",
            "",
            f"- Base model: `{base_model_id}`",
            f"- Source checkpoint: `{checkpoint_dir.name}`",
            "",
        ]
    )


def run_leap_train(*, repo_dir: Path, config_path: Path, output_dir: str) -> None:
    try:
        run_leap_train_entrypoint(repo_dir=repo_dir, config_path=config_path, output_dir=output_dir)
    except subprocess.CalledProcessError:
        print("entrypoint_failed=1 source_fallback=1", flush=True)
        run_leap_train_source_fallback(
            repo_dir=repo_dir,
            config_path=config_path,
            output_dir=output_dir,
        )


def run_leap_train_entrypoint(*, repo_dir: Path, config_path: Path, output_dir: str) -> None:
    env = os.environ.copy()
    env["OUTPUT_DIR"] = output_dir
    subprocess.run(
        ["uv", "run", "--directory", str(repo_dir), "leap-finetune", str(config_path)],
        check=True,
        env=env,
    )


def run_leap_train_source_fallback(*, repo_dir: Path, config_path: Path, output_dir: str) -> None:
    env = os.environ.copy()
    env["OUTPUT_DIR"] = output_dir
    env["PYTHONPATH"] = str((repo_dir / "src").resolve())
    subprocess.run(
        [
            "uv",
            "run",
            "--directory",
            str(repo_dir),
            "python",
            "-c",
            "from leap_finetune import main; main()",
            str(config_path),
        ],
        check=True,
        env=env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
