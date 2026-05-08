from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.sam3_eval import Sam3EvalCase  # noqa: E402
from app.schemas.sam3_evidence import Sam3EvidenceReport  # noqa: E402

DEFAULT_DATASET = ROOT / "training" / "replay_pack" / "sam3_eval_pack.jsonl"
DEFAULT_REPORTS = ROOT / "training" / "eval_runs" / "sam3_eval" / "reports.jsonl"


def evaluate_sam3_reports(
    *,
    dataset_path: Path,
    reports_path: Path,
) -> dict[str, Any]:
    cases = _load_cases(dataset_path)
    reports = _load_reports(reports_path)
    results = []
    for case in cases:
        key = _case_key(case)
        results.append(_evaluate_case(case, reports.get(key)))

    metrics = {
        "schema_valid": sum(result["schema_valid"] for result in results),
        "action_match": sum(result["action_match"] for result in results),
        "tag_match": sum(result["tag_match"] for result in results),
        "bbox_iou_pass": sum(result["bbox_iou_pass"] for result in results),
        "false_positive_count": sum(result["false_positive"] for result in results),
        "missing_reports": sum(result["missing_report"] for result in results),
        "pass_count": sum(result["passed"] for result in results),
    }
    total = len(cases)
    return {
        "passed": total > 0 and metrics["pass_count"] == total,
        "total_cases": total,
        "metrics": metrics,
        "rates": {
            "pass_rate": _safe_rate(metrics["pass_count"], total),
            "action_match_rate": _safe_rate(metrics["action_match"], total),
            "tag_match_rate": _safe_rate(metrics["tag_match"], total),
            "bbox_iou_pass_rate": _safe_rate(metrics["bbox_iou_pass"], total),
        },
        "cases": results,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate SAM3/SAM3.1 evidence reports against Blackline SAM3 eval cases.",
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--reports", type=Path, default=DEFAULT_REPORTS)
    parser.add_argument("--summary-json", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = evaluate_sam3_reports(dataset_path=args.dataset, reports_path=args.reports)
    serialized = json.dumps(summary, indent=2, sort_keys=True)
    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0 if summary["passed"] else 1


def _load_cases(path: Path) -> list[Sam3EvalCase]:
    return [
        Sam3EvalCase.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _load_reports(path: Path) -> dict[str, Sam3EvidenceReport]:
    reports = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        report = Sam3EvidenceReport.model_validate(json.loads(line))
        reports[(report.asset_id, report.current_frame_id)] = report
    return reports


def _evaluate_case(
    case: Sam3EvalCase,
    report: Sam3EvidenceReport | None,
) -> dict[str, Any]:
    result = {
        "case_id": case.case_id,
        "missing_report": report is None,
        "schema_valid": report is not None,
        "action_match": False,
        "tag_match": False,
        "bbox_iou": 0.0,
        "bbox_iou_pass": False,
        "false_positive": False,
        "passed": False,
        "errors": [],
    }
    if report is None:
        result["errors"].append("missing SAM3 report")
        return result

    result["action_match"] = report.triage_action == case.expected_action
    if not result["action_match"]:
        result["errors"].append(
            f"action mismatch: expected {case.expected_action}, got {report.triage_action}"
        )

    expected_tags = set(case.expected_visual_evidence_tags)
    predicted_tags = set(report.visual_evidence_tags)
    result["tag_match"] = not expected_tags or bool(expected_tags.intersection(predicted_tags))
    if not result["tag_match"]:
        result["errors"].append(
            f"tag mismatch: expected one of {sorted(expected_tags)}, got {sorted(predicted_tags)}"
        )

    if case.expected_bbox_norm is None:
        result["bbox_iou_pass"] = not report.masks
    else:
        best_iou = max(
            (_bbox_iou(case.expected_bbox_norm, mask.bbox_norm) for mask in report.masks),
            default=0.0,
        )
        result["bbox_iou"] = round(best_iou, 3)
        result["bbox_iou_pass"] = best_iou >= case.expected_min_iou
        if not result["bbox_iou_pass"]:
            result["errors"].append(
                f"bbox IoU below threshold: {best_iou:.3f} < {case.expected_min_iou:.3f}"
            )

    result["false_positive"] = case.expected_action == "discard" and (
        report.triage_action != "discard" or bool(report.masks)
    )
    if result["false_positive"]:
        result["errors"].append("false positive mask/action on discard case")

    result["passed"] = (
        result["schema_valid"]
        and result["action_match"]
        and result["tag_match"]
        and result["bbox_iou_pass"]
        and not result["false_positive"]
    )
    return result


def _case_key(case: Sam3EvalCase) -> tuple[str, str]:
    return (case.asset.asset_id, case.current_frame.frame.frame_id)


def _bbox_iou(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    x1 = max(first[0], second[0])
    y1 = max(first[1], second[1])
    x2 = min(first[2], second[2])
    y2 = min(first[3], second[3])
    intersection = max(x2 - x1, 0.0) * max(y2 - y1, 0.0)
    first_area = max(first[2] - first[0], 0.0) * max(first[3] - first[1], 0.0)
    second_area = max(second[2] - second[0], 0.0) * max(second[3] - second[1], 0.0)
    union = first_area + second_area - intersection
    return intersection / union if union else 0.0


def _safe_rate(value: int, total: int) -> float:
    return round(value / total, 3) if total else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
