from __future__ import annotations

import json
from pathlib import Path

from app.schemas.annotated_case import AnnotatedCaseRecord

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REFERENCE_CASES_PATH = ROOT / "training" / "replay_pack" / "non_demo_eval.jsonl"


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
        case = AnnotatedCaseRecord.model_validate(payload)
        cases[case.asset.asset_id] = case
    return cases
