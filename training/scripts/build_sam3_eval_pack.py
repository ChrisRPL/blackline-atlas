from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.annotated_case import AnnotatedCaseRecord  # noqa: E402
from app.schemas.sam3_eval import Sam3EvalCase  # noqa: E402
from app.schemas.simsat_capture import SimSatCaptureRecord  # noqa: E402
from app.services.sam3_evidence import (  # noqa: E402
    FixtureSam3EvidenceBackend,
    Sam3EvidenceService,
    prompts_for_asset,
)

DEFAULT_INPUT_DATASET = ROOT / "training" / "replay_pack" / "non_demo_eval.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "training" / "replay_pack"
DEFAULT_DATASET_NAME = "sam3_eval_pack.jsonl"
DEFAULT_MANIFEST_NAME = "sam3_eval_manifest.json"
PACK_VERSION = "sam3-eval-v2"


def build_sam3_eval_pack(
    *,
    input_dataset: Path = DEFAULT_INPUT_DATASET,
    capture_manifest: Path | None = None,
    require_images: bool = False,
    max_cases: int | None = None,
) -> dict[str, Any]:
    cases = _load_cases(input_dataset)
    rows = [_build_sam3_case(case, source_dataset=str(input_dataset)) for case in cases]
    if max_cases is not None:
        rows = _balanced_prefix(rows, max_cases=max_cases)
    capture_records = _load_capture_records(capture_manifest)
    if capture_records:
        rows = _apply_capture_records(
            rows,
            capture_records=capture_records,
            require_images=require_images,
        )
    action_counts = _action_counts(rows)
    image_counts = _image_counts(rows)
    return {
        "pack_version": PACK_VERSION,
        "source_dataset": str(input_dataset),
        "capture_manifest": str(capture_manifest) if capture_manifest else None,
        "case_count": len(rows),
        "action_counts": action_counts,
        "image_counts": image_counts,
        "cases": [row.model_dump(mode="json") for row in rows],
    }


def write_sam3_eval_pack(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    input_dataset: Path = DEFAULT_INPUT_DATASET,
    capture_manifest: Path | None = None,
    require_images: bool = False,
    dataset_name: str = DEFAULT_DATASET_NAME,
    manifest_name: str = DEFAULT_MANIFEST_NAME,
    max_cases: int | None = None,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pack = build_sam3_eval_pack(
        input_dataset=input_dataset,
        capture_manifest=capture_manifest,
        require_images=require_images,
        max_cases=max_cases,
    )
    dataset_path = output_dir / dataset_name
    manifest_path = output_dir / manifest_name
    dataset_path.write_text(
        "".join(json.dumps(case, sort_keys=True) + "\n" for case in pack["cases"]),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps({key: value for key, value in pack.items() if key != "cases"}, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path, dataset_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a SAM3/SAM3.1 promptable-concept segmentation eval pack.",
    )
    parser.add_argument("--input-dataset", type=Path, default=DEFAULT_INPUT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--capture-manifest",
        type=Path,
        default=None,
        help="Optional SimSat capture manifest used to replace pending image refs.",
    )
    parser.add_argument(
        "--require-images",
        action="store_true",
        help="Fail if any SAM3 eval case is missing a current/baseline captured image.",
    )
    parser.add_argument("--dataset-name", default=DEFAULT_DATASET_NAME)
    parser.add_argument("--manifest-name", default=DEFAULT_MANIFEST_NAME)
    parser.add_argument("--max-cases", type=int, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest_path, dataset_path = write_sam3_eval_pack(
        output_dir=args.output_dir,
        input_dataset=args.input_dataset,
        capture_manifest=args.capture_manifest,
        require_images=args.require_images,
        dataset_name=args.dataset_name,
        manifest_name=args.manifest_name,
        max_cases=args.max_cases,
    )
    print(f"wrote {manifest_path}")
    print(f"wrote {dataset_path}")
    return 0


def _load_cases(path: Path) -> list[AnnotatedCaseRecord]:
    cases = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        cases.append(AnnotatedCaseRecord.model_validate(json.loads(line)))
    return cases


def _load_capture_records(path: Path | None) -> dict[str, SimSatCaptureRecord]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_records = payload.get("cases", payload) if isinstance(payload, dict) else payload
    if not isinstance(raw_records, list):
        raise ValueError(f"unsupported capture manifest layout in {path}")
    records = [SimSatCaptureRecord.model_validate(record) for record in raw_records]
    return {record.case_id: record for record in records}


def _apply_capture_records(
    rows: list[Sam3EvalCase],
    *,
    capture_records: dict[str, SimSatCaptureRecord],
    require_images: bool,
) -> list[Sam3EvalCase]:
    materialized = []
    missing = []
    for row in rows:
        record = capture_records.get(row.source_case_id)
        if record is None:
            missing.append(f"{row.source_case_id}: missing capture record")
            materialized.append(row)
            continue
        if not record.current.image_path or not record.baseline.image_path:
            missing.append(f"{row.source_case_id}: missing current/baseline image")
            materialized.append(row)
            continue

        payload = row.model_dump(mode="json")
        payload["current_frame"]["frame"]["image_ref"] = record.current.image_path
        payload["baseline_frame"]["frame"]["image_ref"] = record.baseline.image_path
        payload["current_frame"]["frame"]["source"] = "simsat_capture"
        payload["baseline_frame"]["frame"]["source"] = "simsat_capture"
        materialized.append(Sam3EvalCase.model_validate(payload))

    if require_images and missing:
        preview = "; ".join(missing[:6])
        suffix = "" if len(missing) <= 6 else f"; +{len(missing) - 6} more"
        raise ValueError(f"SAM3 eval pack has missing captured images: {preview}{suffix}")
    return materialized


def _build_sam3_case(
    case: AnnotatedCaseRecord,
    *,
    source_dataset: str,
) -> Sam3EvalCase:
    service = Sam3EvidenceService(
        model_version="facebook/sam3",
        backend=FixtureSam3EvidenceBackend(),
    )
    alert = case.expected_alert if case.expected_action != "discard" else None
    report = service.analyze(
        asset=case.asset,
        current=case.current_frame,
        baseline=case.baseline_frame,
        alert=alert,
    )
    expected_bbox = report.masks[0].bbox_norm if report.masks else None
    return Sam3EvalCase(
        case_id=f"sam3_{case.case_id}",
        source_case_id=case.case_id,
        source_dataset=source_dataset,
        split="eval",
        asset=case.asset,
        current_frame=case.current_frame,
        baseline_frame=case.baseline_frame,
        prompts=prompts_for_asset(case.asset, alert),
        expected_action=case.expected_action,
        expected_visual_evidence_tags=report.visual_evidence_tags,
        expected_bbox_norm=expected_bbox,
        expected_min_iou=0.2 if case.expected_action != "discard" else 0.0,
        hard_negative_reason=(
            case.holdout_reason or "negative_control" if case.expected_action == "discard" else None
        ),
    )


def _balanced_prefix(rows: list[Sam3EvalCase], *, max_cases: int) -> list[Sam3EvalCase]:
    positives = [row for row in rows if row.expected_action != "discard"]
    negatives = [row for row in rows if row.expected_action == "discard"]
    selected: list[Sam3EvalCase] = []
    while len(selected) < max_cases and (positives or negatives):
        if positives:
            selected.append(positives.pop(0))
        if len(selected) >= max_cases:
            break
        if negatives:
            selected.append(negatives.pop(0))
    return selected


def _action_counts(rows: list[Sam3EvalCase]) -> dict[str, int]:
    counts = {"discard": 0, "defer": 0, "downlink_now": 0}
    for row in rows:
        counts[row.expected_action] += 1
    return counts


def _image_counts(rows: list[Sam3EvalCase]) -> dict[str, int]:
    current = sum(
        bool(row.current_frame.frame.image_ref)
        and not row.current_frame.frame.image_ref.startswith("pending://")
        for row in rows
    )
    baseline = sum(
        bool(row.baseline_frame.frame.image_ref)
        and not row.baseline_frame.frame.image_ref.startswith("pending://")
        for row in rows
    )
    pairs = sum(
        bool(row.current_frame.frame.image_ref)
        and bool(row.baseline_frame.frame.image_ref)
        and not row.current_frame.frame.image_ref.startswith("pending://")
        and not row.baseline_frame.frame.image_ref.startswith("pending://")
        for row in rows
    )
    return {"current": current, "baseline": baseline, "pairs": pairs}


if __name__ == "__main__":
    raise SystemExit(main())
