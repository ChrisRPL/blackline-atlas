from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.training_run import (  # noqa: E402
    TrainAdapterConfig,
    TrainAdapterDatasetManifest,
    TrainBackendPlan,
    TrainBundleManifest,
)
from training.scripts import train_adapter  # noqa: E402

DEFAULT_CONFIG_PATH = ROOT / "training" / "configs" / "lfm25_vl_sft_smoke.yaml"
DEFAULT_LEAP_ROOT = Path.home() / "Projects" / "oss" / "leap-finetune"
DEFAULT_BACKEND_DIRNAME = "trainer_backend"
DEFAULT_BUNDLE_DIRNAME = "trainer_bundle"
DEFAULT_BUNDLE_ARCHIVE_NAME = "trainer_bundle.tar.gz"
LEAP_CONFIG_NAME = "leap_vlm_job.yaml"
LEAP_BUNDLE_MANIFEST_NAME = "bundle_manifest.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a real LEAP VLM train backend handoff from a checked-in Blackline "
            "train config. Writes a generated LEAP config and a self-contained bundle."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"Train config YAML. Default: {DEFAULT_CONFIG_PATH}",
    )
    parser.add_argument(
        "--leap-root",
        type=Path,
        default=Path(os.getenv("BLACKLINE_LEAP_FINETUNE_ROOT", DEFAULT_LEAP_ROOT)),
        help=f"Local leap-finetune checkout. Default: {DEFAULT_LEAP_ROOT}",
    )
    parser.add_argument(
        "--skip-capture",
        action="store_true",
        help="Reuse the existing capture manifest when train_adapter prep runs.",
    )
    parser.add_argument(
        "--skip-prepare",
        action="store_true",
        help="Do not rebuild captures/corpus/export. Requires an existing dataset manifest.",
    )
    parser.add_argument(
        "--print-plan",
        action="store_true",
        help="Print the resolved backend plan as JSON and exit.",
    )
    parser.add_argument(
        "--run-local",
        action="store_true",
        help="After writing the LEAP config, run `uv run leap-finetune ...` locally.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plan, bundle_manifest = materialize_train_backend(
        config_path=args.config,
        leap_root=args.leap_root,
        skip_capture=args.skip_capture,
        skip_prepare=args.skip_prepare,
    )
    if args.print_plan:
        print(
            json.dumps(
                {
                    "backend_plan": plan.model_dump(mode="json"),
                    "bundle_manifest": bundle_manifest.model_dump(mode="json"),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    print(f"generated_config={plan.generated_config_path}")
    print(f"bundle_dir={bundle_manifest.bundle_dir}")
    print(f"bundle_archive={bundle_manifest.bundle_archive}")
    if not args.run_local:
        return 0
    run_local_train_backend(plan=plan, leap_root=args.leap_root)
    return 0


def materialize_train_backend(
    *,
    config_path: Path,
    leap_root: Path = DEFAULT_LEAP_ROOT,
    skip_capture: bool = False,
    skip_prepare: bool = False,
) -> tuple[TrainBackendPlan, TrainBundleManifest]:
    config = train_adapter.load_train_adapter_config(config_path)
    if config.trainer is None:
        raise ValueError(f"missing trainer section in config: {config_path}")
    adapter_plan = train_adapter.build_train_adapter_plan(config_path=config_path, config=config)

    if skip_prepare:
        dataset_manifest_path = Path(adapter_plan.dataset_manifest_path)
        if not dataset_manifest_path.exists():
            raise FileNotFoundError(
                f"--skip-prepare requested but dataset manifest is missing: {dataset_manifest_path}"
            )
    else:
        artifacts = train_adapter.prepare_training_artifacts(
            plan=adapter_plan,
            skip_capture=skip_capture,
        )
        dataset_manifest_path = Path(artifacts.dataset_manifest)

    dataset_manifest = load_dataset_manifest(dataset_manifest_path)
    output_dir = resolve_output_dir(config_path=config_path, config=config)
    backend_dir = output_dir / DEFAULT_BACKEND_DIRNAME
    backend_dir.mkdir(parents=True, exist_ok=True)
    generated_config_path = backend_dir / LEAP_CONFIG_NAME
    write_yaml(
        generated_config_path,
        build_leap_job_config_payload(config=config, dataset_manifest=dataset_manifest),
    )

    bundle_dir = output_dir / DEFAULT_BUNDLE_DIRNAME
    bundle_manifest = package_train_bundle(
        dataset_manifest_path=dataset_manifest_path,
        dataset_manifest=dataset_manifest,
        run_name=config.run_name,
        output_dir=bundle_dir,
        backend=config.trainer.backend,
        authoritative_eval_note=config.trainer.authoritative_eval_note,
    )
    command = ["uv", "run", "leap-finetune", str(generated_config_path)]
    plan = TrainBackendPlan(
        version="blackline-train-backend-v1",
        run_name=config.run_name,
        backend=config.trainer.backend,
        dataset_manifest=str(dataset_manifest_path),
        leap_train_dataset=dataset_manifest.leap_train_dataset,
        leap_eval_dataset=dataset_manifest.leap_eval_dataset,
        image_root=dataset_manifest.image_root,
        generated_config_path=str(generated_config_path),
        output_dir=str(output_dir),
        command=command,
        authoritative_eval_note=config.trainer.authoritative_eval_note,
        bundle_dir=bundle_manifest.bundle_dir,
        bundle_archive=bundle_manifest.bundle_archive,
    )
    if not leap_root.exists():
        return plan, bundle_manifest
    return plan, bundle_manifest


def load_dataset_manifest(path: Path) -> TrainAdapterDatasetManifest:
    return TrainAdapterDatasetManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))


def build_leap_job_config_payload(
    *,
    config: TrainAdapterConfig,
    dataset_manifest: TrainAdapterDatasetManifest,
) -> dict[str, object]:
    trainer = config.trainer
    if trainer is None:
        raise ValueError("trainer config is required")
    payload: dict[str, object] = {
        "project_name": trainer.project_name,
        "model_name": config.model.model_id,
        "training_type": "vlm_sft",
        "dataset": {
            "path": dataset_manifest.leap_train_dataset,
            "type": "vlm_sft",
            "test_size": trainer.dataset_test_size,
            "image_root": dataset_manifest.image_root,
        },
        "training_config": {
            "extends": trainer.training_config.extends,
            "num_train_epochs": trainer.training_config.num_train_epochs,
            "per_device_train_batch_size": trainer.training_config.per_device_train_batch_size,
            "gradient_accumulation_steps": trainer.training_config.gradient_accumulation_steps,
            "learning_rate": trainer.training_config.learning_rate,
            "logging_steps": trainer.training_config.logging_steps,
            "eval_on_start": trainer.training_config.eval_on_start,
            "eval_strategy": trainer.training_config.eval_strategy,
            "save_strategy": trainer.training_config.save_strategy,
            "save_total_limit": trainer.training_config.save_total_limit,
        },
        "peft_config": {
            "extends": trainer.peft_config.extends,
            "use_peft": trainer.peft_config.use_peft,
        },
    }
    if trainer.dataset_limit is not None:
        payload["dataset"]["limit"] = trainer.dataset_limit
    if trainer.training_config.eval_steps is not None:
        payload["training_config"]["eval_steps"] = trainer.training_config.eval_steps
    if trainer.training_config.save_steps is not None:
        payload["training_config"]["save_steps"] = trainer.training_config.save_steps
    if trainer.training_config.warmup_ratio is not None:
        payload["training_config"]["warmup_ratio"] = trainer.training_config.warmup_ratio
    if trainer.training_config.lr_scheduler_type is not None:
        payload["training_config"]["lr_scheduler_type"] = trainer.training_config.lr_scheduler_type
    if trainer.peft_config.r is not None:
        payload["peft_config"]["r"] = trainer.peft_config.r
    if trainer.peft_config.lora_alpha is not None:
        payload["peft_config"]["lora_alpha"] = trainer.peft_config.lora_alpha
    if trainer.peft_config.lora_dropout is not None:
        payload["peft_config"]["lora_dropout"] = trainer.peft_config.lora_dropout
    return payload


def resolve_output_dir(*, config_path: Path, config: TrainAdapterConfig) -> Path:
    if config.runtime.execution_environment == "hf_jobs":
        return (ROOT / "training" / "eval_runs" / config.run_name).resolve()
    output_path = Path(config.runtime.output_dir)
    if output_path.is_absolute():
        return output_path
    repo_roots = {"app", "docs", "tests", "training", "ui", "vendor"}
    if output_path.parts and output_path.parts[0] in repo_roots:
        return (ROOT / output_path).resolve()
    return (config_path.parent / output_path).resolve()


def write_yaml(path: Path, payload: dict[str, object]) -> Path:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "PyYAML is required for train backend configs. "
            'Install with `pip install -e ".[dev,train]"`.'
        ) from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def package_train_bundle(
    *,
    dataset_manifest_path: Path,
    dataset_manifest: TrainAdapterDatasetManifest,
    run_name: str,
    output_dir: Path,
    backend: str,
    authoritative_eval_note: str,
) -> TrainBundleManifest:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    train_path = Path(dataset_manifest.leap_train_dataset)
    eval_path = Path(dataset_manifest.leap_eval_dataset)
    summary_path = Path(dataset_manifest.leap_summary)
    dataset_manifest_path = Path(dataset_manifest.leap_summary).with_name("dataset_manifest.json")
    image_root = Path(dataset_manifest.image_root)

    bundled_train = output_dir / "train.jsonl"
    bundled_eval = output_dir / "eval.jsonl"
    bundled_summary = output_dir / "summary.json"
    bundled_manifest = output_dir / "dataset_manifest.json"

    shutil.copy2(train_path, bundled_train)
    shutil.copy2(eval_path, bundled_eval)
    shutil.copy2(summary_path, bundled_summary)
    shutil.copy2(dataset_manifest_path, bundled_manifest)

    referenced_images = collect_referenced_images(train_path) | collect_referenced_images(eval_path)
    for relative_path in sorted(referenced_images):
        source_path = image_root / relative_path
        if not source_path.exists():
            raise FileNotFoundError(f"missing referenced image for bundle: {source_path}")
        destination = output_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)

    archive_path = output_dir.parent / f"{run_name}_{DEFAULT_BUNDLE_ARCHIVE_NAME}"
    if archive_path.exists():
        archive_path.unlink()
    with tarfile.open(archive_path, mode="w:gz") as tar:
        tar.add(output_dir, arcname=output_dir.name)

    summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    bundle_manifest = TrainBundleManifest(
        version="blackline-train-bundle-v1",
        run_name=run_name,
        backend=backend,
        dataset_manifest=str(bundled_manifest),
        train_jsonl=str(bundled_train),
        eval_jsonl=str(bundled_eval),
        summary_json=str(bundled_summary),
        image_root=str(output_dir),
        bundle_dir=str(output_dir),
        bundle_archive=str(archive_path),
        train_records=summary_payload.get("train_records", 0),
        eval_records=summary_payload.get("eval_records", 0),
        authoritative_eval_note=authoritative_eval_note,
    )
    (output_dir / LEAP_BUNDLE_MANIFEST_NAME).write_text(
        json.dumps(bundle_manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return bundle_manifest


def collect_referenced_images(jsonl_path: Path) -> set[str]:
    referenced: set[str] = set()
    if not jsonl_path.exists():
        return referenced
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        for message in payload.get("messages", []):
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if item.get("type") != "image":
                    continue
                image_path = item.get("image")
                if not isinstance(image_path, str) or Path(image_path).is_absolute():
                    continue
                referenced.add(image_path)
    return referenced


def run_local_train_backend(*, plan: TrainBackendPlan, leap_root: Path) -> None:
    if not leap_root.exists():
        raise FileNotFoundError(f"missing leap-finetune checkout: {leap_root}")
    env = os.environ.copy()
    env["OUTPUT_DIR"] = str(Path(plan.output_dir) / "checkpoints")
    subprocess.run(plan.command, cwd=leap_root, check=True, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
