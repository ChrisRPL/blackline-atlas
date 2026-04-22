from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path

from huggingface_hub import hf_hub_download

DEFAULT_LEAP_REPO = "https://github.com/Liquid4All/leap-finetune.git"
DEFAULT_LEAP_REF = "d017458"
DEFAULT_OUTPUT_DIR = "/outputs/blackline-train"


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


def patch_text_file(*, path: Path, before: str, after: str, log_token: str) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    patched = text.replace(before, after)
    if patched != text:
        path.write_text(patched, encoding="utf-8")
        print(log_token, flush=True)


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
