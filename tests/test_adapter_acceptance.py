from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts.check_adapter_acceptance import check_adapter_acceptance  # noqa: E402


def test_adapter_acceptance_requires_action_and_positive_recall_gain(tmp_path: Path) -> None:
    base_path = tmp_path / "base.json"
    adapter_path = tmp_path / "adapter.json"
    base_path.write_text(json.dumps(_summary(correct_positive_count=0)) + "\n", encoding="utf-8")
    adapter_path.write_text(
        json.dumps(_summary(correct_positive_count=1)) + "\n",
        encoding="utf-8",
    )

    result = check_adapter_acceptance(
        base_summary_path=base_path,
        adapter_summary_path=adapter_path,
    )

    assert result["accepted"] is True
    assert result["adapter"]["action_match"] == 3
    assert result["adapter"]["positive_recall_count"] == 1


def test_adapter_acceptance_rejects_all_discard_adapter(tmp_path: Path) -> None:
    base_path = tmp_path / "base.json"
    adapter_path = tmp_path / "adapter.json"
    base_path.write_text(json.dumps(_summary(correct_positive_count=0)) + "\n", encoding="utf-8")
    adapter_path.write_text(
        json.dumps(_summary(correct_positive_count=0)) + "\n",
        encoding="utf-8",
    )

    result = check_adapter_acceptance(
        base_summary_path=base_path,
        adapter_summary_path=adapter_path,
    )

    assert result["accepted"] is False
    assert "adapter action_match count must strictly beat base" in result["failures"]
    assert "adapter downlink_now recall must strictly beat base" in result["failures"]
    assert "adapter predicted zero downlink_now rows on a positive gold set" in result["failures"]


def test_adapter_acceptance_rejects_evidence_tag_regression(tmp_path: Path) -> None:
    base_path = tmp_path / "base.json"
    adapter_path = tmp_path / "adapter.json"
    base = _summary(correct_positive_count=1)
    adapter = _summary(correct_positive_count=2)
    base["evidence_case_count"] = 4
    adapter["evidence_case_count"] = 4
    base["metrics"]["evidence_schema_valid"] = 4
    adapter["metrics"]["evidence_schema_valid"] = 4
    base["metrics"]["evidence_tags_match"] = 4
    adapter["metrics"]["evidence_tags_match"] = 3
    base_path.write_text(json.dumps(base) + "\n", encoding="utf-8")
    adapter_path.write_text(json.dumps(adapter) + "\n", encoding="utf-8")

    result = check_adapter_acceptance(
        base_summary_path=base_path,
        adapter_summary_path=adapter_path,
    )

    assert result["accepted"] is False
    assert "adapter evidence_tags_match count regressed" in result["failures"]


def _summary(*, correct_positive_count: int) -> dict[str, object]:
    cases = [
        _case("discard", "discard", action_match=True),
        _case("discard", "discard", action_match=True),
        _case(
            "downlink_now",
            "downlink_now" if correct_positive_count >= 1 else "discard",
            action_match=correct_positive_count >= 1,
        ),
        _case(
            "downlink_now",
            "downlink_now" if correct_positive_count >= 2 else "discard",
            action_match=correct_positive_count >= 2,
        ),
    ]
    action_match = sum(1 for case in cases if case["action_match"])
    predicted_downlink = sum(1 for case in cases if case["predicted_action"] == "downlink_now")
    return {
        "passed": False,
        "total_cases": 4,
        "metrics": {
            "schema_valid": 4,
            "action_match": action_match,
            "false_positive_count": 0,
            "pass_count": action_match,
        },
        "expected_action_counts": {
            "discard": 2,
            "defer": 0,
            "downlink_now": 2,
        },
        "predicted_action_counts": {
            "discard": 4 - predicted_downlink,
            "defer": 0,
            "downlink_now": predicted_downlink,
        },
        "cases": cases,
    }


def _case(expected: str, predicted: str, *, action_match: bool) -> dict[str, object]:
    errors = []
    if not action_match:
        errors.append(f"action mismatch: expected {expected}, got {predicted}")
    return {
        "case_id": f"{expected}_{predicted}_{len(errors)}",
        "action_match": action_match,
        "predicted_action": predicted,
        "errors": errors,
    }
