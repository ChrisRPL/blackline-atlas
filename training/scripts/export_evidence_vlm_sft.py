from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.evidence_candidate import EvidenceFirstCandidate  # noqa: E402
from app.schemas.training_corpus import LeapVLMSFTRecord  # noqa: E402
from app.schemas.training_run import TrainAdapterDatasetManifest  # noqa: E402

DEFAULT_SOURCE_ROOT = ROOT / "work" / "dataset_v21" / "satellite-disruption-triage-aux-v2-1"
DEFAULT_OUTPUT_DIR = ROOT / "training" / "corpus" / "lfm25-vl-train-01-aux-v8"
DEFAULT_RUN_NAME = "lfm25_vl_sft_train_hf_aux_v8"
DEFAULT_REPLAY_DATASET = ROOT / "training" / "replay_pack" / "train_01.jsonl"
DEFAULT_SOURCE_DATASET_ID = "ChrisRPL/satellite-disruption-triage-aux-v2-1"
DEFAULT_VERSION_LABEL = "satellite-disruption-triage-aux-v2.1"
EVIDENCE_KEYS = (
    "visual_evidence_tags",
    "evidence_strength",
    "damage_mechanism",
    "visibility_quality",
    "negative_type",
    "bbox_norm",
    "bbox_quality",
    "change_confidence",
    "civilian_infrastructure_type",
    "rationale",
    "triage_action",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export satellite-disruption-triage evidence-first rows into "
            "LEAP-compatible VLM SFT files plus a Blackline dataset manifest."
        )
    )
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-name", default=DEFAULT_RUN_NAME)
    parser.add_argument("--replay-dataset", type=Path, default=DEFAULT_REPLAY_DATASET)
    parser.add_argument("--train-file", default="train_flat.jsonl")
    parser.add_argument("--eval-file", default="eval_flat.jsonl")
    parser.add_argument("--calibration-file", default="eval_calibration_flat.jsonl")
    parser.add_argument("--source-dataset-id", default=DEFAULT_SOURCE_DATASET_ID)
    parser.add_argument("--version-label", default=DEFAULT_VERSION_LABEL)
    parser.add_argument(
        "--max-eval-cases",
        type=int,
        default=24,
        help="Max eval cases recorded in the dataset manifest.",
    )
    parser.add_argument(
        "--save-full-predictions",
        action="store_true",
        help="Record that downstream eval should retain full predictions.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_root = args.source_root.resolve()
    output_dir = args.output_dir.resolve()
    leap_dir = output_dir / "leap_vlm_sft"
    support_dir = output_dir / "corpus"
    leap_dir.mkdir(parents=True, exist_ok=True)
    support_dir.mkdir(parents=True, exist_ok=True)

    train_rows = _load_and_validate_rows(source_root=source_root, filename=args.train_file)
    eval_rows = _load_and_validate_rows(source_root=source_root, filename=args.eval_file)
    calibration_rows = _load_and_validate_rows(
        source_root=source_root,
        filename=args.calibration_file,
        required=False,
    )

    train_records = [_build_record(row=row, source_split="train") for row in train_rows]
    eval_records = [_build_record(row=row, source_split="dev") for row in eval_rows]

    train_path = leap_dir / "train.jsonl"
    eval_path = leap_dir / "eval.jsonl"
    calibration_path = leap_dir / "eval_calibration.jsonl"
    summary_path = leap_dir / "summary.json"
    manifest_path = leap_dir / "dataset_manifest.json"
    empty_grounding_path = support_dir / "liquid_grounding.jsonl"
    empty_candidate_eval_path = support_dir / "blackline_candidate_eval.jsonl"
    splits_path = support_dir / "splits.json"

    _write_jsonl(train_path, [record.model_dump(mode="json") for record in train_records])
    _write_jsonl(eval_path, [record.model_dump(mode="json") for record in eval_records])
    _write_jsonl(
        calibration_path,
        [
            _build_record(row=row, source_split="dev").model_dump(mode="json")
            for row in calibration_rows
        ],
    )
    empty_grounding_path.write_text("", encoding="utf-8")
    empty_candidate_eval_path.write_text("", encoding="utf-8")
    splits_path.write_text(
        json.dumps(
            {
                "version": "evidence-vlm-sft-v1",
                "policy": (
                    f"{args.version_label} event-held-out train/eval; "
                    "calibration retained separately"
                ),
                "split_counts": {"train": len(train_rows), "dev": len(eval_rows)},
                "cases": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = _build_summary(
        source_root=source_root,
        source_dataset_id=args.source_dataset_id,
        version_label=args.version_label,
        train_file=args.train_file,
        eval_file=args.eval_file,
        calibration_file=args.calibration_file,
        train_rows=train_rows,
        eval_rows=eval_rows,
        calibration_rows=calibration_rows,
    )
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest = TrainAdapterDatasetManifest(
        version="blackline-evidence-vlm-sft-v1",
        run_name=args.run_name,
        purpose=(
            "Evidence-first diagnostic SFT for civilian conflict-disruption triage "
            f"using {args.version_label}."
        ),
        model_id="LiquidAI/LFM2.5-VL-450M",
        task_kind="candidate_json_sft",
        source_replay_dataset=str(args.replay_dataset.resolve()),
        source_aux_candidate_eval_datasets=[args.source_dataset_id, str(source_root)],
        capture_manifest=str(source_root / "metadata.json"),
        liquid_grounding_dataset=str(empty_grounding_path),
        source_internal_candidate_eval_dataset=str(empty_candidate_eval_path),
        candidate_eval_dataset=str(source_root / args.train_file),
        splits_manifest=str(splits_path),
        image_root=str(source_root),
        leap_train_dataset=str(train_path),
        leap_eval_dataset=str(eval_path),
        leap_summary=str(summary_path),
        source_split_counts={
            "train": len(train_rows),
            "dev": len(eval_rows),
            "holdout_geo": 0,
            "holdout_stress": 0,
        },
        eval_mode="smoke",
        benchmark_on_start=True,
        max_eval_cases=args.max_eval_cases,
        save_full_predictions=args.save_full_predictions,
        execution_environment="hf_jobs",
        output_dir="/outputs/blackline-train",
        hf_flavor="l4x1",
        hf_timeout="8h",
    )
    manifest_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"train_records={len(train_records)}")
    print(f"eval_records={len(eval_records)}")
    print(f"calibration_records={len(calibration_rows)}")
    print(f"dataset_manifest={manifest_path}")
    return 0


def _load_and_validate_rows(
    *,
    source_root: Path,
    filename: str,
    required: bool = True,
) -> list[dict[str, Any]]:
    path = source_root / filename
    if not path.exists():
        if required:
            raise FileNotFoundError(f"missing evidence split: {path}")
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    for row in rows:
        EvidenceFirstCandidate.model_validate(row)
        for image_key in ("baseline_image", "current_image"):
            image_path = source_root / str(row[image_key])
            if not image_path.exists():
                raise FileNotFoundError(f"missing referenced image: {image_path}")
    return rows


def _build_record(*, row: dict[str, Any], source_split: str) -> LeapVLMSFTRecord:
    target_split = "train" if source_split == "train" else "eval"
    return LeapVLMSFTRecord(
        record_id=f"{row['row_id']}__evidence_sft",
        case_id=str(row["row_id"]),
        asset_id=f"satdis_{row['row_id']}",
        source_split=source_split,
        target_split=target_split,
        messages=[
            {
                "role": "system",
                "content": [{"type": "text", "text": _system_prompt()}],
            },
            {
                "role": "user",
                "content": _user_content(row),
            },
            {
                "role": "assistant",
                "content": [{"type": "text", "text": _assistant_json(row)}],
            },
        ],
    )


def _system_prompt() -> str:
    return (
        "You are Blackline Atlas evidence-first satellite disruption triage. "
        "Compare a baseline and current satellite image for macro-visible civilian "
        "infrastructure disruption only. Return one strict JSON object. Do not provide "
        "tactical targeting, strike support, route intelligence, or military asset ranking."
    )


def _user_content(row: dict[str, Any]) -> list[dict[str, str]]:
    date_window = f"{row.get('baseline_date', 'unknown')} to {row.get('current_date', 'unknown')}"
    prompt = "\n".join(
        [
            "Task: compare two satellite images.",
            "Image 1 is the baseline/pre-event image.",
            "Image 2 is the current/post-event image.",
            "Return visual evidence fields first and triage_action last.",
            f"Location: {row['location_name']}, {row['country']}",
            f"Event: {row['source_event']}",
            f"Date window: {date_window}",
            f"Modality: {row['modality']}",
            "Visibility quality options include: excellent, good, fair, poor.",
            "Accepted triage_action values: discard, defer, downlink_now.",
        ]
    )
    return [
        {"type": "text", "text": prompt},
        {"type": "image", "image": str(row["baseline_image"])},
        {"type": "image", "image": str(row["current_image"])},
    ]


def _assistant_json(row: dict[str, Any]) -> str:
    payload = {key: row[key] for key in EVIDENCE_KEYS}
    return json.dumps(payload, ensure_ascii=False)


def _build_summary(
    *,
    source_root: Path,
    source_dataset_id: str,
    version_label: str,
    train_file: str,
    eval_file: str,
    calibration_file: str,
    train_rows: list[dict[str, Any]],
    eval_rows: list[dict[str, Any]],
    calibration_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    all_rows = train_rows + eval_rows
    return {
        "version": f"{version_label}-evidence-vlm-sft",
        "source_dataset_id": source_dataset_id,
        "source_dataset": str(source_root),
        "image_root": str(source_root),
        "source_files": {
            "train": train_file,
            "eval": eval_file,
            "calibration": calibration_file,
        },
        "total_records": len(all_rows),
        "train_records": len(train_rows),
        "eval_records": len(eval_rows),
        "calibration_records": len(calibration_rows),
        "source_split_counts": {
            "train": len(train_rows),
            "dev": len(eval_rows),
            "holdout_geo": 0,
            "holdout_stress": 0,
        },
        "action_counts": dict(Counter(str(row["triage_action"]) for row in all_rows)),
        "modality_counts": dict(Counter(str(row["modality"]) for row in all_rows)),
        "event_counts": dict(Counter(str(row["source_event"]) for row in all_rows)),
        "export_note": (
            f"Evidence-first {version_label} rows are exported directly to LEAP VLM SFT. "
            "Calibration/eval-gold rows are retained separately and are not mixed into train.jsonl."
        ),
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
