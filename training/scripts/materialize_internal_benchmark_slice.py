from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.annotated_case import AnnotatedCaseRecord  # noqa: E402
from app.schemas.training_corpus import BlacklineCandidateEvalRecord  # noqa: E402
from training.scripts.build_lfm25_vl_corpus import write_lfm25_vl_corpus  # noqa: E402
from training.scripts.capture_simsat_manifest import write_simsat_capture_manifest  # noqa: E402

DEFAULT_ANNOTATED_DATASET = ROOT / "training" / "replay_pack" / "non_demo_eval.jsonl"
DEFAULT_CAPTURE_OVERRIDES = ROOT / "training" / "replay_pack" / "non_demo_capture_overrides.json"
DEFAULT_OUTPUT_DIR = ROOT / "training" / "eval_runs" / "benchmark-inputs" / "internal_non_demo"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize the internal non-demo annotated pack into a benchmark-ready "
            "Blackline candidate-eval slice."
        ),
    )
    parser.add_argument(
        "--annotated-dataset",
        type=Path,
        default=DEFAULT_ANNOTATED_DATASET,
        help=f"Annotated internal dataset. Default: {DEFAULT_ANNOTATED_DATASET}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Materialized benchmark output dir. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--capture-manifest",
        type=Path,
        default=None,
        help="Existing SimSat capture manifest to reuse.",
    )
    parser.add_argument(
        "--historical-endpoint",
        default=None,
        help="SimSat historical endpoint to capture pending refs if no manifest is supplied.",
    )
    parser.add_argument(
        "--capture-overrides",
        type=Path,
        default=DEFAULT_CAPTURE_OVERRIDES,
        help=f"Optional capture overrides JSON. Default: {DEFAULT_CAPTURE_OVERRIDES}",
    )
    return parser.parse_args(argv)


def materialize_internal_benchmark_slice(
    *,
    annotated_dataset_path: Path,
    output_dir: Path,
    capture_manifest_path: Path | None = None,
    historical_endpoint: str | None = None,
    capture_overrides_path: Path | None = DEFAULT_CAPTURE_OVERRIDES,
) -> Path:
    dataset_kind = detect_dataset_kind(annotated_dataset_path)
    if dataset_kind == "candidate_eval":
        if candidate_eval_images_resolve(annotated_dataset_path):
            return annotated_dataset_path
        raise ValueError(
            f"candidate-eval dataset has unresolved image refs: {annotated_dataset_path}"
        )

    if dataset_kind != "annotated":
        raise ValueError(f"unsupported internal benchmark dataset: {annotated_dataset_path}")

    if capture_manifest_path is None:
        if not historical_endpoint:
            raise ValueError(
                "internal benchmark materialization requires "
                "BLACKLINE_INTERNAL_BENCHMARK_CAPTURE_MANIFEST or "
                "BLACKLINE_INTERNAL_BENCHMARK_HISTORICAL_ENDPOINT"
            )
        capture_dir = output_dir / "simsat_capture"
        capture_manifest_path, _ = write_simsat_capture_manifest(
            historical_endpoint,
            capture_dir,
            cases_dataset_path=annotated_dataset_path,
            capture_overrides_path=(
                capture_overrides_path
                if capture_overrides_path and capture_overrides_path.exists()
                else None
            ),
            scenario_ids=(),
        )

    _, candidate_eval_path, _ = write_lfm25_vl_corpus(
        output_dir=output_dir,
        capture_manifest_path=capture_manifest_path,
        replay_dataset_path=annotated_dataset_path,
    )
    return candidate_eval_path


def detect_dataset_kind(dataset_path: Path) -> str:
    for raw_line in dataset_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        try:
            BlacklineCandidateEvalRecord.model_validate(payload)
            return "candidate_eval"
        except Exception:
            pass
        try:
            AnnotatedCaseRecord.model_validate(payload)
            return "annotated"
        except Exception:
            pass
        break
    raise ValueError(f"unrecognized dataset format: {dataset_path}")


def candidate_eval_images_resolve(dataset_path: Path) -> bool:
    dataset_root = dataset_path.parent.resolve()
    for raw_line in dataset_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = BlacklineCandidateEvalRecord.model_validate(json.loads(line))
        if not _image_exists(payload.current_image_path, dataset_root):
            return False
        if not _image_exists(payload.baseline_image_path, dataset_root):
            return False
    return True


def _image_exists(image_path: str, dataset_root: Path) -> bool:
    path = Path(image_path)
    if not path.is_absolute():
        path = dataset_root / path
    return path.is_file()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    candidate_eval_path = materialize_internal_benchmark_slice(
        annotated_dataset_path=args.annotated_dataset,
        output_dir=args.output_dir,
        capture_manifest_path=args.capture_manifest,
        historical_endpoint=args.historical_endpoint,
        capture_overrides_path=args.capture_overrides,
    )
    print(f"wrote {candidate_eval_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
