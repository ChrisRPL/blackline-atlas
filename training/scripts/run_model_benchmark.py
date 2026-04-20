from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.model_benchmark import (  # noqa: E402
    BenchmarkManifest,
    BenchmarkModelConfig,
    BenchmarkSliceConfig,
)
from training.scripts.materialize_internal_benchmark_slice import (  # noqa: E402
    materialize_internal_benchmark_slice,
)
from training.scripts.run_lfm25_vl_prompted_eval import (  # noqa: E402
    HttpCandidateTextRunner,
    TransformersLfm25Runner,
    run_prompted_eval,
)

DEFAULT_MANIFEST = ROOT / "training" / "replay_pack" / "model_benchmark_manifest.json"


@dataclass(frozen=True)
class BenchmarkSkip:
    model_key: str
    slice_id: str
    reason: str


@dataclass(frozen=True)
class BenchmarkRunResult:
    model_key: str
    model_title: str
    model_id: str
    slice_id: str
    slice_title: str
    tier: str
    predictions_path: Path
    summary_path: Path
    summary: dict[str, Any]


class SkipBenchmarkRun(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Blackline cross-model benchmark cohort against ready eval slices.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"Benchmark manifest path. Default: {DEFAULT_MANIFEST}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional benchmark output directory. Defaults to the manifest value.",
    )
    parser.add_argument(
        "--model-key",
        action="append",
        default=None,
        help="Restrict to one or more model keys.",
    )
    parser.add_argument(
        "--slice-id",
        action="append",
        default=None,
        help="Restrict to one or more slice ids.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional case limit per slice for smoke runs.",
    )
    return parser.parse_args(argv)


def load_manifest(path: Path) -> BenchmarkManifest:
    return BenchmarkManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))


def resolve_selected_models(
    manifest: BenchmarkManifest,
    *,
    model_keys: list[str] | None,
) -> list[BenchmarkModelConfig]:
    wanted = set(model_keys or [])
    models = []
    for model in manifest.models:
        if wanted and model.model_key not in wanted:
            continue
        if not wanted and not model.enabled:
            continue
        models.append(model)
    return models


def resolve_selected_slices(
    manifest: BenchmarkManifest,
    *,
    slice_ids: list[str] | None,
) -> list[BenchmarkSliceConfig]:
    wanted = set(slice_ids or [])
    slices = []
    for slice_config in manifest.slices:
        if wanted and slice_config.slice_id not in wanted:
            continue
        slices.append(slice_config)
    return slices


def run_benchmark(
    *,
    manifest_path: Path,
    output_dir: Path | None,
    model_keys: list[str] | None = None,
    slice_ids: list[str] | None = None,
    limit: int | None = None,
) -> tuple[list[BenchmarkRunResult], list[BenchmarkSkip], Path, Path]:
    manifest = load_manifest(manifest_path)
    benchmark_output_dir = output_dir or (ROOT / manifest.default_output_dir)
    benchmark_output_dir.mkdir(parents=True, exist_ok=True)

    models = resolve_selected_models(manifest, model_keys=model_keys)
    slices = resolve_selected_slices(manifest, slice_ids=slice_ids)
    results: list[BenchmarkRunResult] = []
    skipped: list[BenchmarkSkip] = []

    for model in models:
        for slice_config in slices:
            try:
                result = _run_single_slice(
                    model=model,
                    slice_config=slice_config,
                    output_dir=benchmark_output_dir,
                    limit=limit,
                )
            except SkipBenchmarkRun as exc:
                skipped.append(
                    BenchmarkSkip(
                        model_key=model.model_key,
                        slice_id=slice_config.slice_id,
                        reason=str(exc),
                    )
                )
                continue
            results.append(result)

    scorecard_json = benchmark_output_dir / "scorecard.json"
    scorecard_md = benchmark_output_dir / "scorecard.md"
    payload = build_scorecard_payload(results=results, skipped=skipped)
    scorecard_json.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    scorecard_md.write_text(
        render_scorecard_markdown(results=results, skipped=skipped),
        encoding="utf-8",
    )
    return results, skipped, scorecard_json, scorecard_md


def build_scorecard_payload(
    *,
    results: list[BenchmarkRunResult],
    skipped: list[BenchmarkSkip],
) -> dict[str, Any]:
    return {
        "results": [
            {
                "model_key": result.model_key,
                "model_title": result.model_title,
                "model_id": result.model_id,
                "slice_id": result.slice_id,
                "slice_title": result.slice_title,
                "tier": result.tier,
                "predictions_path": str(result.predictions_path),
                "summary_path": str(result.summary_path),
                "summary": result.summary,
            }
            for result in results
        ],
        "skipped": [
            {
                "model_key": item.model_key,
                "slice_id": item.slice_id,
                "reason": item.reason,
            }
            for item in skipped
        ],
    }


def render_scorecard_markdown(
    *,
    results: list[BenchmarkRunResult],
    skipped: list[BenchmarkSkip],
) -> str:
    lines = [
        "# Blackline Model Benchmark",
        "",
    ]
    if results:
        lines.extend(
            [
                "| Model | Slice | Tier | Total | Pass | Action | Schema | FP | Downlink |",
                "|---|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for result in results:
            metrics = result.summary["metrics"]
            rates = result.summary["rates"]
            predicted = result.summary["predicted_action_counts"]
            lines.append(
                "| "
                + " | ".join(
                    [
                        result.model_title,
                        result.slice_title,
                        result.tier,
                        str(result.summary["total_cases"]),
                        _pct(rates["pass_rate"]),
                        _pct(rates["action_match_rate"]),
                        _pct(rates["schema_valid_rate"]),
                        str(metrics["false_positive_count"]),
                        str(predicted["downlink_now"]),
                    ]
                )
                + " |"
            )
        lines.append("")

    if skipped:
        lines.append("## Skipped")
        lines.append("")
        for item in skipped:
            lines.append(f"- `{item.model_key}` on `{item.slice_id}`: {item.reason}")
        lines.append("")

    return "\n".join(lines)


def _run_single_slice(
    *,
    model: BenchmarkModelConfig,
    slice_config: BenchmarkSliceConfig,
    output_dir: Path,
    limit: int | None,
) -> BenchmarkRunResult:
    if slice_config.status != "ready":
        raise SkipBenchmarkRun(f"slice status is {slice_config.status}")
    if not slice_config.dataset_path:
        raise SkipBenchmarkRun("slice dataset path missing")

    dataset_path = _resolve_dataset_path(slice_config=slice_config, output_dir=output_dir)
    if not dataset_path.exists():
        raise SkipBenchmarkRun(f"dataset missing: {dataset_path}")

    generator = _build_generator(model)
    run_output_dir = output_dir / model.model_key / slice_config.slice_id
    predictions_path, summary_path, summary = run_prompted_eval(
        dataset_path=dataset_path,
        output_dir=run_output_dir,
        model_id=model.model_id,
        limit=limit,
        generator=generator,
    )
    return BenchmarkRunResult(
        model_key=model.model_key,
        model_title=model.title,
        model_id=model.model_id,
        slice_id=slice_config.slice_id,
        slice_title=slice_config.title,
        tier=slice_config.tier,
        predictions_path=predictions_path,
        summary_path=summary_path,
        summary=summary,
    )


def _build_generator(model: BenchmarkModelConfig):
    if model.runner_kind == "transformers_local":
        return TransformersLfm25Runner(model_id=model.model_id)

    if model.runner_kind == "openai_chat_completions_http":
        endpoint = os.getenv(model.endpoint_env or "")
        if not endpoint:
            raise SkipBenchmarkRun(f"missing endpoint env {model.endpoint_env}")
        api_key = os.getenv(model.api_key_env) if model.api_key_env else None
        return HttpCandidateTextRunner(
            model_id=model.model_id,
            endpoint=endpoint,
            provider_id=model.provider_id or "openai_chat_completions_http",
            api_key=api_key,
        )

    raise SkipBenchmarkRun(f"unsupported runner kind {model.runner_kind}")


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _resolve_dataset_path(
    *,
    slice_config: BenchmarkSliceConfig,
    output_dir: Path,
) -> Path:
    raw_path = Path(slice_config.dataset_path or "")
    dataset_path = raw_path if raw_path.is_absolute() else (ROOT / raw_path)
    dataset_path = dataset_path.resolve()

    if slice_config.tier != "internal":
        return dataset_path

    try:
        return materialize_internal_benchmark_slice(
            annotated_dataset_path=dataset_path,
            output_dir=output_dir / "_prepared" / slice_config.slice_id,
            capture_manifest_path=_env_path("BLACKLINE_INTERNAL_BENCHMARK_CAPTURE_MANIFEST"),
            historical_endpoint=(
                os.getenv("BLACKLINE_INTERNAL_BENCHMARK_HISTORICAL_ENDPOINT")
                or os.getenv("SIMSAT_BASELINE_ENDPOINT")
            ),
            capture_overrides_path=(
                _env_path("BLACKLINE_INTERNAL_BENCHMARK_CAPTURE_OVERRIDES")
                or (ROOT / "training" / "replay_pack" / "non_demo_capture_overrides.json").resolve()
            ),
        )
    except ValueError as exc:
        raise SkipBenchmarkRun(str(exc)) from exc


def _env_path(name: str) -> Path | None:
    value = os.getenv(name)
    if not value:
        return None
    return Path(value).resolve()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    results, skipped, scorecard_json, scorecard_md = run_benchmark(
        manifest_path=args.manifest,
        output_dir=args.output_dir,
        model_keys=args.model_key,
        slice_ids=args.slice_id,
        limit=args.limit,
    )
    print(f"wrote {scorecard_json}")
    print(f"wrote {scorecard_md}")
    print(f"benchmark_runs={len(results)} skipped={len(skipped)}")
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
