from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pydantic import ValidationError  # noqa: E402

from app.schemas.alert import Alert, AlertCandidate  # noqa: E402
from app.schemas.evidence_candidate import (  # noqa: E402
    EVIDENCE_FIRST_KEYS,
    EvidenceFirstCandidate,
    is_evidence_first_payload,
)
from app.schemas.metrics import Metrics  # noqa: E402
from app.services.candidate_guardrails import normalize_candidate_payload  # noqa: E402
from training.scripts.build_dataset import (  # noqa: E402
    DEFAULT_DATASET_NAME,
    DEFAULT_OUTPUT_DIR,
)

DEFAULT_DATASET_PATH = DEFAULT_OUTPUT_DIR / DEFAULT_DATASET_NAME
ACTION_KEYS = ("discard", "defer", "downlink_now")
PREDICTION_FIELDS = set(AlertCandidate.model_fields) | EVIDENCE_FIRST_KEYS
CORE_MATCH_FIELDS = (
    "event_type",
    "severity",
    "civilian_impact",
)


def evaluate_dataset(
    dataset_path: Path,
    *,
    predictions_path: Path | None = None,
) -> dict[str, Any]:
    cases = _load_cases(dataset_path)
    predictions = _load_predictions(predictions_path, cases=cases)
    expected_actions = Counter(case["expected_action"] for case in cases)
    predicted_actions: Counter[str] = Counter()
    results: list[dict[str, Any]] = []

    for case in cases:
        result = _evaluate_case(case, predictions.get(case["case_id"]))
        results.append(result)
        if result["predicted_action"] in ACTION_KEYS:
            predicted_actions[result["predicted_action"]] += 1

    total_cases = len(cases)
    metrics = {
        "dataset_metrics_valid": sum(result["dataset_metrics_valid"] for result in results),
        "json_valid": sum(result["json_valid"] for result in results),
        "schema_valid": sum(result["schema_valid"] for result in results),
        "evidence_schema_valid": sum(result["evidence_schema_valid"] for result in results),
        "evidence_tags_match": sum(result["evidence_tags_match"] for result in results),
        "bbox_valid": sum(result["bbox_valid"] for result in results),
        "core_fields_match": sum(result["core_fields_match"] for result in results),
        "action_match": sum(result["action_match"] for result in results),
        "false_positive_count": sum(result["false_positive"] for result in results),
        "missing_predictions": sum(result["missing_prediction"] for result in results),
        "pass_count": sum(result["passed"] for result in results),
    }

    summary = {
        "passed": total_cases > 0
        and metrics["pass_count"] == total_cases
        and metrics["missing_predictions"] == 0,
        "total_cases": total_cases,
        "metrics": metrics,
        "rates": {
            "pass_rate": _safe_rate(metrics["pass_count"], total_cases),
            "json_valid_rate": _safe_rate(metrics["json_valid"], total_cases),
            "schema_valid_rate": _safe_rate(metrics["schema_valid"], total_cases),
            "evidence_schema_valid_rate": _safe_rate(
                metrics["evidence_schema_valid"],
                _evidence_case_count(results),
            ),
            "evidence_tags_match_rate": _safe_rate(
                metrics["evidence_tags_match"],
                _evidence_case_count(results),
            ),
            "bbox_valid_rate": _safe_rate(metrics["bbox_valid"], total_cases),
            "core_fields_match_rate": _safe_rate(metrics["core_fields_match"], total_cases),
            "action_match_rate": _safe_rate(metrics["action_match"], total_cases),
        },
        "expected_action_counts": _fill_action_counts(expected_actions),
        "predicted_action_counts": _fill_action_counts(predicted_actions),
        "evidence_case_count": _evidence_case_count(results),
        "cases": results,
    }
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline structured-output eval for Blackline Atlas replay cases.",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help=f"Replay dataset path (.json or .jsonl). Default: {DEFAULT_DATASET_PATH}",
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        default=None,
        help="Predictions JSONL/JSON. If omitted, uses expected alerts for a self-check.",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        default=None,
        help="Optional path for the summary JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = evaluate_dataset(args.dataset, predictions_path=args.predictions)
    serialized = json.dumps(summary, indent=2, sort_keys=True)
    if args.summary_json is not None:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0 if summary["passed"] else 1


def _evaluate_case(case: dict[str, Any], prediction_entry: dict[str, Any] | None) -> dict[str, Any]:
    errors: list[str] = []
    expected_candidate = case["expected_candidate"]
    expected_action = case["expected_action"]
    expected_evidence = case.get("expected_evidence_candidate")
    dataset_metrics_valid = True

    try:
        Metrics.model_validate(case["expected_metrics"])
    except ValidationError as exc:
        dataset_metrics_valid = False
        errors.append(f"invalid expected_metrics: {exc.errors()[0]['msg']}")

    result = {
        "case_id": case["case_id"],
        "passed": False,
        "missing_prediction": prediction_entry is None,
        "dataset_metrics_valid": dataset_metrics_valid,
        "json_valid": False,
        "schema_valid": False,
        "evidence_required": expected_evidence is not None,
        "evidence_schema_valid": False,
        "evidence_tags_match": False,
        "bbox_valid": False,
        "core_fields_match": False,
        "action_match": False,
        "false_positive": False,
        "predicted_action": None,
        "errors": errors,
    }

    if prediction_entry is None:
        result["errors"].append("missing prediction")
        return result

    payload, json_error = _extract_prediction_payload(prediction_entry)
    if json_error is not None:
        result["errors"].append(json_error)
        return result

    result["json_valid"] = True
    normalized_payload = normalize_candidate_payload(payload)

    if is_evidence_first_payload(payload):
        try:
            evidence = EvidenceFirstCandidate.model_validate(payload)
            result["evidence_schema_valid"] = True
            if expected_evidence is not None:
                evidence_mismatches = _collect_evidence_field_mismatches(
                    expected_evidence,
                    evidence.model_dump(mode="json"),
                )
                result["evidence_tags_match"] = not evidence_mismatches
                if evidence_mismatches:
                    result["errors"].append(
                        "evidence mismatch: " + ", ".join(evidence_mismatches),
                    )
        except ValidationError as exc:
            result["errors"].append(f"evidence schema validation failed: {exc.errors()[0]['msg']}")

    _repair_safe_discard_payload(normalized_payload)

    try:
        candidate = AlertCandidate.model_validate(normalized_payload)
    except ValidationError as exc:
        result["errors"].append(f"schema validation failed: {exc.errors()[0]['msg']}")
        return result

    result["schema_valid"] = True
    result["predicted_action"] = candidate.action
    result["bbox_valid"] = _bbox_is_valid(candidate.bbox)
    if not result["bbox_valid"]:
        result["errors"].append("bbox invalid: expected normalized x1< x2 and y1 < y2")

    predicted_candidate = candidate.model_dump(mode="json")
    mismatches = _collect_core_field_mismatches(expected_candidate, predicted_candidate)
    result["core_fields_match"] = not mismatches
    if mismatches:
        result["errors"].append(
            "core field mismatch: " + ", ".join(mismatches),
        )

    result["action_match"] = candidate.action == expected_action
    if not result["action_match"]:
        result["errors"].append(
            f"action mismatch: expected {expected_action}, got {candidate.action}",
        )

    result["false_positive"] = (
        expected_action != "downlink_now" and candidate.action == "downlink_now"
    )
    result["passed"] = (
        result["dataset_metrics_valid"]
        and result["json_valid"]
        and result["schema_valid"]
        and (not result["evidence_required"] or result["evidence_schema_valid"])
        and (not result["evidence_required"] or result["evidence_tags_match"])
        and result["bbox_valid"]
        and result["core_fields_match"]
        and result["action_match"]
    )
    return result


def _load_cases(dataset_path: Path) -> list[dict[str, Any]]:
    entries = _load_json_records(dataset_path)
    cases = []
    for entry in entries:
        required_keys = (
            "model_output_text",
            "expected_candidate",
            "expected_alert",
            "expected_action",
            "expected_metrics",
        )
        if any(key not in entry for key in required_keys):
            raise ValueError(f"dataset case missing required fields: {entry}")
        case = dict(entry)
        case["model_output_text"] = str(entry["model_output_text"])
        case["expected_candidate"] = AlertCandidate.model_validate(
            entry["expected_candidate"],
        ).model_dump(mode="json")
        case["expected_alert"] = Alert.model_validate(
            entry["expected_alert"],
        ).model_dump(mode="json")
        case["expected_action"] = str(entry["expected_action"])
        case["expected_metrics"] = Metrics.model_validate(
            entry["expected_metrics"],
        ).model_dump(mode="json")
        if "expected_evidence_candidate" in entry:
            case["expected_evidence_candidate"] = EvidenceFirstCandidate.model_validate(
                entry["expected_evidence_candidate"],
            ).model_dump(mode="json")
        cases.append(case)
    return cases


def _load_predictions(
    predictions_path: Path | None,
    *,
    cases: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    if predictions_path is None:
        return {
            case["case_id"]: {
                "case_id": case["case_id"],
                "raw_output": case["model_output_text"],
            }
            for case in cases
        }

    prediction_map: dict[str, dict[str, Any]] = {}
    for entry in _load_json_records(predictions_path):
        case_id = entry.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"prediction missing case_id: {entry}")
        prediction_map[case_id] = entry
    return prediction_map


def _load_json_records(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in raw.splitlines() if line.strip()]

    payload = json.loads(raw)
    if isinstance(payload, dict) and isinstance(payload.get("cases"), list):
        return list(payload["cases"])
    if isinstance(payload, list):
        return payload
    raise ValueError(f"unsupported record layout in {path}")


def _extract_prediction_payload(entry: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    if "raw_output" in entry:
        raw_output = entry["raw_output"]
        if not isinstance(raw_output, str):
            return None, "raw_output must be a JSON string"
        return _extract_raw_output_payload(raw_output)

    for key in ("output", "prediction", "predicted_alert", "alert", "candidate"):
        if key in entry:
            payload = _unwrap_prediction_payload(entry[key])
            if isinstance(payload, dict):
                return payload, None
            return None, f"{key} must be an object"

    inferred = {key: value for key, value in entry.items() if key in PREDICTION_FIELDS}
    if inferred:
        return inferred, None
    return None, "prediction missing output payload"


def _extract_raw_output_payload(raw_output: str) -> tuple[dict[str, Any] | None, str | None]:
    parse_errors: list[str] = []
    for blob in _prediction_json_blobs(raw_output):
        try:
            payload = _unwrap_prediction_payload(json.loads(blob))
        except json.JSONDecodeError as exc:
            parse_errors.append(exc.msg)
            continue
        if isinstance(payload, dict):
            return payload, None
        return None, "raw_output must decode to an object"
    if parse_errors:
        return None, f"json parse failed: {parse_errors[0]}"
    return None, "raw_output must decode to an object"


def _prediction_json_blobs(raw_output: str) -> list[str]:
    text = raw_output.strip()
    if not text:
        return []

    blobs = [text]
    fenced = _strip_json_fence(text)
    if fenced != text:
        blobs.append(fenced)

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
        excerpt = text[first_brace : last_brace + 1]
        if excerpt not in blobs:
            blobs.append(excerpt)
    return blobs


def _strip_json_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _unwrap_prediction_payload(payload: object) -> object:
    if isinstance(payload, list) and len(payload) == 1 and isinstance(payload[0], dict):
        return payload[0]
    return payload


def _repair_safe_discard_payload(payload: dict[str, Any]) -> None:
    if payload.get("action") != "discard":
        return
    payload.setdefault("event_type", "no_event")
    payload.setdefault("severity", "low")
    payload.setdefault("confidence", 0.0)
    payload.setdefault("bbox", [0.0, 0.0, 1.0, 1.0])
    payload.setdefault("civilian_impact", "no_material_impact")
    payload.setdefault("why", "Model returned discard with insufficient disruption evidence.")


def _bbox_is_valid(bbox: tuple[float, float, float, float]) -> bool:
    x1, y1, x2, y2 = bbox
    return all(0.0 <= value <= 1.0 for value in bbox) and x1 < x2 and y1 < y2


def _collect_core_field_mismatches(
    expected_alert: dict[str, Any],
    predicted_alert: dict[str, Any],
) -> list[str]:
    mismatches = []
    for field in CORE_MATCH_FIELDS:
        if predicted_alert[field] != expected_alert[field]:
            mismatches.append(
                f"{field} expected {expected_alert[field]!r} got {predicted_alert[field]!r}",
            )
    return mismatches


def _collect_evidence_field_mismatches(
    expected: dict[str, Any],
    predicted: dict[str, Any],
) -> list[str]:
    fields = (
        "visual_evidence_tags",
        "evidence_strength",
        "damage_mechanism",
        "visibility_quality",
        "negative_type",
        "bbox_quality",
        "triage_action",
    )
    mismatches = []
    for field in fields:
        if predicted[field] != expected[field]:
            mismatches.append(f"{field} expected {expected[field]!r} got {predicted[field]!r}")
    return mismatches


def _fill_action_counts(counter: Counter[str]) -> dict[str, int]:
    return {action: counter.get(action, 0) for action in ACTION_KEYS}


def _evidence_case_count(results: list[dict[str, Any]]) -> int:
    return sum(result["evidence_required"] for result in results)


def _safe_rate(value: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(value / total, 3)


if __name__ == "__main__":
    raise SystemExit(main())
