from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Protocol

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.model_payload import (  # noqa: E402
    CandidateImageInput,
    CandidateRequestPayload,
    CandidateTextInput,
)
from app.schemas.training_corpus import BlacklineCandidateEvalRecord  # noqa: E402
from app.services.alert_pipeline import StructuredAlertPipeline  # noqa: E402
from app.services.model_gateway import ModelGateway, ModelGatewayTelemetry  # noqa: E402
from app.services.model_provider import resolve_http_candidate_provider  # noqa: E402
from training.scripts.eval_structured_outputs import evaluate_dataset  # noqa: E402

DEFAULT_MODEL_ID = "LiquidAI/LFM2.5-VL-450M"
DEFAULT_DATASET_PATH = (
    ROOT / "training" / "corpus" / "lfm25-vl-v1" / "blackline_candidate_eval.jsonl"
)
DEFAULT_OUTPUT_DIR = ROOT / "training" / "eval_runs" / "lfm25-vl-prompted"
DEFAULT_PREDICTIONS_NAME = "predictions.jsonl"
DEFAULT_SUMMARY_NAME = "summary.json"


class CandidateTextGenerator(Protocol):
    def generate(self, case: BlacklineCandidateEvalRecord) -> str: ...


class TransformersLfm25Runner:
    def __init__(self, *, model_id: str, max_new_tokens: int = 196) -> None:
        self.model_id = model_id
        self.max_new_tokens = max_new_tokens

        try:
            import torch
            from PIL import Image
            from transformers import AutoModelForImageTextToText, AutoProcessor
        except ImportError as exc:
            raise RuntimeError(
                "Missing local VLM dependencies. Install torch, pillow, and transformers>=5.1."
            ) from exc

        token = os.getenv("HF_TOKEN")
        self._torch = torch
        self._image_open = Image.open
        self._processor = AutoProcessor.from_pretrained(model_id, token=token)
        self._model = AutoModelForImageTextToText.from_pretrained(
            model_id,
            token=token,
            device_map="auto",
            dtype="auto",
        )

    def generate(self, case: BlacklineCandidateEvalRecord) -> str:
        current = self._image_open(case.current_image_path)
        baseline = self._image_open(case.baseline_image_path)
        conversation = build_liquid_conversation(
            case,
            current_image=current,
            baseline_image=baseline,
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
        text = self._processor.batch_decode(generated, skip_special_tokens=True)[0]
        return text.strip()


class HttpCandidateTextRunner:
    def __init__(
        self,
        *,
        model_id: str,
        endpoint: str,
        provider_id: str,
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
        gateway: ModelGateway | None = None,
        telemetry_sink: list[ModelGatewayTelemetry] | None = None,
    ) -> None:
        provider = resolve_http_candidate_provider(provider_id)
        if provider is None:
            raise RuntimeError(f"Unsupported candidate provider: {provider_id}")

        self.model_id = model_id
        self.endpoint = endpoint
        self.provider = provider
        self.api_key = api_key
        self.telemetry_sink = telemetry_sink if telemetry_sink is not None else []
        self.gateway = gateway or ModelGateway(
            timeout_seconds=timeout_seconds,
            telemetry_sink=self.telemetry_sink,
        )

    def generate(self, case: BlacklineCandidateEvalRecord) -> str:
        payload = build_frozen_candidate_payload(case=case, model_id=self.model_id)
        result = self.gateway.invoke(
            endpoint=self.endpoint,
            provider=self.provider,
            payload=payload,
            api_key=self.api_key,
            fallback="",
            request_kind="benchmark_candidate",
            frame_ids=(
                case.expected_alert.source.current_frame_id,
                case.expected_alert.source.baseline_frame_id,
            ),
        )
        return result.output_text


def build_liquid_conversation(
    case: BlacklineCandidateEvalRecord,
    *,
    current_image: object,
    baseline_image: object,
) -> list[dict[str, object]]:
    return [
        {
            "role": "system",
            "content": [{"type": "text", "text": case.prompt["system"]}],
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Current frame"},
                {"type": "image", "image": current_image},
                {"type": "text", "text": "Baseline frame"},
                {"type": "image", "image": baseline_image},
                {"type": "text", "text": case.prompt["user"]},
            ],
        },
    ]


def build_frozen_candidate_payload(
    *,
    case: BlacklineCandidateEvalRecord,
    model_id: str,
) -> CandidateRequestPayload:
    inputs: list[CandidateTextInput | CandidateImageInput] = [
        CandidateTextInput(type="input_text", role="system", text=case.prompt["system"]),
        CandidateTextInput(type="input_text", role="user", text=case.prompt["user"]),
        CandidateImageInput(
            type="input_image",
            role="current",
            image_ref=case.current_image_path,
        ),
        CandidateImageInput(
            type="input_image",
            role="baseline",
            image_ref=case.baseline_image_path,
        ),
    ]
    return CandidateRequestPayload(
        model_version=model_id,
        asset_id=case.asset.asset_id,
        scenario_id=case.case_id,
        inputs=inputs,
    )


def load_candidate_eval_cases(dataset_path: Path) -> list[BlacklineCandidateEvalRecord]:
    cases = []
    dataset_root = dataset_path.parent.resolve()
    for line in dataset_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = BlacklineCandidateEvalRecord.model_validate(json.loads(line))
        cases.append(
            case.model_copy(
                update={
                    "current_image_path": _resolve_image_path(
                        case.current_image_path,
                        dataset_root,
                    ),
                    "baseline_image_path": _resolve_image_path(
                        case.baseline_image_path,
                        dataset_root,
                    ),
                }
            )
        )
    return cases


def write_prompted_predictions(
    *,
    dataset_path: Path,
    output_path: Path,
    generator: CandidateTextGenerator,
    model_id: str,
    limit: int | None = None,
) -> tuple[Path, tuple[str, ...]]:
    cases = load_candidate_eval_cases(dataset_path)
    if limit is not None:
        cases = cases[:limit]
    case_ids = tuple(case.case_id for case in cases)
    parser = StructuredAlertPipeline(model_version=model_id)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for case in cases:
            raw_text = generator.generate(case)
            candidate = parser.parse_candidate(raw_text)
            payload: dict[str, object] = {
                "case_id": case.case_id,
                "raw_text": raw_text,
            }
            if candidate is not None:
                payload["candidate"] = candidate.model_dump(mode="json")
            else:
                payload["raw_output"] = raw_text
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return output_path, case_ids


def run_prompted_eval(
    *,
    dataset_path: Path,
    output_dir: Path,
    model_id: str = DEFAULT_MODEL_ID,
    limit: int | None = None,
    predictions_name: str = DEFAULT_PREDICTIONS_NAME,
    summary_name: str = DEFAULT_SUMMARY_NAME,
    generator: CandidateTextGenerator | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = output_dir / predictions_name
    summary_path = output_dir / summary_name

    generator = generator or TransformersLfm25Runner(model_id=model_id)
    predictions_path, case_ids = write_prompted_predictions(
        dataset_path=dataset_path,
        output_path=predictions_path,
        generator=generator,
        model_id=model_id,
        limit=limit,
    )
    eval_dataset_path = _write_dataset_subset(
        dataset_path=dataset_path,
        case_ids=case_ids,
        output_path=output_dir / "dataset_subset.jsonl",
    )
    summary = evaluate_dataset(eval_dataset_path, predictions_path=predictions_path)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return predictions_path, summary_path, summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run prompted Liquid LFM2.5-VL eval against a frozen Blackline candidate set.",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help=f"Candidate-eval JSONL. Default: {DEFAULT_DATASET_PATH}",
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
        "--limit",
        type=int,
        default=None,
        help="Optional case limit for smoke runs.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    predictions_path, summary_path, summary = run_prompted_eval(
        dataset_path=args.dataset,
        output_dir=args.output_dir,
        model_id=args.model_id,
        limit=args.limit,
    )
    print(f"wrote {predictions_path}")
    print(f"wrote {summary_path}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


def _resolve_image_path(image_path: str, dataset_root: Path) -> str:
    path = Path(image_path)
    if path.is_absolute():
        return str(path)
    return str((dataset_root / path).resolve())


def _write_dataset_subset(
    *,
    dataset_path: Path,
    case_ids: tuple[str, ...],
    output_path: Path,
) -> Path:
    wanted = set(case_ids)
    rows = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    selected = [row for row in rows if row.get("case_id") in wanted]
    output_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in selected),
        encoding="utf-8",
    )
    return output_path


if __name__ == "__main__":
    raise SystemExit(main())
