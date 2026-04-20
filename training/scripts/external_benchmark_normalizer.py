from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from shutil import copy2

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.alert import Alert, AlertCandidate, AlertSource  # noqa: E402
from app.schemas.asset import Asset  # noqa: E402
from app.schemas.frame import FrameEnvelope, FrameRecord  # noqa: E402
from app.schemas.metrics import Metrics  # noqa: E402
from app.schemas.training_corpus import (  # noqa: E402
    BlacklineCandidateEvalRecord,
    CorpusSplit,
    SimSatCorpusFrameSidecar,
    SimSatCorpusSidecar,
)
from app.services.prompt_builder import CandidatePromptBuilder  # noqa: E402

DEFAULT_EXTERNAL_MODEL_VERSION = "external-benchmark-normalized"


def write_external_candidate_eval_slice(
    *,
    records: list[BlacklineCandidateEvalRecord],
    output_dir: Path,
    dataset_name: str = "blackline_candidate_eval.jsonl",
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    materialized = [
        _materialize_record_images(record=record, output_dir=output_dir) for record in records
    ]
    dataset_path = output_dir / dataset_name
    dataset_path.write_text(
        "".join(
            json.dumps(row.model_dump(mode="json"), sort_keys=True) + "\n" for row in materialized
        ),
        encoding="utf-8",
    )
    return dataset_path


def build_candidate_eval_record(
    *,
    benchmark_source: str,
    benchmark_case_id: str,
    case_id: str,
    split: CorpusSplit,
    asset: Asset,
    current_image_path: str,
    baseline_image_path: str,
    current_captured_at: str,
    baseline_captured_at: str,
    current_frame_id: str,
    baseline_frame_id: str,
    expected_candidate: AlertCandidate,
    holdout_reason: str | None = None,
    annotation_source: str | None = None,
    current_source: str | None = None,
    baseline_source: str | None = None,
    current_cloud_cover: float | None = None,
    baseline_cloud_cover: float | None = None,
    model_version: str = DEFAULT_EXTERNAL_MODEL_VERSION,
) -> BlacklineCandidateEvalRecord:
    baseline = FrameEnvelope(
        frame=FrameRecord(
            frame_id=baseline_frame_id,
            asset_id=asset.asset_id,
            captured_at=baseline_captured_at,
            image_ref=current_or_absolute(baseline_image_path),
            cloud_cover=baseline_cloud_cover,
            source=baseline_source or benchmark_source,
        )
    )
    current = FrameEnvelope(
        frame=FrameRecord(
            frame_id=current_frame_id,
            asset_id=asset.asset_id,
            captured_at=current_captured_at,
            image_ref=current_or_absolute(current_image_path),
            cloud_cover=current_cloud_cover,
            source=current_source or benchmark_source,
        ),
        baseline_frame_id=baseline_frame_id,
    )
    prompt = CandidatePromptBuilder().build(asset=asset, current=current, baseline=baseline)
    expected_alert = Alert(
        alert_id=f"ext_{slugify(benchmark_source)}_{slugify(case_id)}",
        timestamp=current_captured_at,
        asset_id=asset.asset_id,
        asset_name=asset.asset_name,
        asset_type=asset.asset_type,
        event_type=expected_candidate.event_type,
        severity=expected_candidate.severity,
        confidence=expected_candidate.confidence,
        bbox=expected_candidate.bbox,
        civilian_impact=expected_candidate.civilian_impact,
        why=expected_candidate.why,
        action=expected_candidate.action,
        source=AlertSource(
            current_frame_id=current_frame_id,
            baseline_frame_id=baseline_frame_id,
            model_version=model_version,
        ),
    )
    return BlacklineCandidateEvalRecord(
        case_id=case_id,
        split=split,
        benchmark_source=benchmark_source,
        benchmark_case_id=benchmark_case_id,
        asset=asset,
        current_image_path=current.frame.image_ref or "",
        baseline_image_path=baseline.frame.image_ref or "",
        prompt={"system": prompt.system, "user": prompt.user},
        model_output_text=json.dumps(
            expected_candidate.model_dump(mode="json"),
            separators=(",", ":"),
        ),
        expected_candidate=expected_candidate,
        expected_action=expected_candidate.action,
        expected_alert=expected_alert,
        expected_metrics=default_metrics_for_action(expected_candidate.action),
        simsat=SimSatCorpusSidecar(
            current=SimSatCorpusFrameSidecar(
                requested_timestamp=current_captured_at,
                request_url=current.frame.image_ref or "",
                image_available=True,
                datetime=current_captured_at,
                cloud_cover=current_cloud_cover,
                spectral_bands=[],
            ),
            baseline=SimSatCorpusFrameSidecar(
                requested_timestamp=baseline_captured_at,
                request_url=baseline.frame.image_ref or "",
                image_available=True,
                datetime=baseline_captured_at,
                cloud_cover=baseline_cloud_cover,
                spectral_bands=[],
            ),
        ),
    ).model_copy(
        update={
            "expected_alert": expected_alert,
            "expected_metrics": default_metrics_for_action(expected_candidate.action),
        }
    )


def default_metrics_for_action(action: str) -> Metrics:
    alerts_emitted = 1 if action == "downlink_now" else 0
    frames_scanned = 48
    raw_frames_suppressed = frames_scanned - alerts_emitted
    downlink_rate = alerts_emitted / frames_scanned
    return Metrics(
        frames_scanned=frames_scanned,
        alerts_emitted=alerts_emitted,
        raw_frames_suppressed=raw_frames_suppressed,
        downlink_rate=round(downlink_rate, 3),
    )


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    return cleaned or "item"


def current_or_absolute(path: str) -> str:
    return str(Path(path).resolve())


def copy_image_into_case_dir(
    *,
    source_path: Path,
    output_dir: Path,
    case_id: str,
    label: str,
) -> str:
    suffix = source_path.suffix or ".png"
    target_dir = output_dir / "images" / case_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{label}{suffix}"
    copy2(source_path, target_path)
    return str(target_path.relative_to(output_dir))


def _materialize_record_images(
    *,
    record: BlacklineCandidateEvalRecord,
    output_dir: Path,
) -> BlacklineCandidateEvalRecord:
    case_id = record.case_id
    current_path = Path(record.current_image_path)
    baseline_path = Path(record.baseline_image_path)
    current_rel = copy_image_into_case_dir(
        source_path=current_path,
        output_dir=output_dir,
        case_id=case_id,
        label="current",
    )
    baseline_rel = copy_image_into_case_dir(
        source_path=baseline_path,
        output_dir=output_dir,
        case_id=case_id,
        label="baseline",
    )
    return record.model_copy(
        update={
            "current_image_path": current_rel,
            "baseline_image_path": baseline_rel,
            "simsat": record.simsat.model_copy(
                update={
                    "current": record.simsat.current.model_copy(
                        update={"request_url": current_rel}
                    ),
                    "baseline": record.simsat.baseline.model_copy(
                        update={"request_url": baseline_rel}
                    ),
                }
            ),
        }
    )
