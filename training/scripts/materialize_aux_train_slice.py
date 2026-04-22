from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.training_corpus import BlacklineCandidateEvalRecord  # noqa: E402

DEFAULT_SOURCE_DATASETS = (
    ROOT
    / "training"
    / "external_benchmarks"
    / "xbd_public_seed"
    / "blackline_candidate_eval.jsonl",
    ROOT
    / "training"
    / "external_benchmarks"
    / "spacenet8_public_seed"
    / "blackline_candidate_eval.jsonl",
)
DEFAULT_OUTPUT_DIR = ROOT / "training" / "eval_runs" / "aux-train-inputs" / "aux_public_seed_v0"
DEFAULT_DATASET_NAME = "blackline_candidate_eval.jsonl"
DEFAULT_SUMMARY_NAME = "summary.json"
IMAGE_REF_PATTERN = re.compile(r"^- image_ref: .*$", re.MULTILINE)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize checked-in public external slices into a separate train-only "
            "auxiliary Blackline candidate-eval dataset."
        ),
    )
    parser.add_argument(
        "--source-dataset",
        type=Path,
        action="append",
        dest="source_datasets",
        default=None,
        help="Candidate-eval dataset to include. Repeat for multiple.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Materialized aux-train output dir. Default: {DEFAULT_OUTPUT_DIR}",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    candidate_eval_path, summary_path = materialize_aux_train_slice(
        source_datasets=tuple(args.source_datasets or DEFAULT_SOURCE_DATASETS),
        output_dir=args.output_dir,
    )
    print(f"wrote {candidate_eval_path}")
    print(f"wrote {summary_path}")
    return 0


def materialize_aux_train_slice(
    *,
    source_datasets: tuple[Path, ...],
    output_dir: Path,
    dataset_name: str = DEFAULT_DATASET_NAME,
    summary_name: str = DEFAULT_SUMMARY_NAME,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    if images_dir.exists():
        shutil.rmtree(images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    sources_summary: list[dict[str, object]] = []

    for dataset_path in source_datasets:
        source_rows = _load_candidate_rows(dataset_path)
        source_root = dataset_path.parent.resolve()
        slice_id = dataset_path.parent.name
        source_case_ids: list[str] = []
        benchmark_sources = sorted({row.benchmark_source or "unknown" for row in source_rows})

        for row in source_rows:
            materialized_case_id = f"{slice_id}__{row.case_id}"
            source_case_ids.append(materialized_case_id)
            row_payload = row.model_dump(mode="json")

            baseline_rel = _copy_image(
                source_root=source_root,
                source_path=row.baseline_image_path,
                output_dir=images_dir,
                case_id=materialized_case_id,
                variant="baseline",
            )
            current_rel = _copy_image(
                source_root=source_root,
                source_path=row.current_image_path,
                output_dir=images_dir,
                case_id=materialized_case_id,
                variant="current",
            )

            row_payload["case_id"] = materialized_case_id
            row_payload["split"] = "train"
            row_payload["baseline_image_path"] = baseline_rel
            row_payload["current_image_path"] = current_rel
            row_payload["prompt"]["user"] = rewrite_prompt_user_image_refs(
                row.prompt["user"],
                current_image_ref=current_rel,
                baseline_image_ref=baseline_rel,
            )
            row_payload["simsat"]["baseline"]["request_url"] = baseline_rel
            row_payload["simsat"]["current"]["request_url"] = current_rel
            rows.append(row_payload)

        sources_summary.append(
            {
                "slice_id": slice_id,
                "dataset_path": str(dataset_path),
                "row_count": len(source_rows),
                "benchmark_sources": benchmark_sources,
                "materialized_case_ids": source_case_ids,
            }
        )

    dataset_path = output_dir / dataset_name
    summary_path = output_dir / summary_name
    dataset_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(
            {
                "version": "blackline-aux-train-slice-v1",
                "row_count": len(rows),
                "source_dataset_count": len(source_datasets),
                "source_datasets": sources_summary,
                "split": "train",
                "notes": [
                    "Auxiliary-train only. Keep separate from core Blackline gold metrics.",
                    (
                        "Public seed slices stay useful for transfer widening, "
                        "not for replacing internal eval."
                    ),
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return dataset_path, summary_path


def rewrite_prompt_user_image_refs(
    prompt_user: str,
    *,
    current_image_ref: str,
    baseline_image_ref: str,
) -> str:
    replacements = iter(
        (
            f"- image_ref: {current_image_ref}",
            f"- image_ref: {baseline_image_ref}",
        )
    )

    def replace(match: re.Match[str]) -> str:
        try:
            return next(replacements)
        except StopIteration:
            return match.group(0)

    return IMAGE_REF_PATTERN.sub(replace, prompt_user, count=2)


def _copy_image(
    *,
    source_root: Path,
    source_path: str,
    output_dir: Path,
    case_id: str,
    variant: str,
) -> str:
    source = Path(source_path)
    if not source.is_absolute():
        source = source_root / source
    if not source.exists():
        raise FileNotFoundError(f"missing source image for aux train materialization: {source}")
    suffix = source.suffix or ".png"
    relative = Path("images") / case_id / f"{variant}{suffix}"
    target = output_dir.parent / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return str(relative)


def _load_candidate_rows(dataset_path: Path) -> list[BlacklineCandidateEvalRecord]:
    return [
        BlacklineCandidateEvalRecord.model_validate(json.loads(line))
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


if __name__ == "__main__":
    raise SystemExit(main())
