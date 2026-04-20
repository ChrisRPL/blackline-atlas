from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.annotated_case import AnnotatedCaseRecord  # noqa: E402
from app.schemas.training_corpus import (  # noqa: E402
    BlacklineCandidateEvalRecord,
    SimSatCorpusFrameSidecar,
    SimSatCorpusSidecar,
)
from app.services.prompt_builder import CandidatePromptBuilder  # noqa: E402

DEFAULT_CASE_ID = "port_sudan_aid_hub_strikes"
DEFAULT_SOURCE_IMAGE = ROOT / "ui" / "assets" / "blackline-portsudan-comparison.png"
DEFAULT_ANNOTATED_DATASET = ROOT / "training" / "replay_pack" / "non_demo_eval.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "training" / "internal_benchmarks" / "blackline_public_seed"
DEFAULT_DATASET_NAME = "blackline_candidate_eval.jsonl"

# Crops only the imagery panels, excluding the title bar and cloud labels.
BASELINE_CROP = (28, 106, 536, 610)
CURRENT_CROP = (562, 106, 1070, 610)


def load_case(dataset_path: Path, case_id: str) -> AnnotatedCaseRecord:
    for raw_line in dataset_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if payload.get("case_id") != case_id:
            continue
        return AnnotatedCaseRecord.model_validate(payload)
    raise ValueError(f"missing case_id={case_id} in {dataset_path}")


def build_internal_public_seed(
    *,
    annotated_dataset_path: Path = DEFAULT_ANNOTATED_DATASET,
    source_image_path: Path = DEFAULT_SOURCE_IMAGE,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    case_id: str = DEFAULT_CASE_ID,
) -> Path:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Missing Pillow. Install project deps before building the seed."
        ) from exc

    case = load_case(annotated_dataset_path, case_id)
    image_dir = output_dir / "images" / case_id
    image_dir.mkdir(parents=True, exist_ok=True)

    baseline_rel = f"images/{case_id}/baseline.png"
    current_rel = f"images/{case_id}/current.png"
    baseline_path = output_dir / baseline_rel
    current_path = output_dir / current_rel

    with Image.open(source_image_path) as source:
        source.crop(BASELINE_CROP).save(baseline_path)
        source.crop(CURRENT_CROP).save(current_path)

    prompt_builder = CandidatePromptBuilder()
    current_frame = case.current_frame.model_copy(
        update={
            "frame": case.current_frame.frame.model_copy(
                update={"image_ref": str(current_path.resolve())}
            ),
            "overlay_ref": None,
        }
    )
    baseline_frame = case.baseline_frame.model_copy(
        update={
            "frame": case.baseline_frame.frame.model_copy(
                update={"image_ref": str(baseline_path.resolve())}
            ),
            "overlay_ref": None,
        }
    )
    prompt = prompt_builder.build(
        asset=case.asset,
        current=current_frame,
        baseline=baseline_frame,
    )

    record = BlacklineCandidateEvalRecord(
        case_id=case.case_id,
        split=case.split or "holdout_geo",
        benchmark_source="BlacklineInternalPublicSeed",
        benchmark_case_id=case.case_id,
        asset=case.asset,
        current_image_path=current_rel,
        baseline_image_path=baseline_rel,
        prompt={"system": prompt.system, "user": prompt.user},
        model_output_text=case.model_output_text,
        expected_candidate=case.expected_candidate,
        expected_action=case.expected_action,
        expected_alert=case.expected_alert,
        expected_metrics=case.expected_metrics,
        simsat=SimSatCorpusSidecar(
            current=SimSatCorpusFrameSidecar(
                requested_timestamp=case.current_frame.frame.captured_at,
                request_url=source_image_path.as_posix(),
                image_available=True,
                datetime=case.current_frame.frame.captured_at,
                cloud_cover=case.current_frame.frame.cloud_cover,
                footprint=[],
                spectral_bands=["red", "green", "blue"],
                size_km=None,
                window_seconds=None,
            ),
            baseline=SimSatCorpusFrameSidecar(
                requested_timestamp=case.baseline_frame.frame.captured_at,
                request_url=source_image_path.as_posix(),
                image_available=True,
                datetime=case.baseline_frame.frame.captured_at,
                cloud_cover=case.baseline_frame.frame.cloud_cover,
                footprint=[],
                spectral_bands=["red", "green", "blue"],
                size_km=None,
                window_seconds=None,
            ),
        ),
    )

    dataset_path = output_dir / DEFAULT_DATASET_NAME
    dataset_path.write_text(
        json.dumps(record.model_dump(mode="json"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return dataset_path


def main() -> int:
    dataset_path = build_internal_public_seed()
    print(f"wrote {dataset_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
