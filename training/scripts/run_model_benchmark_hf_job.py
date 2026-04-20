from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

DEFAULT_REPO_URL = "https://github.com/ChrisRPL/blackline-atlas.git"
DEFAULT_REF = "main"
DEFAULT_MANIFEST = "training/replay_pack/model_benchmark_manifest.json"
DEFAULT_OUTPUT_DIR = "/outputs/model-benchmark"
DEFAULT_EXTRAS = "dev,vlm"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Blackline model benchmark on Hugging Face Jobs with a local "
            "transformers model, using the checked-in benchmark runner."
        )
    )
    parser.add_argument(
        "--repo-url",
        default=os.getenv("BLACKLINE_BENCHMARK_REPO_URL", DEFAULT_REPO_URL),
        help=f"HTTPS GitHub repo URL. Default: {DEFAULT_REPO_URL}",
    )
    parser.add_argument(
        "--ref",
        default=os.getenv("BLACKLINE_BENCHMARK_REF", DEFAULT_REF),
        help=f"Git ref, tag, or commit-ish to archive. Default: {DEFAULT_REF}",
    )
    parser.add_argument(
        "--manifest",
        default=DEFAULT_MANIFEST,
        help=f"Benchmark manifest path inside the repo. Default: {DEFAULT_MANIFEST}",
    )
    parser.add_argument(
        "--model-key",
        required=True,
        help="Manifest model_key to run in local transformers mode.",
    )
    parser.add_argument(
        "--slice-id",
        action="append",
        required=True,
        help="Ready slice id to benchmark. Repeat for multiple slices.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Where benchmark artifacts should land. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional case limit per slice for smoke runs.",
    )
    parser.add_argument(
        "--extras",
        default=DEFAULT_EXTRAS,
        help=f'Editable-install extras to use. Default: "{DEFAULT_EXTRAS}"',
    )
    return parser.parse_args(argv)


def normalize_repo_base(repo_url: str) -> str:
    normalized = repo_url.rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    return normalized


def build_archive_url(repo_url: str, ref: str) -> str:
    base = normalize_repo_base(repo_url)
    return f"{base}/archive/{quote(ref, safe='')}.tar.gz"


def download_repo_snapshot(*, repo_url: str, ref: str, workspace: Path) -> Path:
    archive_url = build_archive_url(repo_url, ref)
    archive_path = workspace / "repo.tar.gz"
    with urlopen(archive_url) as response, archive_path.open("wb") as handle:
        shutil.copyfileobj(response, handle)

    extract_dir = workspace / "repo"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, mode="r:gz") as tar:
        tar.extractall(extract_dir)

    children = [child for child in extract_dir.iterdir() if child.is_dir()]
    if len(children) != 1:
        raise RuntimeError(f"expected exactly one extracted repo dir, found {len(children)}")
    return children[0]


def install_repo(repo_dir: Path, *, extras: str) -> None:
    target = f".[{extras}]" if extras else "."
    run_checked(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-e",
            target,
        ],
        cwd=repo_dir,
    )


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_job_manifest(*, manifest: dict, model_key: str) -> dict:
    found = False
    for model in manifest.get("models", []):
        is_target = model.get("model_key") == model_key
        model["enabled"] = is_target
        if not is_target:
            continue
        found = True
        model["runner_kind"] = "transformers_local"
        model["provider_id"] = None
        model["endpoint_env"] = None
        model["api_key_env"] = None
        notes = model.get("notes") or ""
        suffix = "HF Jobs local transformers fallback."
        if suffix not in notes:
            model["notes"] = (notes + " " + suffix).strip()
    if not found:
        raise RuntimeError(f"model_key not found in manifest: {model_key}")
    return manifest


def write_job_manifest(*, repo_dir: Path, manifest_relpath: str, model_key: str) -> Path:
    manifest_path = repo_dir / manifest_relpath
    manifest = load_manifest(manifest_path)
    patched = build_job_manifest(manifest=manifest, model_key=model_key)
    output_path = repo_dir / "training" / "eval_runs" / "job-benchmark-manifest.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(patched, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def build_benchmark_command(
    *,
    repo_dir: Path,
    manifest_path: Path,
    model_key: str,
    slice_ids: list[str],
    output_dir: str,
    limit: int | None,
) -> list[str]:
    command = [
        sys.executable,
        "training/scripts/run_model_benchmark.py",
        "--manifest",
        str(manifest_path),
        "--model-key",
        model_key,
        "--output-dir",
        output_dir,
    ]
    for slice_id in slice_ids:
        command.extend(["--slice-id", slice_id])
    if limit is not None:
        command.extend(["--limit", str(limit)])
    return command


def run_checked(command: list[str], *, cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="blackline-benchmark-job-") as temp_dir:
        workspace = Path(temp_dir)
        repo_dir = download_repo_snapshot(repo_url=args.repo_url, ref=args.ref, workspace=workspace)
        install_repo(repo_dir, extras=args.extras)
        manifest_path = write_job_manifest(
            repo_dir=repo_dir,
            manifest_relpath=args.manifest,
            model_key=args.model_key,
        )
        command = build_benchmark_command(
            repo_dir=repo_dir,
            manifest_path=manifest_path,
            model_key=args.model_key,
            slice_ids=args.slice_id,
            output_dir=args.output_dir,
            limit=args.limit,
        )
        run_checked(command, cwd=repo_dir)
        print(f"benchmark_output_dir={args.output_dir}")
        print(f"patched_manifest={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
