from __future__ import annotations

import argparse
import io
import json
import random
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import tifffile
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PARQUET = ROOT / "work" / "external" / "hf" / "bigearthnet_txt" / "BigEarthNet.txt.parquet"
DEFAULT_ARCHIVE = Path("/Users/krzysztof/Downloads/BigEarthNet-S2.tar.zst")
DEFAULT_OUTPUT = ROOT / "work" / "hf_chunks" / "bigearthnet_s2_chunk_01"
RANDOM_SEED = 42
RGB_BANDS = {"B02", "B03", "B04"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a bounded BigEarthNet-S2 VLM SFT chunk without unpacking " "the full archive."
        )
    )
    parser.add_argument("--parquet", type=Path, default=DEFAULT_PARQUET)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-patches", type=int, default=2000)
    parser.add_argument("--max-qa-per-patch", type=int, default=10)
    parser.add_argument("--eval-ratio", type=float, default=0.1)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _validate_inputs(args)
    if args.output_root.exists():
        if not args.force:
            raise FileExistsError(f"{args.output_root} exists; pass --force")
        if not _safe_to_remove(args.output_root):
            raise ValueError(f"refusing to remove unsafe path: {args.output_root}")
        shutil.rmtree(args.output_root)
    images_dir = args.output_root / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    qa_by_patch = _load_patch_questions(args.parquet, args.max_patches, args.max_qa_per_patch)
    target_patches = set(qa_by_patch)
    written_images = _extract_rgb_images(
        archive=args.archive,
        images_dir=images_dir,
        target_patches=target_patches,
        image_size=args.image_size,
    )
    rows = _build_rows(qa_by_patch=qa_by_patch, written_images=written_images)
    splits = _split_rows(rows, eval_ratio=args.eval_ratio)
    _write_jsonl(args.output_root / "train.jsonl", splits["train"])
    _write_jsonl(args.output_root / "eval.jsonl", splits["eval"])

    metadata = {
        "name": "bigearthnet_s2_chunk_01",
        "source_dataset": "BIFOLD-BigEarthNetv2-0/BigEarthNet.txt + local BigEarthNet-S2 archive",
        "source_parquet": str(args.parquet),
        "source_archive": str(args.archive),
        "policy": {
            "purpose": "VLM Sentinel-2 visual literacy and hard-negative calibration",
            "raw_mirror": False,
            "tactical_targeting_excluded": True,
            "per_row_license_required": True,
        },
        "counts": {
            "requested_patches": len(target_patches),
            "written_images": len(written_images),
            "rows_total": len(rows),
            "rows_train": len(splits["train"]),
            "rows_eval": len(splits["eval"]),
        },
        "license_note": (
            "Text rows originate from BigEarthNet.txt. Derived RGB PNGs are generated from the "
            "user-provided BigEarthNet-S2 archive and kept private in the Blackline corpus. "
            "Verify upstream imagery redistribution terms before public release."
        ),
    }
    (args.output_root / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )
    (args.output_root / "README.md").write_text(_readme(metadata), encoding="utf-8")
    print(json.dumps(metadata["counts"], indent=2, sort_keys=True))
    print(f"wrote {args.output_root}")
    return 0


def _validate_inputs(args: argparse.Namespace) -> None:
    if not args.parquet.exists():
        raise FileNotFoundError(args.parquet)
    if not args.archive.exists():
        raise FileNotFoundError(args.archive)
    if args.max_patches < 1:
        raise ValueError("--max-patches must be positive")
    if args.max_qa_per_patch < 1:
        raise ValueError("--max-qa-per-patch must be positive")
    if not 0 < args.eval_ratio < 0.5:
        raise ValueError("--eval-ratio must be between 0 and 0.5")


def _safe_to_remove(path: Path) -> bool:
    work_root = (ROOT / "work").resolve()
    return work_root in path.resolve().parents


def _load_patch_questions(
    parquet_path: Path,
    max_patches: int,
    max_qa_per_patch: int,
) -> dict[str, list[dict[str, Any]]]:
    columns = [
        "ID",
        "patch_id",
        "input",
        "output",
        "split",
        "latitude",
        "longitude",
        "country",
        "season",
    ]
    df = pd.read_parquet(parquet_path, columns=columns)
    qa_by_patch: dict[str, list[dict[str, Any]]] = {}
    for patch_id, group in df.groupby("patch_id", sort=False):
        records = group.head(max_qa_per_patch).to_dict(orient="records")
        qa_by_patch[str(patch_id)] = records
        if len(qa_by_patch) >= max_patches:
            break
    return qa_by_patch


def _extract_rgb_images(
    *,
    archive: Path,
    images_dir: Path,
    target_patches: set[str],
    image_size: int,
) -> set[str]:
    proc = subprocess.Popen(
        ["zstd", "-dcq", str(archive)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.stdout is None:
        raise RuntimeError("failed to open zstd stdout")
    pending: dict[str, dict[str, np.ndarray]] = defaultdict(dict)
    written: set[str] = set()
    long_name: str | None = None
    try:
        while len(written) < len(target_patches):
            header = proc.stdout.read(512)
            if not header or header == b"\0" * 512:
                break
            name = _tar_name(header)
            size = _tar_size(header)
            file_type = header[156:157].decode("ascii", "ignore") or "0"
            block_size = ((size + 511) // 512) * 512
            if file_type == "L":
                data = proc.stdout.read(block_size)
                long_name = data[:size].rstrip(b"\0").decode("utf-8", "replace")
                continue
            if long_name is not None:
                name = long_name
                long_name = None
            if _is_target_band(name):
                data = proc.stdout.read(block_size)[:size]
                patch_id, band = _patch_and_band(name)
                if patch_id in target_patches and patch_id not in written:
                    pending[patch_id][band] = tifffile.imread(io.BytesIO(data))
                    if RGB_BANDS <= pending[patch_id].keys():
                        _write_rgb_png(
                            path=images_dir / f"{patch_id}.png",
                            red=pending[patch_id]["B04"],
                            green=pending[patch_id]["B03"],
                            blue=pending[patch_id]["B02"],
                            image_size=image_size,
                        )
                        written.add(patch_id)
                        pending.pop(patch_id, None)
                continue
            _skip(proc.stdout, block_size)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
    return written


def _tar_name(header: bytes) -> str:
    name = header[:100].rstrip(b"\0").decode("utf-8", "replace")
    prefix = header[345:500].rstrip(b"\0").decode("utf-8", "replace")
    return f"{prefix}/{name}" if prefix else name


def _tar_size(header: bytes) -> int:
    size_oct = header[124:136].rstrip(b"\0 ").decode("ascii", "ignore")
    return int(size_oct or "0", 8)


def _skip(stream: Any, size: int) -> None:
    remaining = size
    while remaining:
        chunk = stream.read(min(remaining, 1024 * 1024))
        if not chunk:
            return
        remaining -= len(chunk)


def _is_target_band(name: str) -> bool:
    return name.endswith(("_B02.tif", "_B03.tif", "_B04.tif"))


def _patch_and_band(name: str) -> tuple[str, str]:
    stem = Path(name).stem
    patch_id, band = stem.rsplit("_", 1)
    return patch_id, band


def _write_rgb_png(
    *,
    path: Path,
    red: np.ndarray,
    green: np.ndarray,
    blue: np.ndarray,
    image_size: int,
) -> None:
    rgb = np.stack([_scale_band(red), _scale_band(green), _scale_band(blue)], axis=-1)
    image = Image.fromarray(rgb, mode="RGB")
    if image.size != (image_size, image_size):
        image = image.resize((image_size, image_size), Image.Resampling.BICUBIC)
    image.save(path, optimize=True)


def _scale_band(band: np.ndarray) -> np.ndarray:
    band = band.astype(np.float32)
    low, high = np.percentile(band, [2, 98])
    if high <= low:
        high = float(band.max() or 1.0)
        low = float(band.min())
    scaled = (band - low) / max(high - low, 1.0)
    return (np.clip(scaled, 0.0, 1.0) * 255).astype(np.uint8)


def _build_rows(
    *,
    qa_by_patch: dict[str, list[dict[str, Any]]],
    written_images: set[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for patch_id, qa_rows in qa_by_patch.items():
        if patch_id not in written_images:
            continue
        image_path = f"images/{patch_id}.png"
        for qa in qa_rows:
            rows.append(
                {
                    "row_id": f"bigearthnet_s2_{qa['ID']}",
                    "image": image_path,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a civilian remote-sensing analyst. Answer from visible "
                                "satellite evidence only. Do not infer conflict, casualties, "
                                "military targets, or attribution from generic land-cover imagery."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                "<image>\n"
                                "Use the Sentinel-2 image to answer the land-cover question. "
                                f"Question: {qa['input']}"
                            ),
                        },
                        {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "answer": str(qa["output"]).strip(),
                                    "visible_evidence_tags": _tags_for_question(str(qa["input"])),
                                    "satellite_relevance": "generic_remote_sensing_context",
                                    "conflict_evidence": "not_present_in_source_label",
                                    "quality_warning": (
                                        "This is land-cover training data, not "
                                        "conflict-event evidence."
                                    ),
                                    "triage_action": "discard",
                                },
                                sort_keys=True,
                            ),
                        },
                    ],
                    "source_dataset": "BIFOLD-BigEarthNetv2-0/BigEarthNet.txt + BigEarthNet-S2",
                    "source_license": "verify_upstream_imagery_terms_before_public_release",
                    "source_record_id": str(qa["ID"]),
                    "source_split": str(qa["split"]),
                    "patch_id": patch_id,
                    "latitude": float(qa["latitude"]),
                    "longitude": float(qa["longitude"]),
                    "country": str(qa["country"]),
                    "season": str(qa["season"]),
                    "redistribution_status": "private_derived_rgb_png",
                }
            )
    return rows


def _tags_for_question(question: str) -> list[str]:
    lowered = question.lower()
    candidates = [
        "arable land",
        "pastures",
        "broad-leaved forest",
        "coniferous forest",
        "urban fabric",
        "industrial",
        "water",
        "wetlands",
        "transport",
        "mineral extraction",
    ]
    tags = [candidate.replace(" ", "_") for candidate in candidates if candidate in lowered]
    return tags or ["land_cover_context"]


def _split_rows(rows: list[dict[str, Any]], eval_ratio: float) -> dict[str, list[dict[str, Any]]]:
    rng = random.Random(RANDOM_SEED)
    rows = list(rows)
    rng.shuffle(rows)
    eval_count = max(1, int(len(rows) * eval_ratio))
    return {"train": rows[eval_count:], "eval": rows[:eval_count]}


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _readme(metadata: dict[str, Any]) -> str:
    counts = metadata["counts"]
    return f"""# BigEarthNet-S2 Chunk 01

Bounded add-on shard for `ChrisRPL/blackline-atlas-training-corpus-v1`.

This shard adds Sentinel-2 land-cover visual literacy and hard-negative
calibration rows. It is not conflict evidence and should not be used to claim
that a conflict occurred.

## Counts

- images: {counts["written_images"]}
- rows total: {counts["rows_total"]}
- train rows: {counts["rows_train"]}
- eval rows: {counts["rows_eval"]}

## Purpose

- improve generic Sentinel-2 scene understanding
- teach the model to answer from visible evidence only
- reduce over-firing on ordinary land-cover imagery
- reinforce safe `discard` behavior when no event source supports conflict

## License Note

{metadata["license_note"]}
"""


if __name__ == "__main__":
    raise SystemExit(main())
