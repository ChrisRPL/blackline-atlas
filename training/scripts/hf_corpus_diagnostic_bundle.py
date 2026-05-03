from __future__ import annotations

import json
import random
import shutil
import tarfile
from pathlib import Path
from typing import Any

from huggingface_hub import hf_hub_download, snapshot_download

ROOT = Path(__file__).resolve().parents[2]
MODEL_ID = "LiquidAI/LFM2.5-VL-450M"
RANDOM_SEED = 42


def materialize_bundle(
    *,
    corpus_repo_id: str,
    run_name: str,
    run_dir: Path,
    bundle_dir: Path,
    token: str,
    force: bool,
    simsat_repeat: int,
    include_initial_vlm: bool,
    initial_vlm_train_rows: int,
    initial_vlm_eval_rows: int,
    bigearthnet_train_rows: int,
    chatearthnet_train_rows: int,
    context_eval_rows: int,
    prefetch_shards: bool = False,
) -> None:
    if bundle_dir.exists():
        if not force:
            raise FileExistsError(f"{bundle_dir} exists; pass --force")
        if not _safe_to_remove(bundle_dir):
            raise ValueError(f"refusing to remove unsafe bundle dir: {bundle_dir}")
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(RANDOM_SEED)

    train_rows: list[dict[str, Any]] = []
    eval_rows: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}
    shard_prefixes = [
        "vlm_evidence_sft_simsat_gold_v1",
        "vlm_evidence_sft_bigearthnet_s2_chunk_01",
        "vlm_evidence_sft_chatearthnet_chunk_02",
    ]
    if include_initial_vlm:
        shard_prefixes.append("vlm_evidence_sft")
    snapshot_root = (
        prefetch_corpus_shards(
            corpus_repo_id=corpus_repo_id,
            token=token,
            shard_prefixes=shard_prefixes,
        )
        if prefetch_shards
        else None
    )

    simsat_train = download_jsonl(
        corpus_repo_id,
        "vlm_evidence_sft_simsat_gold_v1/train.jsonl",
        token,
        snapshot_root=snapshot_root,
    )
    simsat_eval = download_jsonl(
        corpus_repo_id,
        "vlm_evidence_sft_simsat_gold_v1/eval.jsonl",
        token,
        snapshot_root=snapshot_root,
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
                    snapshot_root=snapshot_root,
                )
            )
    for row in simsat_eval:
        eval_rows.append(
            convert_pair_row(
                corpus_repo_id=corpus_repo_id,
                token=token,
                bundle_dir=bundle_dir,
                row=row,
                shard_prefix="vlm_evidence_sft_simsat_gold_v1",
                row_suffix="heldout",
                snapshot_root=snapshot_root,
            )
        )
    source_counts["simsat_gold_train_repeated_rows"] = len(train_rows)
    source_counts["simsat_gold_eval_rows"] = len(eval_rows)

    if include_initial_vlm:
        initial_train = sample_rows(
            download_jsonl(
                corpus_repo_id,
                "vlm_evidence_sft/train.jsonl",
                token,
                snapshot_root=snapshot_root,
            ),
            initial_vlm_train_rows,
            rng,
        )
        initial_eval = sample_rows(
            download_jsonl(
                corpus_repo_id,
                "vlm_evidence_sft/eval.jsonl",
                token,
                snapshot_root=snapshot_root,
            ),
            initial_vlm_eval_rows,
            rng,
        )
        for row in initial_train:
            train_rows.append(
                convert_single_image_row(
                    corpus_repo_id=corpus_repo_id,
                    token=token,
                    bundle_dir=bundle_dir,
                    row=row,
                    shard_prefix="vlm_evidence_sft",
                    snapshot_root=snapshot_root,
                )
            )
        for row in initial_eval:
            eval_rows.append(
                convert_single_image_row(
                    corpus_repo_id=corpus_repo_id,
                    token=token,
                    bundle_dir=bundle_dir,
                    row=row,
                    shard_prefix="vlm_evidence_sft",
                    snapshot_root=snapshot_root,
                )
            )
        source_counts["initial_vlm_train_rows"] = len(initial_train)
        source_counts["initial_vlm_eval_rows"] = len(initial_eval)

    big_train = sample_rows(
        download_jsonl(
            corpus_repo_id,
            "vlm_evidence_sft_bigearthnet_s2_chunk_01/train.jsonl",
            token,
            snapshot_root=snapshot_root,
        ),
        bigearthnet_train_rows,
        rng,
    )
    chat_train = sample_rows(
        download_jsonl(
            corpus_repo_id,
            "vlm_evidence_sft_chatearthnet_chunk_02/train.jsonl",
            token,
            snapshot_root=snapshot_root,
        ),
        chatearthnet_train_rows,
        rng,
    )
    big_eval = sample_rows(
        download_jsonl(
            corpus_repo_id,
            "vlm_evidence_sft_bigearthnet_s2_chunk_01/eval.jsonl",
            token,
            snapshot_root=snapshot_root,
        ),
        context_eval_rows,
        rng,
    )
    chat_eval = sample_rows(
        download_jsonl(
            corpus_repo_id,
            "vlm_evidence_sft_chatearthnet_chunk_02/eval.jsonl",
            token,
            snapshot_root=snapshot_root,
        ),
        context_eval_rows,
        rng,
    )

    for row in big_train:
        train_rows.append(
            convert_single_image_row(
                corpus_repo_id=corpus_repo_id,
                token=token,
                bundle_dir=bundle_dir,
                row=row,
                shard_prefix="vlm_evidence_sft_bigearthnet_s2_chunk_01",
                snapshot_root=snapshot_root,
            )
        )
    for row in chat_train:
        train_rows.append(
            convert_single_image_row(
                corpus_repo_id=corpus_repo_id,
                token=token,
                bundle_dir=bundle_dir,
                row=row,
                shard_prefix="vlm_evidence_sft_chatearthnet_chunk_02",
                snapshot_root=snapshot_root,
            )
        )
    for row in big_eval:
        eval_rows.append(
            convert_single_image_row(
                corpus_repo_id=corpus_repo_id,
                token=token,
                bundle_dir=bundle_dir,
                row=row,
                shard_prefix="vlm_evidence_sft_bigearthnet_s2_chunk_01",
                snapshot_root=snapshot_root,
            )
        )
    for row in chat_eval:
        eval_rows.append(
            convert_single_image_row(
                corpus_repo_id=corpus_repo_id,
                token=token,
                bundle_dir=bundle_dir,
                row=row,
                shard_prefix="vlm_evidence_sft_chatearthnet_chunk_02",
                snapshot_root=snapshot_root,
            )
        )
    source_counts["bigearthnet_train_rows"] = len(big_train)
    source_counts["chatearthnet_train_rows"] = len(chat_train)
    source_counts["bigearthnet_eval_rows"] = len(big_eval)
    source_counts["chatearthnet_eval_rows"] = len(chat_eval)

    write_jsonl(bundle_dir / "train.jsonl", train_rows)
    write_jsonl(bundle_dir / "eval.jsonl", eval_rows)
    write_summary_files(
        corpus_repo_id=corpus_repo_id,
        run_name=run_name,
        run_dir=run_dir,
        bundle_dir=bundle_dir,
        train_rows=train_rows,
        eval_rows=eval_rows,
        source_counts=source_counts,
    )


def write_summary_files(
    *,
    corpus_repo_id: str,
    run_name: str,
    run_dir: Path,
    bundle_dir: Path,
    train_rows: list[dict[str, Any]],
    eval_rows: list[dict[str, Any]],
    source_counts: dict[str, int],
) -> None:
    summary = {
        "run_name": run_name,
        "source_corpus_repo_id": corpus_repo_id,
        "train_records": len(train_rows),
        "eval_records": len(eval_rows),
        "source_split_counts": source_counts,
        "strategy": (
            "SimSat gold is oversampled for Blackline-specific schema and evidence "
            "behavior; BigEarthNet/ChatEarthNet rows provide Sentinel context and "
            "non-conflict hard negatives."
        ),
    }
    (bundle_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    dataset_manifest = {
        "version": "blackline-hf-corpus-diagnostic-v1",
        "run_name": run_name,
        "model_id": MODEL_ID,
        "source_corpus_repo_id": corpus_repo_id,
        "leap_train_dataset": str((bundle_dir / "train.jsonl").resolve()),
        "leap_eval_dataset": str((bundle_dir / "eval.jsonl").resolve()),
        "leap_summary": str((bundle_dir / "summary.json").resolve()),
        "image_root": str(bundle_dir.resolve()),
        "train_records": len(train_rows),
        "eval_records": len(eval_rows),
        "source_split_counts": source_counts,
    }
    (bundle_dir / "dataset_manifest.json").write_text(
        json.dumps(dataset_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    archive_path = run_dir / f"{run_name}_trainer_bundle.tar.gz"
    if archive_path.exists():
        archive_path.unlink()
    with tarfile.open(archive_path, mode="w:gz") as tar:
        tar.add(bundle_dir, arcname=bundle_dir.name)
    bundle_manifest = {
        "version": "blackline-hf-corpus-train-bundle-v1",
        "run_name": run_name,
        "backend": "leap_finetune",
        "dataset_manifest": str((bundle_dir / "dataset_manifest.json").resolve()),
        "train_jsonl": str((bundle_dir / "train.jsonl").resolve()),
        "eval_jsonl": str((bundle_dir / "eval.jsonl").resolve()),
        "summary_json": str((bundle_dir / "summary.json").resolve()),
        "image_root": str(bundle_dir.resolve()),
        "bundle_dir": str(bundle_dir.resolve()),
        "bundle_archive": str(archive_path.resolve()),
        "train_records": len(train_rows),
        "eval_records": len(eval_rows),
        "authoritative_eval_note": (
            "Diagnostic only. Promote only if held-out SimSat gold eval produces strict "
            "JSON, sane discard/downlink behavior, and no false-positive regression."
        ),
        "uploaded_bundle_repo_id": None,
        "uploaded_bundle_path": None,
        "last_submit_status": None,
        "last_submit_error": None,
    }
    (bundle_dir / "bundle_manifest.json").write_text(
        json.dumps(bundle_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def prefetch_corpus_shards(
    *,
    corpus_repo_id: str,
    token: str,
    shard_prefixes: list[str],
) -> Path:
    return Path(
        snapshot_download(
            repo_id=corpus_repo_id,
            repo_type="dataset",
            token=token,
            allow_patterns=[f"{prefix}/**" for prefix in shard_prefixes],
            max_workers=16,
        )
    )


def download_jsonl(
    repo_id: str,
    filename: str,
    token: str,
    *,
    snapshot_root: Path | None,
) -> list[dict[str, Any]]:
    local_path = snapshot_root / filename if snapshot_root is not None else None
    path = (
        local_path
        if local_path is not None and local_path.exists()
        else Path(
            hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                repo_type="dataset",
                token=token,
            )
        )
    )
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sample_rows(rows: list[dict[str, Any]], count: int, rng: random.Random) -> list[dict[str, Any]]:
    if count >= len(rows):
        return list(rows)
    return rng.sample(rows, count)


def convert_pair_row(
    *,
    corpus_repo_id: str,
    token: str,
    bundle_dir: Path,
    row: dict[str, Any],
    shard_prefix: str,
    row_suffix: str,
    snapshot_root: Path | None,
) -> dict[str, Any]:
    baseline = copy_hf_image(
        repo_id=corpus_repo_id,
        token=token,
        bundle_dir=bundle_dir,
        hf_path=f"{shard_prefix}/{row['baseline_image']}",
        local_prefix=shard_prefix,
        snapshot_root=snapshot_root,
    )
    current = copy_hf_image(
        repo_id=corpus_repo_id,
        token=token,
        bundle_dir=bundle_dir,
        hf_path=f"{shard_prefix}/{row['current_image']}",
        local_prefix=shard_prefix,
        snapshot_root=snapshot_root,
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
    snapshot_root: Path | None,
) -> dict[str, Any]:
    image = copy_hf_image(
        repo_id=corpus_repo_id,
        token=token,
        bundle_dir=bundle_dir,
        hf_path=f"{shard_prefix}/{row['image']}",
        local_prefix=shard_prefix,
        snapshot_root=snapshot_root,
    )
    messages = row["messages"]
    assistant_text = normalize_single_image_assistant(row=row, text=messages[2]["content"])
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
            {"role": "assistant", "content": [{"type": "text", "text": assistant_text}]},
        ],
    }


def copy_hf_image(
    *,
    repo_id: str,
    token: str,
    bundle_dir: Path,
    hf_path: str,
    local_prefix: str,
    snapshot_root: Path | None,
) -> str:
    local_path = snapshot_root / hf_path if snapshot_root is not None else None
    source = (
        local_path
        if local_path is not None and local_path.exists()
        else Path(
            hf_hub_download(repo_id=repo_id, filename=hf_path, repo_type="dataset", token=token)
        )
    )
    shard_image_path = Path(hf_path).relative_to(local_prefix).relative_to("images")
    rel = Path("images") / local_prefix / shard_image_path
    destination = bundle_dir / rel
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copy2(source, destination)
    return rel.as_posix()


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
    visible_tags = target.get("visible_evidence_tags")
    if not isinstance(visible_tags, list) or not visible_tags:
        visible_tags = _tags_from_text(stripped)
    payload = {
        "bbox_norm": None,
        "bbox_quality": "null",
        "change_confidence": 0.0,
        "civilian_impact": "none_visible_from_single_context_image",
        "civilian_infrastructure_type": "land_cover_context",
        "evidence_strength": "none",
        "quality_warning": target.get(
            "quality_warning",
            "single_image_context_not_before_after_evidence",
        ),
        "rationale": (
            "Single-image remote-sensing context row. It can teach land-cover and "
            "visibility language, but it is not direct before/after disruption evidence."
        ),
        "scene_description": stripped,
        "source_led_context": "generic remote-sensing context row",
        "triage_action": "discard",
        "visibility_quality": "context_only",
        "visual_evidence_tags": visible_tags,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _tags_from_text(text: str) -> list[str]:
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


def _safe_to_remove(path: Path) -> bool:
    allowed_root = (ROOT / "training" / "eval_runs").resolve()
    return allowed_root in path.resolve().parents
