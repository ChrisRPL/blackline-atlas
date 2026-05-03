from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from shutil import copy2
from typing import Any

from huggingface_hub import HfApi, hf_hub_download

DEFAULT_LEAP_REPO = "https://github.com/Liquid4All/leap-finetune.git"
DEFAULT_LEAP_REF = "d017458"
DEFAULT_OUTPUT_DIR = "/outputs/blackline-train"
MODEL_ID = "LiquidAI/LFM2.5-VL-450M"
RANDOM_SEED = 42
ADAPTER_REQUIRED_FILES = ("adapter_config.json",)
ADAPTER_WEIGHT_FILES = ("adapter_model.safetensors", "adapter_model.bin")
ADAPTER_PUBLISH_FILES = (
    "adapter_config.json",
    "adapter_model.safetensors",
    "adapter_model.bin",
    "trainer_state.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize the Blackline HF corpus inside HF Jobs and train LFM2.5-VL."
    )
    parser.add_argument("--job-spec", required=True)
    parser.add_argument("--corpus-repo-id", required=True)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--leap-repo", default=DEFAULT_LEAP_REPO)
    parser.add_argument("--leap-ref", default=DEFAULT_LEAP_REF)
    parser.add_argument("--publish-adapter-repo-id", required=True)
    parser.add_argument("--publish-adapter-private", default="true")
    return parser.parse_args()


def main() -> int:
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "60")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "180")
    args = parse_args()
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN secret is missing")
    job_spec = json.loads(args.job_spec)
    with tempfile.TemporaryDirectory(prefix="blackline-corpus-train-") as temp:
        workspace = Path(temp)
        bundle_dir = workspace / "trainer_bundle"
        materialize_corpus_bundle(
            corpus_repo_id=args.corpus_repo_id,
            token=token,
            bundle_dir=bundle_dir,
            run_name=str(job_spec["run_name"]),
            materialization=dict(job_spec["corpus_materialization"]),
        )
        config_path = workspace / "leap_vlm_job.yaml"
        write_yaml(
            config_path,
            build_leap_config(job_spec=job_spec, bundle_dir=bundle_dir),
        )
        leap_dir = clone_leap_finetune(
            workspace=workspace,
            repo_url=args.leap_repo,
            ref=args.leap_ref,
        )
        sanitize_leap_repo_for_hf_jobs(repo_dir=leap_dir)
        run_leap_train(repo_dir=leap_dir, config_path=config_path, output_dir=args.output_dir)
        maybe_publish_adapter_artifacts(
            workspace=workspace,
            output_dir=Path(args.output_dir),
            repo_id=args.publish_adapter_repo_id,
            private=parse_bool_arg(args.publish_adapter_private),
            base_model_id=str(job_spec["model_id"]),
            run_name=str(job_spec["run_name"]),
            corpus_repo_id=args.corpus_repo_id,
            bundle_dir=bundle_dir,
        )
    return 0


def materialize_corpus_bundle(
    *,
    corpus_repo_id: str,
    token: str,
    bundle_dir: Path,
    run_name: str,
    materialization: dict[str, Any],
) -> None:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(RANDOM_SEED)
    train_rows: list[dict[str, Any]] = []
    eval_rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    simsat_repeat = int(materialization.get("simsat_repeat", 8))

    simsat_train = download_jsonl(
        corpus_repo_id, "vlm_evidence_sft_simsat_gold_v1/train.jsonl", token
    )
    simsat_eval = download_jsonl(
        corpus_repo_id, "vlm_evidence_sft_simsat_gold_v1/eval.jsonl", token
    )
    for repeat_idx in range(simsat_repeat):
        for row in simsat_train:
            train_rows.append(
                convert_pair_row(
                    corpus_repo_id=corpus_repo_id,
                    token=token,
                    bundle_dir=bundle_dir,
                    row=row,
                    shard_prefix="vlm_evidence_sft_simsat_gold_v1",
                    row_suffix=f"repeat{repeat_idx:02d}",
                )
            )
        print_progress("simsat_train_repeat", repeat_idx + 1, simsat_repeat)
    for row in simsat_eval:
        eval_rows.append(
            convert_pair_row(
                corpus_repo_id=corpus_repo_id,
                token=token,
                bundle_dir=bundle_dir,
                row=row,
                shard_prefix="vlm_evidence_sft_simsat_gold_v1",
                row_suffix="heldout",
            )
        )
    counts["simsat_gold_train_repeated_rows"] = len(simsat_train) * simsat_repeat
    counts["simsat_gold_eval_rows"] = len(simsat_eval)

    if materialization.get("include_initial_vlm"):
        add_single_image_split(
            corpus_repo_id=corpus_repo_id,
            token=token,
            bundle_dir=bundle_dir,
            shard_prefix="vlm_evidence_sft",
            train_count=int(materialization.get("initial_vlm_train_rows", 0)),
            eval_count=int(materialization.get("initial_vlm_eval_rows", 0)),
            rng=rng,
            train_rows=train_rows,
            eval_rows=eval_rows,
            counts=counts,
            count_prefix="initial_vlm",
        )
    add_single_image_split(
        corpus_repo_id=corpus_repo_id,
        token=token,
        bundle_dir=bundle_dir,
        shard_prefix="vlm_evidence_sft_bigearthnet_s2_chunk_01",
        train_count=int(materialization.get("bigearthnet_train_rows", 128)),
        eval_count=int(materialization.get("context_eval_rows", 32)),
        rng=rng,
        train_rows=train_rows,
        eval_rows=eval_rows,
        counts=counts,
        count_prefix="bigearthnet",
    )
    add_single_image_split(
        corpus_repo_id=corpus_repo_id,
        token=token,
        bundle_dir=bundle_dir,
        shard_prefix="vlm_evidence_sft_chatearthnet_chunk_02",
        train_count=int(materialization.get("chatearthnet_train_rows", 128)),
        eval_count=int(materialization.get("context_eval_rows", 32)),
        rng=rng,
        train_rows=train_rows,
        eval_rows=eval_rows,
        counts=counts,
        count_prefix="chatearthnet",
    )
    write_jsonl(bundle_dir / "train.jsonl", train_rows)
    write_jsonl(bundle_dir / "eval.jsonl", eval_rows)
    summary = {
        "run_name": run_name,
        "source_corpus_repo_id": corpus_repo_id,
        "train_records": len(train_rows),
        "eval_records": len(eval_rows),
        "source_split_counts": counts,
        "image_files": sum(1 for path in (bundle_dir / "images").rglob("*") if path.is_file()),
        "strategy": (
            "HF Jobs direct materialization; SimSat gold oversampled, "
            "context shards normalized to JSON discard targets."
        ),
    }
    (bundle_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"materialized_bundle": summary}, indent=2), flush=True)


def add_single_image_split(
    *,
    corpus_repo_id: str,
    token: str,
    bundle_dir: Path,
    shard_prefix: str,
    train_count: int,
    eval_count: int,
    rng: random.Random,
    train_rows: list[dict[str, Any]],
    eval_rows: list[dict[str, Any]],
    counts: dict[str, int],
    count_prefix: str,
) -> None:
    train = sample_rows(
        download_jsonl(corpus_repo_id, f"{shard_prefix}/train.jsonl", token), train_count, rng
    )
    eval_ = sample_rows(
        download_jsonl(corpus_repo_id, f"{shard_prefix}/eval.jsonl", token), eval_count, rng
    )
    for idx, row in enumerate(train, start=1):
        train_rows.append(
            convert_single_image_row(
                corpus_repo_id=corpus_repo_id,
                token=token,
                bundle_dir=bundle_dir,
                row=row,
                shard_prefix=shard_prefix,
            )
        )
        if idx % 500 == 0:
            print_progress(f"{count_prefix}_train", idx, len(train))
    for idx, row in enumerate(eval_, start=1):
        eval_rows.append(
            convert_single_image_row(
                corpus_repo_id=corpus_repo_id,
                token=token,
                bundle_dir=bundle_dir,
                row=row,
                shard_prefix=shard_prefix,
            )
        )
        if idx % 500 == 0:
            print_progress(f"{count_prefix}_eval", idx, len(eval_))
    counts[f"{count_prefix}_train_rows"] = len(train)
    counts[f"{count_prefix}_eval_rows"] = len(eval_)
    print_progress(f"{count_prefix}_train", len(train), len(train))
    print_progress(f"{count_prefix}_eval", len(eval_), len(eval_))


def download_jsonl(repo_id: str, filename: str, token: str) -> list[dict[str, Any]]:
    path = hf_download(repo_id=repo_id, filename=filename, token=token)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sample_rows(rows: list[dict[str, Any]], count: int, rng: random.Random) -> list[dict[str, Any]]:
    return list(rows) if count >= len(rows) else rng.sample(rows, count)


def convert_pair_row(
    *,
    corpus_repo_id: str,
    token: str,
    bundle_dir: Path,
    row: dict[str, Any],
    shard_prefix: str,
    row_suffix: str,
) -> dict[str, Any]:
    baseline = copy_hf_image(
        corpus_repo_id, token, bundle_dir, f"{shard_prefix}/{row['baseline_image']}", shard_prefix
    )
    current = copy_hf_image(
        corpus_repo_id, token, bundle_dir, f"{shard_prefix}/{row['current_image']}", shard_prefix
    )
    messages = row["messages"]
    return {
        "record_id": f"{row['row_id']}__{row_suffix}",
        "case_id": row.get("source_record_id") or row.get("row_id"),
        "asset_id": (row.get("asset") or {}).get("asset_id"),
        "task_kind": "candidate_json_sft",
        "source_dataset": row.get("source_dataset"),
        "messages": [
            {"role": "system", "content": [{"type": "text", "text": messages[0]["content"]}]},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": clean_user_text(messages[1]["content"])},
                    {"type": "image", "image": baseline},
                    {"type": "image", "image": current},
                ],
            },
            {"role": "assistant", "content": [{"type": "text", "text": messages[2]["content"]}]},
        ],
    }


def convert_single_image_row(
    *,
    corpus_repo_id: str,
    token: str,
    bundle_dir: Path,
    row: dict[str, Any],
    shard_prefix: str,
) -> dict[str, Any]:
    image = copy_hf_image(
        corpus_repo_id, token, bundle_dir, f"{shard_prefix}/{row['image']}", shard_prefix
    )
    messages = row["messages"]
    return {
        "record_id": row["row_id"],
        "case_id": row.get("patch_id") or row.get("source_record_id") or row["row_id"],
        "asset_id": row.get("patch_id"),
        "task_kind": "candidate_json_sft",
        "source_dataset": row.get("source_dataset"),
        "messages": [
            {"role": "system", "content": [{"type": "text", "text": messages[0]["content"]}]},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": clean_user_text(messages[1]["content"])},
                    {"type": "image", "image": image},
                ],
            },
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": normalize_single_image_assistant(
                            row=row, text=messages[2]["content"]
                        ),
                    }
                ],
            },
        ],
    }


def copy_hf_image(
    repo_id: str, token: str, bundle_dir: Path, hf_path: str, local_prefix: str
) -> str:
    source = hf_download(repo_id=repo_id, filename=hf_path, token=token)
    rel = (
        Path("images")
        / local_prefix
        / Path(hf_path).relative_to(local_prefix).relative_to("images")
    )
    destination = bundle_dir / rel
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copy2(source, destination)
    return rel.as_posix()


def hf_download(*, repo_id: str, filename: str, token: str) -> Path:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            return Path(
                hf_hub_download(
                    repo_id=repo_id,
                    filename=filename,
                    repo_type="dataset",
                    token=token,
                    etag_timeout=60,
                )
            )
        except Exception as exc:  # pragma: no cover - network resilience
            last_error = exc
            print(
                f"hf_download_retry={attempt} filename={filename} error={type(exc).__name__}",
                flush=True,
            )
            time.sleep(3 * attempt)
    raise RuntimeError(f"failed to download {filename}") from last_error


def clean_user_text(text: str) -> str:
    return (
        text.replace("<image:baseline>", "Image 1 is the baseline/pre-event image.")
        .replace("<image:current>", "Image 2 is the current/post-event image.")
        .replace("<image>", "Image is attached.")
        .strip()
    )


def normalize_single_image_assistant(*, row: dict[str, Any], text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            json.loads(stripped)
            return stripped
        except json.JSONDecodeError:
            pass
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    tags = target.get("visible_evidence_tags")
    payload = {
        "bbox_norm": None,
        "bbox_quality": "null",
        "change_confidence": 0.0,
        "civilian_impact": "none_visible_from_single_context_image",
        "civilian_infrastructure_type": "land_cover_context",
        "evidence_strength": "none",
        "quality_warning": target.get(
            "quality_warning", "single_image_context_not_before_after_evidence"
        ),
        "rationale": (
            "Single-image remote-sensing context row; "
            "not direct before/after disruption evidence."
        ),
        "scene_description": stripped,
        "source_led_context": "generic remote-sensing context row",
        "triage_action": "discard",
        "visibility_quality": "context_only",
        "visual_evidence_tags": (
            tags if isinstance(tags, list) and tags else tags_from_text(stripped)
        ),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def tags_from_text(text: str) -> list[str]:
    lower = text.lower()
    tags = []
    for needle, tag in (
        ("water", "water_body"),
        ("building", "buildings"),
        ("road", "roads"),
        ("agric", "agricultural_land"),
        ("forest", "vegetation"),
        ("cloud", "cloud_or_haze"),
        ("urban", "urban_area"),
    ):
        if needle in lower:
            tags.append(tag)
    return tags or ["land_cover_context"]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def build_leap_config(*, job_spec: dict[str, Any], bundle_dir: Path) -> dict[str, Any]:
    return {
        "project_name": job_spec["project_name"],
        "model_name": str(job_spec["model_id"]).split("/", 1)[-1],
        "training_type": "vlm_sft",
        "dataset": {
            "path": str((bundle_dir / "train.jsonl").resolve()),
            "type": "vlm_sft",
            "test_size": job_spec["dataset_test_size"],
            "image_root": str(bundle_dir.resolve()),
        },
        "training_config": dict(job_spec["training_config"]),
        "peft_config": dict(job_spec["peft_config"]),
    }


def clone_leap_finetune(*, workspace: Path, repo_url: str, ref: str) -> Path:
    repo_dir = workspace / "leap-finetune"
    subprocess.run(["git", "clone", "--depth", "1", repo_url, str(repo_dir)], check=True)
    subprocess.run(["git", "-C", str(repo_dir), "checkout", ref], check=True)
    return repo_dir


def sanitize_leap_repo_for_hf_jobs(*, repo_dir: Path) -> None:
    pyproject_path = repo_dir / "pyproject.toml"
    pyproject = pyproject_path.read_text(encoding="utf-8")
    patched = pyproject
    for dependency_name in ("flash-attn", "deepspeed"):
        patched = re.sub(
            rf'^\s*"{re.escape(dependency_name)}>=.*\n', "", patched, flags=re.MULTILINE
        )
    if patched != pyproject:
        pyproject_path.write_text(patched, encoding="utf-8")
    lockfile = repo_dir / "uv.lock"
    if lockfile.exists():
        lockfile.unlink()
    patch_text_file(
        repo_dir / "src/leap_finetune/utils/logging_utils.py",
        "except ImportError:",
        "except Exception:",
    )
    patch_text_file(
        repo_dir / "src/leap_finetune/training_configs/vlm_sft_config.py",
        '    "deepspeed": DEEPSPEED_CONFIG,\n',
        "",
    )
    patch_text_file(
        repo_dir / "src/leap_finetune/utils/checkpoint_callback.py",
        "from ray import train\n",
        "from ray import train\nfrom ray.train import Checkpoint\n",
    )
    patch_text_file(
        repo_dir / "src/leap_finetune/utils/checkpoint_callback.py",
        "    ) -> None:\n        if train.get_context().get_world_rank() == 0:\n",
        (
            "    ) -> None:\n"
            "        checkpoint_path = None\n"
            "        if train.get_context().get_world_rank() == 0:\n"
        ),
    )
    patch_text_file(
        repo_dir / "src/leap_finetune/utils/checkpoint_callback.py",
        (
            "        # Report metrics only — HF Trainer already saved checkpoint to output_dir.\n"
            "        # Passing checkpoint=None avoids Ray duplicating files into ray_logs/.\n"
            "        train.report(metrics=report_metrics, checkpoint=None)\n"
        ),
        (
            "        checkpoint = None\n"
            "        if checkpoint_path and pathlib.Path(checkpoint_path).exists():\n"
            "            checkpoint = Checkpoint.from_directory(checkpoint_path)\n"
            "        train.report(metrics=report_metrics, checkpoint=checkpoint)\n"
        ),
    )


def patch_text_file(path: Path, before: str, after: str) -> None:
    if path.exists():
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace(before, after), encoding="utf-8")


def run_leap_train(*, repo_dir: Path, config_path: Path, output_dir: str) -> None:
    env = os.environ.copy()
    env["OUTPUT_DIR"] = output_dir
    try:
        subprocess.run(
            ["uv", "run", "--directory", str(repo_dir), "leap-finetune", str(config_path)],
            check=True,
            env=env,
        )
    except subprocess.CalledProcessError:
        env["PYTHONPATH"] = str((repo_dir / "src").resolve())
        subprocess.run(
            [
                "uv",
                "run",
                "--directory",
                str(repo_dir),
                "python",
                "-c",
                "from leap_finetune import main; main()",
                str(config_path),
            ],
            check=True,
            env=env,
        )


def maybe_publish_adapter_artifacts(
    *,
    workspace: Path,
    output_dir: Path,
    repo_id: str,
    private: bool,
    base_model_id: str,
    run_name: str,
    corpus_repo_id: str,
    bundle_dir: Path,
) -> None:
    checkpoint_dir = find_latest_checkpoint_dir(output_dir)
    publish_dir = workspace / "publish_adapter"
    publish_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for filename in ADAPTER_PUBLISH_FILES:
        source = checkpoint_dir / filename
        if source.exists():
            copy2(source, publish_dir / filename)
            copied += 1
    if copied == 0:
        raise FileNotFoundError(f"no adapter files found in {checkpoint_dir}")
    validate_published_adapter_dir(publish_dir=publish_dir, checkpoint_dir=checkpoint_dir)
    trainer_state = read_json_if_exists(checkpoint_dir / "trainer_state.json")
    summary = read_json_if_exists(bundle_dir / "summary.json")
    (publish_dir / "README.md").write_text(
        build_model_card(repo_id, base_model_id, run_name, corpus_repo_id, summary, trainer_state),
        encoding="utf-8",
    )
    (publish_dir / "training_output_manifest.json").write_text(
        json.dumps(
            {
                "run_name": run_name,
                "base_model_id": base_model_id,
                "corpus_repo_id": corpus_repo_id,
                "adapter_repo_id": repo_id,
                "checkpoint_name": checkpoint_dir.name,
                "bundle_summary": summary,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    api = HfApi(token=os.environ.get("HF_TOKEN"))
    api.create_repo(repo_id=repo_id, repo_type="model", private=private, exist_ok=True)
    api.upload_folder(
        repo_id=repo_id,
        repo_type="model",
        folder_path=str(publish_dir),
        commit_message=f"Upload Blackline adapter artifacts for {run_name}",
    )
    print(f"published_adapter_repo_id={repo_id}", flush=True)


def find_latest_checkpoint_dir(output_dir: Path) -> Path:
    dirs = sorted(
        [p for p in output_dir.rglob("checkpoint*") if p.is_dir()],
        key=lambda p: (checkpoint_sort_key(p), p.stat().st_mtime),
        reverse=True,
    )
    if dirs:
        return dirs[0]
    adapter_dirs = sorted(
        [p.parent for p in output_dir.rglob("adapter_config.json") if p.parent.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if adapter_dirs:
        return adapter_dirs[0]
    raise FileNotFoundError(f"no checkpoint directories found under {output_dir}")


def checkpoint_sort_key(path: Path) -> int:
    match = re.search(r"(\d+)$", path.name)
    return int(match.group(1)) if match else -1


def validate_published_adapter_dir(*, publish_dir: Path, checkpoint_dir: Path) -> None:
    missing = [
        filename for filename in ADAPTER_REQUIRED_FILES if not (publish_dir / filename).exists()
    ]
    if missing:
        raise FileNotFoundError(f"adapter missing required files {missing} in {checkpoint_dir}")
    if not any((publish_dir / filename).exists() for filename in ADAPTER_WEIGHT_FILES):
        raise FileNotFoundError(f"adapter checkpoint missing weights in {checkpoint_dir}")


def read_json_if_exists(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_model_card(
    repo_id: str,
    base_model_id: str,
    run_name: str,
    corpus_repo_id: str,
    summary: dict[str, Any],
    trainer_state: dict[str, Any],
) -> str:
    final_eval = None
    for entry in trainer_state.get("log_history", []):
        if "eval_loss" in entry:
            final_eval = entry["eval_loss"]
    return "\n".join(
        [
            "---",
            "library_name: peft",
            f"base_model: {base_model_id}",
            "tags:",
            "- blackline-atlas",
            "- lfm2.5-vl",
            "- satellite-imagery",
            "- civilian-disruption-triage",
            f"datasets:\n- {corpus_repo_id}",
            "license: other",
            "---",
            "",
            f"# {repo_id}",
            "",
            (
                f"PEFT LoRA adapter for `{base_model_id}` trained for Blackline "
                "Atlas civilian disruption evidence reporting."
            ),
            "",
            f"- Run: `{run_name}`",
            f"- Corpus: `{corpus_repo_id}`",
            f"- Train rows: `{summary.get('train_records')}`",
            f"- Eval rows packaged: `{summary.get('eval_records')}`",
            f"- Image files materialized: `{summary.get('image_files')}`",
            f"- Final trainer eval loss: `{final_eval}`",
            "",
            (
                "Promotion note: this adapter must still pass the frozen Blackline "
                "held-out SimSat/product smoke gate before being treated as "
                "production-selected."
            ),
            "",
        ]
    )


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    import yaml

    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def parse_bool_arg(value: str) -> bool:
    return value.strip().lower() not in {"0", "false", "no", "off"}


def print_progress(label: str, done: int, total: int) -> None:
    print(f"progress={label} done={done} total={total}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
