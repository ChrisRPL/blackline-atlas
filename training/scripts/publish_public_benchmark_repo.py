from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from huggingface_hub import HfApi, get_token, whoami

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.model_benchmark import BenchmarkManifest, BenchmarkSliceConfig  # noqa: E402

DEFAULT_MANIFEST = ROOT / "training" / "replay_pack" / "model_benchmark_manifest.json"
DEFAULT_OUTPUT_DIR = ROOT / "training" / "eval_runs" / "public_benchmark_repo"
DEFAULT_REPO_SUFFIX = "blackline-atlas-benchmark-seeds"
DEFAULT_PUBLIC_SLICE_IDS = (
    "internal_public_seed_v0",
    "xbd_public_seed_v0",
    "spacenet8_public_seed_v0",
)
SLICE_KEEP_FILES = ("blackline_candidate_eval.jsonl",)
SLICE_KEEP_DIRS = ("images", "source_labels")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Assemble a clean public-facing HF dataset repo from the ready Blackline "
            "benchmark seed slices, and optionally publish it."
        ),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"Benchmark manifest path. Default: {DEFAULT_MANIFEST}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Local assembled repo dir. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--slice-id",
        action="append",
        default=None,
        help="Optional explicit public slice ids to include.",
    )
    parser.add_argument(
        "--repo-id",
        default=None,
        help="Optional HF dataset repo id. Default: derived from HF username.",
    )
    parser.add_argument(
        "--public",
        action="store_true",
        help="Create/publish the HF dataset repo as public.",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Actually upload the assembled repo to Hugging Face.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    selected_slice_ids = tuple(args.slice_id or DEFAULT_PUBLIC_SLICE_IDS)
    manifest = load_manifest(args.manifest)
    slices = resolve_public_seed_slices(manifest=manifest, slice_ids=selected_slice_ids)
    materialized = materialize_public_benchmark_repo(
        output_dir=args.output_dir,
        slices=slices,
    )
    print(f"output_dir={materialized}")
    if not args.publish:
        print(f"slice_ids={','.join(selected_slice_ids)}")
        return 0
    token = get_token()
    if not token:
        raise RuntimeError("HF token missing. Run `hf auth login` first.")
    repo_id = args.repo_id or default_public_benchmark_repo_id(token=token)
    publish_public_benchmark_repo(
        output_dir=materialized,
        repo_id=repo_id,
        private=not args.public,
        token=token,
    )
    print(f"repo_id={repo_id}")
    return 0


def load_manifest(path: Path) -> BenchmarkManifest:
    return BenchmarkManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))


def resolve_public_seed_slices(
    *,
    manifest: BenchmarkManifest,
    slice_ids: tuple[str, ...],
) -> list[BenchmarkSliceConfig]:
    wanted = set(slice_ids)
    selected = [slice_config for slice_config in manifest.slices if slice_config.slice_id in wanted]
    missing = wanted - {slice_config.slice_id for slice_config in selected}
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"missing benchmark slices: {missing_text}")
    for slice_config in selected:
        if slice_config.status != "ready":
            raise ValueError(f"slice is not ready: {slice_config.slice_id}")
        if not slice_config.dataset_path:
            raise ValueError(f"slice missing dataset_path: {slice_config.slice_id}")
    return selected


def materialize_public_benchmark_repo(
    *,
    output_dir: Path,
    slices: list[BenchmarkSliceConfig],
) -> Path:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_payload: dict[str, object] = {
        "version": "2026-04-22",
        "title": "Blackline Atlas Public Benchmark Seeds",
        "slices": [],
    }
    for slice_config in slices:
        source_dir = resolve_slice_source_dir(slice_config)
        target_dir = output_dir / slice_config.slice_id
        target_dir.mkdir(parents=True, exist_ok=True)
        for filename in SLICE_KEEP_FILES:
            source = source_dir / filename
            if source.exists():
                shutil.copy2(source, target_dir / filename)
        for dirname in SLICE_KEEP_DIRS:
            source = source_dir / dirname
            if source.exists():
                shutil.copytree(source, target_dir / dirname)
        manifest_payload["slices"].append(
            build_public_slice_manifest_entry(
                slice_config=slice_config,
                source_dir=source_dir,
            )
        )

    (output_dir / "README.md").write_text(
        build_public_benchmark_dataset_card(slices=slices),
        encoding="utf-8",
    )
    (output_dir / "benchmark_manifest.json").write_text(
        json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_dir


def resolve_slice_source_dir(slice_config: BenchmarkSliceConfig) -> Path:
    dataset_path = ROOT / str(slice_config.dataset_path)
    source_dir = dataset_path.parent
    if not source_dir.exists():
        raise FileNotFoundError(f"slice source dir missing: {source_dir}")
    return source_dir


def build_public_slice_manifest_entry(
    *,
    slice_config: BenchmarkSliceConfig,
    source_dir: Path,
) -> dict[str, object]:
    dataset_path = source_dir / "blackline_candidate_eval.jsonl"
    row_count = sum(
        1 for line in dataset_path.read_text(encoding="utf-8").splitlines() if line.strip()
    )
    return {
        "slice_id": slice_config.slice_id,
        "title": slice_config.title,
        "tier": slice_config.tier,
        "rows": row_count,
        "source_label": slice_config.source_label,
        "source_url": slice_config.source_url,
        "notes": slice_config.notes,
    }


def build_public_benchmark_dataset_card(*, slices: list[BenchmarkSliceConfig]) -> str:
    slice_lines = []
    for slice_config in slices:
        source_dir = resolve_slice_source_dir(slice_config)
        row_count = sum(
            1
            for line in (source_dir / "blackline_candidate_eval.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        )
        slice_lines.append(
            (
                f"- `{slice_config.slice_id}`: {slice_config.title}"
                + (f" ({slice_config.source_label})" if slice_config.source_label else "")
                + f", `{row_count}` rows"
            )
        )
    return "\n".join(
        [
            "---",
            "pretty_name: Blackline Atlas Civilian Disruption Benchmark Seeds",
            "language:",
            "- en",
            "license: other",
            "task_categories:",
            "- image-to-text",
            "task_ids:",
            "- visual-question-answering",
            "tags:",
            "- benchmark",
            "- remote-sensing",
            "- satellite-imagery",
            "- structured-outputs",
            "- humanitarian",
            "- disaster-response",
            "- civilian-infrastructure",
            "- damage-assessment",
            "- blackline-atlas",
            "size_categories:",
            "- n<1K",
            "---",
            "",
            "# Blackline Atlas Civilian Disruption Benchmark Seeds",
            "",
            "Small public benchmark slices for structured civilian disruption triage.",
            "",
            "Purpose:",
            "- compare prompt baselines and small VLMs on the same runnable public slices",
            "- regression-check structured JSON behavior before and after Blackline adaptation",
            "- provide a public-facing benchmark artifact without exposing the internal gold set",
            "",
            "Included slices:",
            *slice_lines,
            "",
            "What this repo is:",
            "- public benchmark-only seed material",
            "- canonical `blackline_candidate_eval.jsonl` rows plus copied image pairs",
            "- external transfer checks for disaster and flood disruption",
            "",
            "What this repo is not:",
            "- not the internal Blackline training corpus",
            "- not the frozen Blackline gold eval set",
            "- not a live conflict feed or operational monitoring service",
            "",
            "Layout:",
            "- `<slice_id>/blackline_candidate_eval.jsonl`: canonical runnable benchmark rows",
            "- `<slice_id>/images/...`: image pairs used by the slice",
            "- `<slice_id>/source_labels/...`: public provenance files when available",
            "",
            "Intended use:",
            "- benchmark and demo material",
            "- cross-model comparison on a shared public slice basket",
            "- public reproducibility for a narrow part of the evaluation stack",
            "",
            "Limitations:",
            "- intentionally small seed slices",
            "- external-only coverage, not full civilian lifeline taxonomy coverage",
            "- mixed-source public artifacts; source terms apply per slice",
            "- not a replacement for the full internal Blackline evaluation program",
            "",
            "Licensing and provenance:",
            "- each slice keeps its original public provenance files when available",
            (
                "- source terms and restrictions follow the original datasets "
                "and published artifacts referenced per slice"
            ),
            "",
        ]
    )


def default_public_benchmark_repo_id(*, token: str) -> str:
    payload = whoami(token=token)
    username = payload.get("name") or payload.get("fullname")
    if not username:
        raise RuntimeError("failed to resolve HF username for public benchmark repo")
    return f"{username}/{DEFAULT_REPO_SUFFIX}"


def publish_public_benchmark_repo(
    *,
    output_dir: Path,
    repo_id: str,
    private: bool,
    token: str,
) -> None:
    api = HfApi(token=token)
    api.create_repo(repo_id=repo_id, repo_type="dataset", private=private, exist_ok=True)
    api.upload_folder(
        repo_id=repo_id,
        repo_type="dataset",
        folder_path=str(output_dir),
        token=token,
        commit_message="Publish Blackline public benchmark seeds",
    )


if __name__ == "__main__":
    raise SystemExit(main())
