from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.annotated_case import AnnotatedCaseRecord  # noqa: E402


def test_train_01_pack_rows_parse() -> None:
    dataset_path = ROOT / "training" / "replay_pack" / "train_01.jsonl"
    rows = [
        AnnotatedCaseRecord.model_validate(json.loads(line))
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert [row.case_id for row in rows] == [
        "morandi_bridge_collapse_train_20180601_20180929",
        "morandi_bridge_collapse_train_20180701_20180919",
        "morandi_bridge_collapse_train_20180701_20181128",
        "kakhovka_dam_breach_train_20220730_20230730",
        "kakhovka_dam_breach_train_20220730_20231031",
    ]
    assert all(row.split == "train" for row in rows)
    assert all(row.holdout_reason is None for row in rows)
    assert all(row.annotation_source == "manual_public_satellite_train_variant" for row in rows)
    assert all(not row.hero for row in rows)
