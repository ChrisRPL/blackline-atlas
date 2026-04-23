from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.training_run import (  # noqa: E402
    TrainAdapterConfig,
    TrainAdapterDatasetManifest,
    TrainAdapterPlan,
    TrainAdapterPreparedArtifacts,
)
from training.scripts.build_lfm25_vl_corpus import write_lfm25_vl_corpus  # noqa: E402
from training.scripts.capture_simsat_manifest import write_simsat_capture_manifest  # noqa: E402
from training.scripts.export_leap_vlm_sft import write_leap_vlm_sft_records  # noqa: E402
from training.scripts.materialize_aux_train_slice import materialize_aux_train_slice  # noqa: E402

DEFAULT_CONFIG_PATH = ROOT / "training" / "configs" / "lfm25_vl_sft_smoke.yaml"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare Blackline VLM training/eval artifacts from a config-first run "
            "definition. Builds captures, corpus files, LEAP export, and a dataset manifest."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"Run config YAML. Default: {DEFAULT_CONFIG_PATH}",
    )
    parser.add_argument(
        "--print-plan",
        action="store_true",
        help="Validate config and print the resolved plan without running prep.",
    )
    parser.add_argument(
        "--skip-capture",
        action="store_true",
        help="Reuse the resolved capture manifest if it already exists.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_train_adapter_config(args.config)
    plan = build_train_adapter_plan(config_path=args.config, config=config)

    if args.print_plan:
        print(json.dumps(plan.model_dump(mode="json"), indent=2, sort_keys=True))
        return 0

    artifacts = prepare_training_artifacts(plan=plan, skip_capture=args.skip_capture)
    print(f"capture_manifest={artifacts.capture_manifest}")
    print(f"candidate_eval_dataset={artifacts.candidate_eval_dataset}")
    print(f"leap_train_dataset={artifacts.leap_train_dataset}")
    print(f"leap_eval_dataset={artifacts.leap_eval_dataset}")
    print(f"dataset_manifest={artifacts.dataset_manifest}")
    return 0


def load_train_adapter_config(path: Path) -> TrainAdapterConfig:
    if not path.exists():
        raise FileNotFoundError(f"missing config: {path}")
    payload = _read_yaml(path)
    return TrainAdapterConfig.model_validate(payload)


def build_train_adapter_plan(
    *,
    config_path: Path,
    config: TrainAdapterConfig,
) -> TrainAdapterPlan:
    base_dir = config_path.parent
    capture_manifest = (
        _resolve_path(base_dir, config.dataset.capture_manifest)
        if config.dataset.capture_manifest
        else _resolve_path(base_dir, config.dataset.capture_output_dir)
        / "simsat_capture_manifest.json"
    )
    dataset_manifest_path = (
        _resolve_path(base_dir, config.dataset.leap_output_dir)
        / config.dataset.dataset_manifest_name
    )
    return TrainAdapterPlan(
        config_path=str(config_path.resolve()),
        run_name=config.run_name,
        purpose=config.purpose,
        historical_endpoint=config.dataset.historical_endpoint,
        replay_dataset=str(_resolve_path(base_dir, config.dataset.replay_dataset)),
        aux_candidate_eval_datasets=[
            str(_resolve_path(base_dir, dataset_path))
            for dataset_path in config.dataset.aux_candidate_eval_datasets
        ],
        capture_overrides=(
            str(_resolve_path(base_dir, config.dataset.capture_overrides))
            if config.dataset.capture_overrides
            else None
        ),
        capture_output_dir=str(_resolve_path(base_dir, config.dataset.capture_output_dir)),
        capture_manifest=str(capture_manifest),
        corpus_output_dir=str(_resolve_path(base_dir, config.dataset.corpus_output_dir)),
        leap_output_dir=str(_resolve_path(base_dir, config.dataset.leap_output_dir)),
        dataset_manifest_path=str(dataset_manifest_path),
        model_id=config.model.model_id,
        task_kind=config.model.task_kind,
        eval_mode=config.eval.mode,
        benchmark_on_start=config.eval.benchmark_on_start,
        max_eval_cases=config.eval.max_eval_cases,
        save_full_predictions=config.eval.save_full_predictions,
        execution_environment=config.runtime.execution_environment,
        editable_extras=config.runtime.editable_extras,
        output_dir=config.runtime.output_dir,
        hf_flavor=config.hf_job.flavor,
        hf_timeout=config.hf_job.timeout,
    )


def prepare_training_artifacts(
    *,
    plan: TrainAdapterPlan,
    skip_capture: bool = False,
) -> TrainAdapterPreparedArtifacts:
    capture_manifest_path = Path(plan.capture_manifest)
    capture_output_dir = Path(plan.capture_output_dir)

    if skip_capture:
        if not capture_manifest_path.exists():
            raise FileNotFoundError(
                f"--skip-capture requested but capture manifest is missing: {capture_manifest_path}"
            )
        capture_dataset_path = capture_output_dir / "simsat_capture_manifest.jsonl"
    else:
        if plan.historical_endpoint is None:
            raise ValueError("historical_endpoint is required when capture is not skipped")
        capture_manifest_path, capture_dataset_path = write_simsat_capture_manifest(
            plan.historical_endpoint,
            output_dir=capture_output_dir,
            cases_dataset_path=Path(plan.replay_dataset),
            capture_overrides_path=(
                Path(plan.capture_overrides) if plan.capture_overrides is not None else None
            ),
        )

    grounding_path, internal_candidate_eval_path, splits_path = write_lfm25_vl_corpus(
        output_dir=Path(plan.corpus_output_dir),
        capture_manifest_path=capture_manifest_path,
        replay_dataset_path=Path(plan.replay_dataset),
    )
    candidate_eval_path = internal_candidate_eval_path
    if plan.aux_candidate_eval_datasets:
        merged_output_dir = Path(plan.corpus_output_dir) / "merged_candidate_eval"
        candidate_eval_path, _ = materialize_aux_train_slice(
            source_datasets=(
                internal_candidate_eval_path,
                *(Path(dataset_path) for dataset_path in plan.aux_candidate_eval_datasets),
            ),
            output_dir=merged_output_dir,
        )
    leap_train_path, leap_eval_path, leap_summary_path = write_leap_vlm_sft_records(
        candidate_eval_path=candidate_eval_path,
        output_dir=Path(plan.leap_output_dir),
    )
    dataset_manifest_path = write_dataset_manifest(
        plan=plan,
        liquid_grounding_path=grounding_path,
        candidate_eval_path=candidate_eval_path,
        internal_candidate_eval_path=internal_candidate_eval_path,
        splits_path=splits_path,
        leap_train_path=leap_train_path,
        leap_eval_path=leap_eval_path,
        leap_summary_path=leap_summary_path,
        capture_manifest_path=capture_manifest_path,
    )
    return TrainAdapterPreparedArtifacts(
        capture_manifest=str(capture_manifest_path),
        capture_dataset=str(capture_dataset_path),
        liquid_grounding_dataset=str(grounding_path),
        candidate_eval_dataset=str(candidate_eval_path),
        splits_manifest=str(splits_path),
        leap_train_dataset=str(leap_train_path),
        leap_eval_dataset=str(leap_eval_path),
        leap_summary=str(leap_summary_path),
        dataset_manifest=str(dataset_manifest_path),
    )


def write_dataset_manifest(
    *,
    plan: TrainAdapterPlan,
    liquid_grounding_path: Path,
    candidate_eval_path: Path,
    internal_candidate_eval_path: Path,
    splits_path: Path,
    leap_train_path: Path,
    leap_eval_path: Path,
    leap_summary_path: Path,
    capture_manifest_path: Path,
) -> Path:
    leap_summary = json.loads(leap_summary_path.read_text(encoding="utf-8"))
    if plan.eval_mode == "smoke" and leap_summary.get("train_records", 0) == 0:
        raise ValueError("smoke config produced zero train records; refuse to continue")
    manifest = TrainAdapterDatasetManifest(
        version="blackline-train-adapter-v1",
        run_name=plan.run_name,
        purpose=plan.purpose,
        model_id=plan.model_id,
        task_kind=plan.task_kind,
        source_replay_dataset=plan.replay_dataset,
        source_aux_candidate_eval_datasets=plan.aux_candidate_eval_datasets,
        capture_manifest=str(capture_manifest_path),
        liquid_grounding_dataset=str(liquid_grounding_path),
        source_internal_candidate_eval_dataset=str(internal_candidate_eval_path),
        candidate_eval_dataset=str(candidate_eval_path),
        splits_manifest=str(splits_path),
        image_root=str(candidate_eval_path.parent.resolve()),
        leap_train_dataset=str(leap_train_path),
        leap_eval_dataset=str(leap_eval_path),
        leap_summary=str(leap_summary_path),
        source_split_counts=leap_summary["source_split_counts"],
        eval_mode=plan.eval_mode,
        benchmark_on_start=plan.benchmark_on_start,
        max_eval_cases=plan.max_eval_cases,
        save_full_predictions=plan.save_full_predictions,
        execution_environment=plan.execution_environment,
        output_dir=plan.output_dir,
        hf_flavor=plan.hf_flavor,
        hf_timeout=plan.hf_timeout,
    )
    output_path = Path(plan.dataset_manifest_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _read_yaml(path: Path) -> dict[str, object]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - exercised through dependency declaration
        raise RuntimeError(
            "PyYAML is required for train adapter configs. "
            'Install with `pip install -e ".[dev,train]"`.'
        ) from exc

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"config root must be a mapping: {path}")
    return payload


def _resolve_path(base_dir: Path, raw_path: str | None) -> Path:
    if raw_path is None:
        raise ValueError("expected path string, got None")
    path = Path(raw_path)
    if path.is_absolute():
        return path
    if str(path).startswith("."):
        return (base_dir / path).resolve()
    repo_roots = {"app", "docs", "tests", "training", "ui", "vendor"}
    if path.parts and path.parts[0] in repo_roots:
        return (ROOT / path).resolve()
    return (base_dir / path).resolve()


if __name__ == "__main__":
    raise SystemExit(main())
