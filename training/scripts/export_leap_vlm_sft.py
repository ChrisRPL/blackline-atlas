from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.training_corpus import (  # noqa: E402
    BlacklineCandidateEvalRecord,
    LeapVLMSFTRecord,
)
from app.services.vlm_conversation import build_candidate_user_content  # noqa: E402

DEFAULT_INPUT_DATASET = (
    ROOT / "training" / "corpus" / "lfm25-vl-v1" / "blackline_candidate_eval.jsonl"
)
DEFAULT_OUTPUT_DIR = ROOT / "training" / "corpus" / "lfm25-vl-v1" / "leap_vlm_sft"
DEFAULT_TRAIN_NAME = "train.jsonl"
DEFAULT_EVAL_NAME = "eval.jsonl"
DEFAULT_SUMMARY_NAME = "summary.json"


def build_leap_vlm_sft_records(
    *,
    candidate_eval_path: Path = DEFAULT_INPUT_DATASET,
    absolute_image_paths: bool = False,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    rows = _load_candidate_rows(candidate_eval_path)
    dataset_root = candidate_eval_path.parent.resolve()

    train_records: list[dict[str, object]] = []
    eval_records: list[dict[str, object]] = []

    for row in rows:
        record = _build_leap_record(
            row=row,
            dataset_root=dataset_root,
            absolute_image_paths=absolute_image_paths,
        )
        if row.split == "train":
            train_records.append(record.model_dump(mode="json"))
        else:
            eval_records.append(record.model_dump(mode="json"))

    summary = {
        "source_dataset": str(candidate_eval_path),
        "image_root": str(dataset_root),
        "total_records": len(rows),
        "train_records": len(train_records),
        "eval_records": len(eval_records),
        "source_split_counts": _count_source_splits(rows),
        "export_note": (
            "Only source split=train is exported to train.jsonl. "
            "All other source splits stay in eval.jsonl to preserve the frozen gold-eval boundary."
        ),
    }
    return train_records, eval_records, summary


def write_leap_vlm_sft_records(
    *,
    candidate_eval_path: Path = DEFAULT_INPUT_DATASET,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    train_name: str = DEFAULT_TRAIN_NAME,
    eval_name: str = DEFAULT_EVAL_NAME,
    summary_name: str = DEFAULT_SUMMARY_NAME,
    absolute_image_paths: bool = False,
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    train_records, eval_records, summary = build_leap_vlm_sft_records(
        candidate_eval_path=candidate_eval_path,
        absolute_image_paths=absolute_image_paths,
    )

    train_path = output_dir / train_name
    eval_path = output_dir / eval_name
    summary_path = output_dir / summary_name

    train_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in train_records),
        encoding="utf-8",
    )
    eval_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in eval_records),
        encoding="utf-8",
    )
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return train_path, eval_path, summary_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Blackline candidate-eval rows into LEAP-compatible VLM SFT JSONL.",
    )
    parser.add_argument(
        "--candidate-eval-dataset",
        type=Path,
        default=DEFAULT_INPUT_DATASET,
        help=f"Blackline candidate-eval JSONL. Default: {DEFAULT_INPUT_DATASET}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for LEAP SFT files. Default: {DEFAULT_OUTPUT_DIR}",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.candidate_eval_dataset.exists():
        raise SystemExit(f"Missing candidate eval dataset: {args.candidate_eval_dataset}")

    train_path, eval_path, summary_path = write_leap_vlm_sft_records(
        candidate_eval_path=args.candidate_eval_dataset,
        output_dir=args.output_dir,
    )
    print(f"wrote {train_path}")
    print(f"wrote {eval_path}")
    print(f"wrote {summary_path}")
    return 0


def _build_leap_record(
    *,
    row: BlacklineCandidateEvalRecord,
    dataset_root: Path,
    absolute_image_paths: bool,
) -> LeapVLMSFTRecord:
    baseline_path = row.baseline_image_path
    current_path = row.current_image_path
    if absolute_image_paths:
        baseline_path = str((dataset_root / row.baseline_image_path).resolve())
        current_path = str((dataset_root / row.current_image_path).resolve())
    target_split = "train" if row.split == "train" else "eval"
    return LeapVLMSFTRecord(
        record_id=f"{row.case_id}__candidate_sft",
        case_id=row.case_id,
        asset_id=row.asset.asset_id,
        source_split=row.split,
        target_split=target_split,
        messages=[
            {
                "role": "system",
                "content": [{"type": "text", "text": row.prompt["system"]}],
            },
            {
                "role": "user",
                "content": build_candidate_user_content(
                    prompt_text=row.prompt["user"],
                    current_image=current_path,
                    baseline_image=baseline_path,
                ),
            },
            {
                "role": "assistant",
                "content": [{"type": "text", "text": row.model_output_text}],
            },
        ],
    )


def _count_source_splits(rows: list[BlacklineCandidateEvalRecord]) -> dict[str, int]:
    counts: dict[str, int] = {
        "train": 0,
        "dev": 0,
        "holdout_geo": 0,
        "holdout_stress": 0,
    }
    for row in rows:
        counts[row.split] += 1
    return counts


def _load_candidate_rows(path: Path) -> list[BlacklineCandidateEvalRecord]:
    return [
        BlacklineCandidateEvalRecord.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


if __name__ == "__main__":
    raise SystemExit(main())
