from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.evidence_candidate import EvidenceFirstCandidate  # noqa: E402

DEFAULT_MODEL_ID = "LiquidAI/LFM2.5-VL-450M"
DEFAULT_DATASET_PATH = (
    ROOT / "work" / "dataset_v22" / "satellite-disruption-triage-aux-v2-2" / "eval_gold_sft.jsonl"
)
DEFAULT_OUTPUT_DIR = ROOT / "training" / "eval_runs" / "evidence-vlm-sft-v9-gold"
DEFAULT_MAX_NEW_TOKENS = 384
ACTION_KEYS = ("discard", "defer", "downlink_now")
EVIDENCE_MATCH_FIELDS = (
    "visual_evidence_tags",
    "evidence_strength",
    "damage_mechanism",
    "visibility_quality",
    "negative_type",
    "bbox_quality",
    "triage_action",
)


@dataclass(frozen=True)
class EvidenceSFTCase:
    case_id: str
    baseline_image_path: str
    current_image_path: str
    system_prompt: str
    user_prompt: str
    expected: EvidenceFirstCandidate
    source_event: str | None = None
    location_name: str | None = None


class EvidenceSFTTextGenerator(Protocol):
    def generate(self, case: EvidenceSFTCase) -> str: ...


class TransformersEvidenceSFTRunner:
    def __init__(
        self,
        *,
        model_id: str,
        adapter_ref: str | None = None,
        max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    ) -> None:
        self.model_id = model_id
        self.adapter_ref = adapter_ref
        self.max_new_tokens = max_new_tokens
        self._torch, self._image_open, self._processor, self._model = _load_transformers_runner(
            model_id=model_id,
            adapter_ref=adapter_ref,
        )

    def generate(self, case: EvidenceSFTCase) -> str:
        baseline = self._image_open(case.baseline_image_path)
        current = self._image_open(case.current_image_path)
        conversation = build_liquid_conversation(
            case,
            baseline_image=baseline,
            current_image=current,
        )
        inputs = self._processor.apply_chat_template(
            conversation,
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
            tokenize=True,
        )
        inputs = inputs.to(self._model.device)
        with self._torch.no_grad():
            outputs = self._model.generate(**inputs, max_new_tokens=self.max_new_tokens)
        input_length = inputs["input_ids"].shape[1]
        generated = outputs[:, input_length:]
        return self._processor.batch_decode(generated, skip_special_tokens=True)[0].strip()


def build_liquid_conversation(
    case: EvidenceSFTCase,
    *,
    baseline_image: object,
    current_image: object,
) -> list[dict[str, object]]:
    return [
        {
            "role": "system",
            "content": [{"type": "text", "text": case.system_prompt}],
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": case.user_prompt},
                {"type": "image", "image": baseline_image},
                {"type": "image", "image": current_image},
            ],
        },
    ]


def load_evidence_sft_cases(dataset_path: Path) -> list[EvidenceSFTCase]:
    dataset_root = dataset_path.parent.resolve()
    cases: list[EvidenceSFTCase] = []
    for row in _load_json_records(dataset_path):
        row_id = _row_id(row)
        images = row.get("images")
        if not isinstance(images, list) or len(images) != 2:
            raise ValueError(f"SFT row {row_id} must contain exactly two image paths")
        baseline_image = _resolve_image_path(str(images[0]), dataset_root)
        current_image = _resolve_image_path(str(images[1]), dataset_root)
        if not baseline_image.exists():
            raise FileNotFoundError(f"missing baseline image for {row_id}: {baseline_image}")
        if not current_image.exists():
            raise FileNotFoundError(f"missing current image for {row_id}: {current_image}")

        messages = row.get("messages")
        if not isinstance(messages, list) or len(messages) < 3:
            raise ValueError(f"SFT row {row_id} must contain system/user/assistant messages")
        system_prompt = _message_text(messages[0])
        user_prompt = _message_text(messages[1])
        expected_payload = _assistant_payload(messages[2], row_id=row_id)
        cases.append(
            EvidenceSFTCase(
                case_id=row_id,
                baseline_image_path=str(baseline_image),
                current_image_path=str(current_image),
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                expected=EvidenceFirstCandidate.model_validate(expected_payload),
                source_event=_optional_str(row.get("source_event")),
                location_name=_optional_str(row.get("location_name")),
            )
        )
    return cases


def run_evidence_sft_eval(
    *,
    dataset_path: Path,
    output_dir: Path,
    model_id: str = DEFAULT_MODEL_ID,
    adapter_ref: str | None = None,
    limit: int | None = None,
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    predictions_name: str = "predictions.jsonl",
    summary_name: str = "summary.json",
    generator: EvidenceSFTTextGenerator | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    cases = load_evidence_sft_cases(dataset_path)
    if limit is not None:
        cases = cases[:limit]
    generator = generator or TransformersEvidenceSFTRunner(
        model_id=model_id,
        adapter_ref=adapter_ref,
        max_new_tokens=max_new_tokens,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = output_dir / predictions_name
    summary_path = output_dir / summary_name

    predictions: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for case in cases:
        raw_text = generator.generate(case)
        prediction = {"case_id": case.case_id, "raw_output": raw_text}
        predictions.append(prediction)
        results.append(_evaluate_case(case=case, raw_text=raw_text))

    predictions_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in predictions),
        encoding="utf-8",
    )
    summary = _build_summary(
        cases=cases, results=results, model_id=model_id, adapter_ref=adapter_ref
    )
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return predictions_path, summary_path, summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run evidence-first VLM SFT eval on the v2.2 eval-gold set.",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help=f"Evidence SFT JSONL. Default: {DEFAULT_DATASET_PATH}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for predictions and summary. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--model-id",
        default=DEFAULT_MODEL_ID,
        help=f"Hugging Face model id. Default: {DEFAULT_MODEL_ID}",
    )
    parser.add_argument(
        "--adapter-ref",
        default=None,
        help="Optional PEFT adapter path or Hub repo id to evaluate on top of the base model.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional case limit.")
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=DEFAULT_MAX_NEW_TOKENS,
        help=f"Maximum generation tokens. Default: {DEFAULT_MAX_NEW_TOKENS}",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    predictions_path, summary_path, summary = run_evidence_sft_eval(
        dataset_path=args.dataset,
        output_dir=args.output_dir,
        model_id=args.model_id,
        adapter_ref=args.adapter_ref,
        limit=args.limit,
        max_new_tokens=args.max_new_tokens,
    )
    print(f"wrote {predictions_path}")
    print(f"wrote {summary_path}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


def _evaluate_case(*, case: EvidenceSFTCase, raw_text: str) -> dict[str, Any]:
    expected = case.expected.model_dump(mode="json")
    expected_action = expected["triage_action"]
    errors: list[str] = []
    result: dict[str, Any] = {
        "case_id": case.case_id,
        "passed": False,
        "missing_prediction": raw_text.strip() == "",
        "json_valid": False,
        "schema_valid": False,
        "evidence_required": True,
        "evidence_schema_valid": False,
        "evidence_tags_match": False,
        "bbox_valid": False,
        "action_match": False,
        "false_positive": False,
        "predicted_action": None,
        "errors": errors,
    }
    if result["missing_prediction"]:
        errors.append("missing prediction")
        return result

    payload, json_error = _extract_raw_output_payload(raw_text)
    if json_error is not None:
        errors.append(json_error)
        return result
    result["json_valid"] = True

    try:
        predicted = EvidenceFirstCandidate.model_validate(payload)
    except ValidationError as exc:
        errors.append(f"evidence schema validation failed: {exc.errors()[0]['msg']}")
        return result

    result["schema_valid"] = True
    result["evidence_schema_valid"] = True
    result["bbox_valid"] = True
    predicted_payload = predicted.model_dump(mode="json")
    predicted_action = predicted_payload["triage_action"]
    result["predicted_action"] = predicted_action
    result["evidence_tags_match"] = _evidence_fields_match(expected, predicted_payload)
    if not result["evidence_tags_match"]:
        errors.append(
            "evidence mismatch: " + ", ".join(_evidence_mismatches(expected, predicted_payload))
        )

    result["action_match"] = predicted_action == expected_action
    if not result["action_match"]:
        errors.append(f"action mismatch: expected {expected_action}, got {predicted_action}")
    result["false_positive"] = (
        expected_action != "downlink_now" and predicted_action == "downlink_now"
    )
    result["passed"] = (
        result["json_valid"]
        and result["schema_valid"]
        and result["bbox_valid"]
        and result["action_match"]
    )
    return result


def _build_summary(
    *,
    cases: list[EvidenceSFTCase],
    results: list[dict[str, Any]],
    model_id: str,
    adapter_ref: str | None,
) -> dict[str, Any]:
    expected_actions = Counter(case.expected.triage_action for case in cases)
    predicted_actions = Counter(
        result["predicted_action"]
        for result in results
        if result.get("predicted_action") in ACTION_KEYS
    )
    total_cases = len(cases)
    metrics = {
        "json_valid": sum(result["json_valid"] for result in results),
        "schema_valid": sum(result["schema_valid"] for result in results),
        "evidence_schema_valid": sum(result["evidence_schema_valid"] for result in results),
        "evidence_tags_match": sum(result["evidence_tags_match"] for result in results),
        "bbox_valid": sum(result["bbox_valid"] for result in results),
        "action_match": sum(result["action_match"] for result in results),
        "false_positive_count": sum(result["false_positive"] for result in results),
        "missing_predictions": sum(result["missing_prediction"] for result in results),
        "pass_count": sum(result["passed"] for result in results),
    }
    evidence_case_count = total_cases
    return {
        "passed": total_cases > 0
        and metrics["pass_count"] == total_cases
        and metrics["missing_predictions"] == 0,
        "model_id": model_id,
        "adapter_ref": adapter_ref,
        "total_cases": total_cases,
        "metrics": metrics,
        "rates": {
            "pass_rate": _safe_rate(metrics["pass_count"], total_cases),
            "json_valid_rate": _safe_rate(metrics["json_valid"], total_cases),
            "schema_valid_rate": _safe_rate(metrics["schema_valid"], total_cases),
            "evidence_schema_valid_rate": _safe_rate(
                metrics["evidence_schema_valid"],
                evidence_case_count,
            ),
            "evidence_tags_match_rate": _safe_rate(
                metrics["evidence_tags_match"],
                evidence_case_count,
            ),
            "bbox_valid_rate": _safe_rate(metrics["bbox_valid"], total_cases),
            "action_match_rate": _safe_rate(metrics["action_match"], total_cases),
        },
        "expected_action_counts": _fill_action_counts(expected_actions),
        "predicted_action_counts": _fill_action_counts(predicted_actions),
        "evidence_case_count": evidence_case_count,
        "cases": results,
    }


def _load_json_records(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def _row_id(row: dict[str, Any]) -> str:
    value = row.get("row_id") or row.get("example_id")
    if not isinstance(value, str) or not value:
        raise ValueError(f"SFT row missing row_id/example_id: {row}")
    return value


def _message_text(message: object) -> str:
    if not isinstance(message, dict):
        raise ValueError(f"message must be an object: {message}")
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = [
            str(item["text"])
            for item in content
            if isinstance(item, dict) and item.get("type") == "text" and "text" in item
        ]
        return "\n".join(texts)
    raise ValueError(f"message content must be text or content parts: {message}")


def _assistant_payload(message: object, *, row_id: str) -> dict[str, Any]:
    text = _message_text(message)
    payload, error = _extract_raw_output_payload(text)
    if error is not None:
        raise ValueError(f"assistant payload for {row_id} is not strict JSON: {error}")
    return payload


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


def _evidence_fields_match(expected: dict[str, Any], predicted: dict[str, Any]) -> bool:
    return not _evidence_mismatches(expected, predicted)


def _evidence_mismatches(expected: dict[str, Any], predicted: dict[str, Any]) -> list[str]:
    mismatches = []
    for field in EVIDENCE_MATCH_FIELDS:
        if predicted[field] != expected[field]:
            mismatches.append(f"{field} expected {expected[field]!r} got {predicted[field]!r}")
    return mismatches


def _resolve_image_path(image_path: str, dataset_root: Path) -> Path:
    path = Path(image_path)
    if path.is_absolute():
        return path
    return (dataset_root / path).resolve()


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _fill_action_counts(counter: Counter[str]) -> dict[str, int]:
    return {action: counter.get(action, 0) for action in ACTION_KEYS}


def _safe_rate(value: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(value / total, 3)


def _load_transformers_runner(
    *,
    model_id: str,
    adapter_ref: str | None,
) -> tuple[object, object, object, object]:
    try:
        import torch
        from PIL import Image
        from transformers import AutoModelForImageTextToText, AutoProcessor
    except ImportError as exc:
        raise RuntimeError(
            "Missing local VLM dependencies. Install torch, pillow, and transformers>=5.1."
        ) from exc

    token = os.getenv("HF_TOKEN")
    processor = AutoProcessor.from_pretrained(model_id, token=token)
    model = AutoModelForImageTextToText.from_pretrained(
        model_id,
        token=token,
        device_map="auto",
        dtype="auto",
    )
    if adapter_ref is not None:
        try:
            from peft import PeftModel
        except ImportError as exc:
            raise RuntimeError(
                "Missing PEFT dependency. Install peft to evaluate adapter checkpoints."
            ) from exc
        model = PeftModel.from_pretrained(model, adapter_ref, token=token)
    return torch, Image.open, processor, model


if __name__ == "__main__":
    raise SystemExit(main())
