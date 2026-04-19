from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.annotated_case import AnnotatedCaseRecord  # noqa: E402
from app.services.alert_pipeline import StructuredAlertPipeline  # noqa: E402
from app.services.model_gateway import ModelGateway, ModelGatewayTelemetry  # noqa: E402
from app.services.model_provider import resolve_http_candidate_provider  # noqa: E402
from app.services.model_wrapper import HttpRawCandidateBackend, PromptedCandidateModel  # noqa: E402
from app.services.scenario_fixtures import ScenarioFixture  # noqa: E402
from training.scripts.capture_simsat_manifest import (  # noqa: E402
    build_simsat_capture_manifest,
)

DEFAULT_CASES_DATASET = ROOT / "training" / "replay_pack" / "non_demo_eval.jsonl"
DEFAULT_CAPTURE_OVERRIDES = ROOT / "training" / "replay_pack" / "non_demo_capture_overrides.json"
DEFAULT_OUTPUT_DIR = ROOT / "output" / "candidate_smoke"
DEFAULT_MODEL_VERSION = "LiquidAI/LFM2.5-VL-450M"
DEFAULT_PROVIDER = "openai_chat_completions_http"
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_CAPTURE_DIR = Path("/tmp/blackline-candidate-smoke-capture")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Capture one real SimSat pair and smoke the configured candidate "
            "HTTP backend against it."
        ),
    )
    parser.add_argument(
        "--historical-endpoint",
        required=True,
        help="SimSat historical Sentinel endpoint.",
    )
    parser.add_argument(
        "--model-endpoint",
        required=True,
        help="OpenAI-compatible chat completions endpoint.",
    )
    parser.add_argument("--case-id", required=True, help="Annotated case id to capture and run.")
    parser.add_argument(
        "--cases-dataset",
        type=Path,
        default=DEFAULT_CASES_DATASET,
        help=f"Annotated case dataset. Default: {DEFAULT_CASES_DATASET}",
    )
    parser.add_argument(
        "--capture-overrides",
        type=Path,
        default=DEFAULT_CAPTURE_OVERRIDES,
        help=f"Capture overrides JSON. Default: {DEFAULT_CAPTURE_OVERRIDES}",
    )
    parser.add_argument(
        "--capture-output-dir",
        type=Path,
        default=DEFAULT_CAPTURE_DIR,
        help="Directory for captured frames.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for smoke output. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--model-version",
        default=DEFAULT_MODEL_VERSION,
        help=f"Model version recorded in prompt/pipeline. Default: {DEFAULT_MODEL_VERSION}",
    )
    parser.add_argument(
        "--model-provider",
        default=DEFAULT_PROVIDER,
        help=f"HTTP provider id. Default: {DEFAULT_PROVIDER}",
    )
    parser.add_argument(
        "--model-api-key",
        default=None,
        help="Optional bearer token for the model endpoint.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Gateway timeout for cold model boots. Default: {DEFAULT_TIMEOUT_SECONDS}",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    provider = resolve_http_candidate_provider(args.model_provider)
    if provider is None:
        raise SystemExit(f"unsupported model provider: {args.model_provider}")

    case = load_case(args.cases_dataset, args.case_id)
    capture = capture_case(
        case_id=args.case_id,
        cases_dataset=args.cases_dataset,
        capture_overrides=args.capture_overrides,
        output_dir=args.capture_output_dir,
        historical_endpoint=args.historical_endpoint,
    )
    current, baseline = materialize_case_frames(case=case, capture_record=capture)
    scenario = ScenarioFixture(
        scenario_id=case.case_id,
        asset_id=case.asset.asset_id,
        current_frame=current,
        baseline_frame=baseline,
        model_output_text=case.model_output_text,
        alerts=[case.expected_alert],
        metrics=case.expected_metrics,
    )

    telemetry: list[ModelGatewayTelemetry] = []
    model = PromptedCandidateModel(
        model_version=args.model_version,
        backend=HttpRawCandidateBackend(
            endpoint=args.model_endpoint,
            provider=provider,
            api_key=args.model_api_key,
            gateway=ModelGateway(
                timeout_seconds=args.timeout_seconds,
                telemetry_sink=telemetry,
            ),
        ),
    )
    raw_text = model.generate_candidate_text(
        asset=case.asset,
        scenario=scenario,
        current=current,
        baseline=baseline,
    )
    parser = StructuredAlertPipeline(model_version=args.model_version)
    candidate = parser.parse_candidate(raw_text)

    payload = {
        "case_id": case.case_id,
        "asset_id": case.asset.asset_id,
        "model_endpoint": args.model_endpoint,
        "model_provider": args.model_provider,
        "current_image_path": current.frame.image_ref,
        "baseline_image_path": baseline.frame.image_ref,
        "raw_text": raw_text,
        "candidate": candidate.model_dump(mode="json") if candidate else None,
        "telemetry": _telemetry_payload(telemetry[-1] if telemetry else None),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / f"{case.case_id}.json"
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {output_path}")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def load_case(dataset_path: Path, case_id: str) -> AnnotatedCaseRecord:
    for raw_line in dataset_path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        case = AnnotatedCaseRecord.model_validate(json.loads(raw_line))
        if case.case_id == case_id:
            return case
    raise ValueError(f"case_id not found in {dataset_path}: {case_id}")


def capture_case(
    *,
    case_id: str,
    cases_dataset: Path,
    capture_overrides: Path,
    output_dir: Path,
    historical_endpoint: str,
) -> dict[str, object]:
    records = build_simsat_capture_manifest(
        historical_endpoint=historical_endpoint,
        output_dir=output_dir,
        cases_dataset_path=cases_dataset,
        capture_overrides_path=capture_overrides if capture_overrides.exists() else None,
        scenario_ids=(case_id,),
    )
    if not records:
        raise ValueError(f"no capture records built for {case_id}")
    record = records[0]
    current_path = record["current"].get("image_path")
    baseline_path = record["baseline"].get("image_path")
    if not current_path or not baseline_path:
        raise ValueError(f"capture missing frame bytes for {case_id}")
    return record


def materialize_case_frames(
    *,
    case: AnnotatedCaseRecord,
    capture_record: dict[str, object],
):
    current_capture = capture_record["current"]
    baseline_capture = capture_record["baseline"]
    current = case.current_frame.model_copy(
        update={
            "frame": case.current_frame.frame.model_copy(
                update={
                    "image_ref": current_capture["image_path"],
                    "cloud_cover": current_capture["response_metadata"].get("cloud_cover"),
                    "captured_at": current_capture["response_metadata"].get("datetime")
                    or current_capture["response_metadata"].get("timestamp")
                    or case.current_frame.frame.captured_at,
                    "source": current_capture["request_url"],
                }
            ),
            "overlay_ref": None,
        }
    )
    baseline = case.baseline_frame.model_copy(
        update={
            "frame": case.baseline_frame.frame.model_copy(
                update={
                    "image_ref": baseline_capture["image_path"],
                    "cloud_cover": baseline_capture["response_metadata"].get("cloud_cover"),
                    "captured_at": baseline_capture["response_metadata"].get("datetime")
                    or baseline_capture["response_metadata"].get("timestamp")
                    or case.baseline_frame.frame.captured_at,
                    "source": baseline_capture["request_url"],
                }
            )
        }
    )
    return current, baseline


def _telemetry_payload(telemetry: ModelGatewayTelemetry | None) -> dict[str, object] | None:
    if telemetry is None:
        return None
    return {
        "request_kind": telemetry.request_kind,
        "model_version": telemetry.model_version,
        "provider_id": telemetry.provider_id,
        "latency_ms": telemetry.latency_ms,
        "parse_ok": telemetry.parse_ok,
        "cache_hit": telemetry.cache_hit,
        "fallback_reason": telemetry.fallback_reason,
        "prompt_hash": telemetry.prompt_hash,
        "frame_ids": list(telemetry.frame_ids),
    }


if __name__ == "__main__":
    raise SystemExit(main())
