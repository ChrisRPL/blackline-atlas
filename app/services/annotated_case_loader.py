from __future__ import annotations

import json
from pathlib import Path

from app.schemas.annotated_case import AnnotatedCaseRecord

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REFERENCE_CASES_PATH = ROOT / "training" / "replay_pack" / "non_demo_eval.jsonl"
REFERENCE_IMAGE_ROOTS = (
    ROOT
    / "training"
    / "eval_runs"
    / "lfm25_vl_sft_hf_corpus_full_v1_targeted"
    / "trainer_bundle"
    / "images"
    / "vlm_evidence_sft_simsat_gold_v1",
    ROOT / "training" / "eval_runs" / "sam3_real_capture",
    ROOT
    / "training"
    / "eval_runs"
    / "lfm25_vl_sft_hf_corpus_full_v1"
    / "trainer_bundle"
    / "images"
    / "vlm_evidence_sft_simsat_gold_v1",
    ROOT / "training" / "internal_benchmarks" / "blackline_public_seed" / "images",
)


def load_reference_cases(path: str | Path | None = None) -> dict[str, AnnotatedCaseRecord]:
    dataset_path = Path(path) if path else DEFAULT_REFERENCE_CASES_PATH

    try:
        rows = dataset_path.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, OSError):
        return {}

    cases: dict[str, AnnotatedCaseRecord] = {}
    for raw_line in rows:
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        case = _with_local_image_refs(AnnotatedCaseRecord.model_validate(payload))
        cases[case.asset.asset_id] = case
    return cases


def _with_local_image_refs(case: AnnotatedCaseRecord) -> AnnotatedCaseRecord:
    current_ref = _local_case_image(case.case_id, "current")
    baseline_ref = _local_case_image(case.case_id, "baseline")
    if current_ref is None and baseline_ref is None:
        return case

    current = case.current_frame
    baseline = case.baseline_frame
    if current_ref is not None and _is_pending_ref(current.frame.image_ref):
        current = current.model_copy(
            update={"frame": current.frame.model_copy(update={"image_ref": current_ref})}
        )
    if baseline_ref is not None and _is_pending_ref(baseline.frame.image_ref):
        baseline = baseline.model_copy(
            update={"frame": baseline.frame.model_copy(update={"image_ref": baseline_ref})}
        )
    return case.model_copy(update={"current_frame": current, "baseline_frame": baseline})


def _local_case_image(case_id: str, kind: str) -> str | None:
    filename = f"{kind}.png"
    for root in REFERENCE_IMAGE_ROOTS:
        candidate = root / case_id / filename
        if candidate.is_file() and candidate.stat().st_size > 0:
            return str(candidate.relative_to(ROOT))
    return None


def _is_pending_ref(image_ref: str | None) -> bool:
    return bool(image_ref and image_ref.startswith("pending://"))
