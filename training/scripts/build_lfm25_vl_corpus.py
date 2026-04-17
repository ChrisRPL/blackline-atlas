from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from shutil import copy2
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.annotated_case import AnnotatedCaseRecord  # noqa: E402
from app.schemas.frame import FrameEnvelope  # noqa: E402
from app.schemas.simsat_capture import SimSatCaptureRecord  # noqa: E402
from app.schemas.training_corpus import (  # noqa: E402
    BlacklineCandidateEvalRecord,
    CorpusSplit,
    CorpusSplitCase,
    CorpusSplits,
    GroundingTarget,
    LiquidGroundingRecord,
    SimSatCorpusFrameSidecar,
    SimSatCorpusSidecar,
)
from app.services.prompt_builder import CandidatePromptBuilder  # noqa: E402

PACK_VERSION = "lfm25-vl-v1"
DEFAULT_CAPTURE_MANIFEST_PATH = (
    ROOT / "training" / "replay_pack" / "simsat_capture" / "simsat_capture_manifest.json"
)
DEFAULT_REPLAY_DATASET_PATH = ROOT / "training" / "replay_pack" / "hero_eval.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "training" / "corpus" / PACK_VERSION
DEFAULT_GROUNDING_DATASET_NAME = "liquid_grounding.jsonl"
DEFAULT_CANDIDATE_EVAL_NAME = "blackline_candidate_eval.jsonl"
DEFAULT_SPLITS_NAME = "splits.json"
SPLIT_POLICY = (
    "Hold out hero/demo AOIs until non-demo SimSat captures exist; "
    "do not train from the 2-case smoke pack."
)
GROUNDING_PROMPT = (
    "Inspect the satellite image and detect the {target}. "
    'Provide result as a valid JSON: [{{"label": str, "bbox": [x1,y1,x2,y2]}}]. '
    "Coordinates must be normalized to 0-1."
)


def build_lfm25_vl_corpus(
    *,
    capture_manifest_path: Path = DEFAULT_CAPTURE_MANIFEST_PATH,
    replay_dataset_path: Path = DEFAULT_REPLAY_DATASET_PATH,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    capture_root = capture_manifest_path.parent.resolve()
    capture_cases = _load_capture_cases(capture_manifest_path)
    replay_cases = _load_replay_cases(replay_dataset_path)

    grounding_records: list[dict[str, object]] = []
    candidate_eval_records: list[dict[str, object]] = []
    split_cases: list[CorpusSplitCase] = []
    split_counts: Counter[str] = Counter()

    for case_id, capture_case in capture_cases.items():
        replay_case = replay_cases.get(case_id)
        if replay_case is None:
            raise ValueError(f"missing replay case for capture case_id={case_id}")

        split, holdout_reason = _assign_split(replay_case)
        split_counts[split] += 1
        split_cases.append(
            CorpusSplitCase(
                case_id=case_id,
                asset_id=capture_case.asset.asset_id,
                aoi_key=capture_case.asset.asset_id,
                requested_date=capture_case.current.requested_timestamp[:10],
                split=split,
                holdout_reason=holdout_reason,
                is_hero=capture_case.asset.hero,
            )
        )

        current_image_path = _relative_capture_image(
            capture_case.current.image_path,
            capture_root=capture_root,
        )
        baseline_image_path = _relative_capture_image(
            capture_case.baseline.image_path,
            capture_root=capture_root,
        )

        if current_image_path is not None:
            grounding_records.append(
                _build_grounding_record(
                    case_id=case_id,
                    split=split,
                    image_path=current_image_path,
                    replay_case=replay_case,
                ).model_dump(mode="json")
            )

        if current_image_path is None or baseline_image_path is None:
            continue

        candidate_eval_records.append(
            _build_candidate_eval_record(
                case_id=case_id,
                split=split,
                current_image_path=current_image_path,
                baseline_image_path=baseline_image_path,
                replay_case=replay_case,
                capture_case=capture_case,
            ).model_dump(mode="json")
        )

    split_manifest = CorpusSplits(
        version=PACK_VERSION,
        policy=SPLIT_POLICY,
        split_counts={
            key: split_counts.get(key, 0)
            for key in ("train", "dev", "holdout_geo", "holdout_stress")
        },
        cases=split_cases,
    ).model_dump(mode="json")

    return grounding_records, candidate_eval_records, split_manifest


def write_lfm25_vl_corpus(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    capture_manifest_path: Path = DEFAULT_CAPTURE_MANIFEST_PATH,
    replay_dataset_path: Path = DEFAULT_REPLAY_DATASET_PATH,
    grounding_name: str = DEFAULT_GROUNDING_DATASET_NAME,
    candidate_eval_name: str = DEFAULT_CANDIDATE_EVAL_NAME,
    splits_name: str = DEFAULT_SPLITS_NAME,
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    grounding_records, candidate_eval_records, split_manifest = build_lfm25_vl_corpus(
        capture_manifest_path=capture_manifest_path,
        replay_dataset_path=replay_dataset_path,
    )
    capture_root = capture_manifest_path.parent.resolve()
    grounding_records, candidate_eval_records = _materialize_corpus_images(
        grounding_records=grounding_records,
        candidate_eval_records=candidate_eval_records,
        capture_root=capture_root,
        output_dir=output_dir,
    )

    grounding_path = output_dir / grounding_name
    candidate_eval_path = output_dir / candidate_eval_name
    splits_path = output_dir / splits_name

    grounding_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in grounding_records),
        encoding="utf-8",
    )
    candidate_eval_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in candidate_eval_records),
        encoding="utf-8",
    )
    splits_path.write_text(
        json.dumps(split_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return grounding_path, candidate_eval_path, splits_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Join frozen SimSat captures with replay labels into LFM2.5-VL corpus files.",
    )
    parser.add_argument(
        "--capture-manifest",
        type=Path,
        default=DEFAULT_CAPTURE_MANIFEST_PATH,
        help=f"Path to the SimSat capture manifest. Default: {DEFAULT_CAPTURE_MANIFEST_PATH}",
    )
    parser.add_argument(
        "--replay-dataset",
        type=Path,
        default=DEFAULT_REPLAY_DATASET_PATH,
        help=f"Path to the replay eval JSONL. Default: {DEFAULT_REPLAY_DATASET_PATH}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for generated corpus files. Default: {DEFAULT_OUTPUT_DIR}",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.capture_manifest.exists():
        raise SystemExit(f"Missing capture manifest: {args.capture_manifest}")
    if not args.replay_dataset.exists():
        raise SystemExit(f"Missing replay dataset: {args.replay_dataset}")
    grounding_path, candidate_eval_path, splits_path = write_lfm25_vl_corpus(
        output_dir=args.output_dir,
        capture_manifest_path=args.capture_manifest,
        replay_dataset_path=args.replay_dataset,
    )
    print(f"wrote {grounding_path}")
    print(f"wrote {candidate_eval_path}")
    print(f"wrote {splits_path}")
    return 0


def _build_grounding_record(
    *,
    case_id: str,
    split: CorpusSplit,
    image_path: str,
    replay_case: AnnotatedCaseRecord,
) -> LiquidGroundingRecord:
    expected_candidate = replay_case.expected_candidate
    task_text = GROUNDING_PROMPT.format(target=expected_candidate.event_type)
    target = GroundingTarget(
        label=expected_candidate.event_type,
        bbox=expected_candidate.bbox,
    )
    assistant_text = json.dumps([target.model_dump(mode="json")], separators=(",", ":"))
    return LiquidGroundingRecord(
        record_id=f"{case_id}__grounding",
        case_id=case_id,
        asset_id=replay_case.asset.asset_id,
        split=split,
        image_path=image_path,
        task_text=task_text,
        targets=[target],
        sidecar_id=case_id,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image_path},
                    {"type": "text", "text": task_text},
                ],
            },
            {
                "role": "assistant",
                "content": [{"type": "text", "text": assistant_text}],
            },
        ],
    )


def _build_candidate_eval_record(
    *,
    case_id: str,
    split: CorpusSplit,
    current_image_path: str,
    baseline_image_path: str,
    replay_case: AnnotatedCaseRecord,
    capture_case: SimSatCaptureRecord,
) -> BlacklineCandidateEvalRecord:
    current_frame = _to_prompt_frame(
        replay_case.current_frame.model_dump(mode="json"),
        image_path=current_image_path,
    )
    baseline_frame = _to_prompt_frame(
        replay_case.baseline_frame.model_dump(mode="json"),
        image_path=baseline_image_path,
    )
    prompt = CandidatePromptBuilder().build(
        asset=replay_case.asset,
        current=current_frame,
        baseline=baseline_frame,
    )
    return BlacklineCandidateEvalRecord(
        case_id=case_id,
        split=split,
        asset=replay_case.asset,
        current_image_path=current_image_path,
        baseline_image_path=baseline_image_path,
        prompt={
            "system": prompt.system,
            "user": prompt.user,
        },
        model_output_text=replay_case.model_output_text,
        expected_candidate=replay_case.expected_candidate,
        expected_action=replay_case.expected_action,
        expected_alert=replay_case.expected_alert,
        expected_metrics=replay_case.expected_metrics,
        simsat=SimSatCorpusSidecar(
            current=_build_frame_sidecar(capture_case.current),
            baseline=_build_frame_sidecar(capture_case.baseline),
        ),
    )


def _build_frame_sidecar(frame: object) -> SimSatCorpusFrameSidecar:
    query = parse_qs(urlparse(frame.request_url).query)
    window_seconds = query.get("window_seconds", [None])[0]
    return SimSatCorpusFrameSidecar(
        requested_timestamp=frame.requested_timestamp,
        request_url=frame.request_url,
        image_available=frame.response_metadata.image_available,
        datetime=frame.response_metadata.datetime,
        cloud_cover=frame.response_metadata.cloud_cover,
        footprint=frame.response_metadata.footprint,
        spectral_bands=frame.response_metadata.spectral_bands,
        size_km=frame.response_metadata.size_km,
        window_seconds=float(window_seconds) if window_seconds is not None else None,
    )


def _to_prompt_frame(frame_payload: object, *, image_path: str) -> FrameEnvelope:
    envelope = FrameEnvelope.model_validate(frame_payload)
    return envelope.model_copy(
        update={
            "frame": envelope.frame.model_copy(update={"image_ref": image_path}),
            "overlay_ref": None,
        }
    )


def _relative_capture_image(
    image_path: str | None,
    *,
    capture_root: Path,
) -> str | None:
    if image_path is None:
        return None
    resolved = Path(image_path).resolve()
    try:
        return resolved.relative_to(capture_root).as_posix()
    except ValueError as exc:
        raise ValueError(f"capture image is outside capture root: {image_path}") from exc


def _materialize_corpus_images(
    *,
    grounding_records: list[dict[str, object]],
    candidate_eval_records: list[dict[str, object]],
    capture_root: Path,
    output_dir: Path,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    image_root = output_dir / "images"
    copied: dict[str, str] = {}

    def copy_relative_path(relative_path: str) -> str:
        cached = copied.get(relative_path)
        if cached is not None:
            return cached

        source = capture_root / relative_path
        destination = image_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        copy2(source, destination)
        materialized = destination.relative_to(output_dir).as_posix()
        copied[relative_path] = materialized
        return materialized

    for record in grounding_records:
        image_path = record.get("image_path")
        if not isinstance(image_path, str):
            continue
        materialized = copy_relative_path(image_path)
        record["image_path"] = materialized
        messages = record.get("messages")
        if not isinstance(messages, list) or not messages:
            continue
        content = messages[0].get("content") if isinstance(messages[0], dict) else None
        if not isinstance(content, list) or not content:
            continue
        first_item = content[0]
        if isinstance(first_item, dict) and first_item.get("type") == "image":
            first_item["image"] = materialized

    for record in candidate_eval_records:
        current_image_path = record.get("current_image_path")
        baseline_image_path = record.get("baseline_image_path")
        if isinstance(current_image_path, str):
            record["current_image_path"] = copy_relative_path(current_image_path)
        if isinstance(baseline_image_path, str):
            record["baseline_image_path"] = copy_relative_path(baseline_image_path)

    return grounding_records, candidate_eval_records


def _assign_split(case: AnnotatedCaseRecord) -> tuple[CorpusSplit, str | None]:
    if case.split is not None:
        return case.split, case.holdout_reason
    if case.asset.asset_id.startswith("demo_") or case.asset.hero:
        return "holdout_geo", "hero_demo"
    return "train", None


def _load_capture_cases(path: Path) -> dict[str, SimSatCaptureRecord]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        entries = payload.get("cases", [])
    elif isinstance(payload, list):
        entries = payload
    else:
        raise ValueError(f"unsupported capture manifest layout in {path}")
    return {
        record.case_id: record
        for record in (SimSatCaptureRecord.model_validate(entry) for entry in entries)
    }


def _load_replay_cases(path: Path) -> dict[str, AnnotatedCaseRecord]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        records = [json.loads(line) for line in raw.splitlines() if line.strip()]
    else:
        payload = json.loads(raw)
        records = payload.get("cases", []) if isinstance(payload, dict) else payload
    return {
        record.case_id: record
        for record in (AnnotatedCaseRecord.model_validate(entry) for entry in records)
    }


if __name__ == "__main__":
    raise SystemExit(main())
