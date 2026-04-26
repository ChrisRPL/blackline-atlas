from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ACTION_KEYS = ("discard", "defer", "downlink_now")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare base and adapter eval summaries and reject adapters that do not "
            "strictly improve frozen Blackline gold behavior."
        )
    )
    parser.add_argument("--base-summary", type=Path, required=True)
    parser.add_argument("--adapter-summary", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument(
        "--allow-equal-positive-recall",
        action="store_true",
        help=(
            "Allow equal downlink_now recall. Default requires strict improvement "
            "when positives exist."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = check_adapter_acceptance(
        base_summary_path=args.base_summary,
        adapter_summary_path=args.adapter_summary,
        allow_equal_positive_recall=args.allow_equal_positive_recall,
    )
    serialized = json.dumps(result, indent=2, sort_keys=True)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(serialized + "\n", encoding="utf-8")
        print(f"wrote {args.output_json}")
    print(serialized)
    return 0 if result["accepted"] else 1


def check_adapter_acceptance(
    *,
    base_summary_path: Path,
    adapter_summary_path: Path,
    allow_equal_positive_recall: bool = False,
) -> dict[str, Any]:
    base = _load_summary(base_summary_path)
    adapter = _load_summary(adapter_summary_path)
    base_stats = _extract_stats(base)
    adapter_stats = _extract_stats(adapter)
    failures: list[str] = []

    if base_stats["total_cases"] <= 0:
        failures.append("base summary has no cases")
    if adapter_stats["total_cases"] <= 0:
        failures.append("adapter summary has no cases")
    if base_stats["total_cases"] != adapter_stats["total_cases"]:
        failures.append("base and adapter summaries must have the same case count")
    if base_stats["expected_action_counts"] != adapter_stats["expected_action_counts"]:
        failures.append("base and adapter summaries must use the same frozen gold dataset")
    if adapter_stats["schema_valid"] < base_stats["schema_valid"]:
        failures.append("adapter schema_valid count regressed")
    if adapter_stats["action_match"] <= base_stats["action_match"]:
        failures.append("adapter action_match count must strictly beat base")
    if adapter_stats["false_positive_count"] > base_stats["false_positive_count"]:
        failures.append("adapter false positives must not exceed base")

    expected_positive = adapter_stats["expected_action_counts"].get("downlink_now", 0)
    if expected_positive > 0:
        if allow_equal_positive_recall:
            if adapter_stats["positive_recall_count"] < base_stats["positive_recall_count"]:
                failures.append("adapter downlink_now recall regressed")
        elif adapter_stats["positive_recall_count"] <= base_stats["positive_recall_count"]:
            failures.append("adapter downlink_now recall must strictly beat base")
        if adapter_stats["predicted_action_counts"].get("downlink_now", 0) == 0:
            failures.append("adapter predicted zero downlink_now rows on a positive gold set")

    return {
        "accepted": not failures,
        "failures": failures,
        "base": base_stats,
        "adapter": adapter_stats,
        "policy": {
            "requires_same_case_count": True,
            "requires_same_expected_actions": True,
            "requires_schema_valid_not_worse": True,
            "requires_action_match_strictly_better": True,
            "requires_false_positive_not_worse": True,
            "requires_downlink_recall_strictly_better": not allow_equal_positive_recall,
        },
    }


def _load_summary(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_stats(summary: dict[str, Any]) -> dict[str, Any]:
    cases = summary.get("cases")
    if not isinstance(cases, list):
        cases = []
    expected_action_counts = _action_counts(summary.get("expected_action_counts"))
    predicted_action_counts = _action_counts(summary.get("predicted_action_counts"))
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    positive_recall_count = sum(
        1
        for case in cases
        if _expected_action(case) == "downlink_now"
        and case.get("predicted_action") == "downlink_now"
    )
    expected_positive_count = expected_action_counts.get("downlink_now", 0)
    return {
        "total_cases": int(summary.get("total_cases") or 0),
        "passed": bool(summary.get("passed")),
        "schema_valid": int(metrics.get("schema_valid") or 0),
        "action_match": int(metrics.get("action_match") or 0),
        "false_positive_count": int(metrics.get("false_positive_count") or 0),
        "pass_count": int(metrics.get("pass_count") or 0),
        "positive_recall_count": positive_recall_count,
        "positive_recall_rate": (
            positive_recall_count / expected_positive_count if expected_positive_count else None
        ),
        "expected_action_counts": expected_action_counts,
        "predicted_action_counts": predicted_action_counts,
    }


def _action_counts(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {key: 0 for key in ACTION_KEYS}
    return {key: int(value.get(key) or 0) for key in ACTION_KEYS}


def _expected_action(case: object) -> str | None:
    if not isinstance(case, dict):
        return None
    for error in case.get("errors", []):
        if isinstance(error, str) and error.startswith("action mismatch: expected "):
            expected = error.removeprefix("action mismatch: expected ").split(",", maxsplit=1)[0]
            return expected
    predicted = case.get("predicted_action")
    if case.get("action_match") and isinstance(predicted, str):
        return predicted
    return None


if __name__ == "__main__":
    raise SystemExit(main())
