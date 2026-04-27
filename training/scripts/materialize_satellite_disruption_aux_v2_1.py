from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datasets import load_dataset  # noqa: E402
from PIL import Image  # noqa: E402

from app.schemas.evidence_candidate import EvidenceFirstCandidate  # noqa: E402

DEFAULT_SOURCE_ROOT = ROOT / "satellite-disruption-triage-aux-v2"
DEFAULT_OUTPUT_ROOT = ROOT / "work" / "dataset_v21" / "satellite-disruption-triage-aux-v2-1"
DATASET_REPO = "ChrisRPL/satellite-disruption-triage-aux-v2"
INCLUDE_SOURCE = "GabeT29/BRIGHT-XView2Format"
UNKNOWN_LICENSE_SOURCE = "mespinosami/sen12mscr"
UNRESOLVABLE_SOURCE = "sda-kr/xbd-ukraine"
SYNTHETIC_SOURCE = "synthetic_curated"
FLAT_FILES = ("train_flat.jsonl", "eval_flat.jsonl", "eval_calibration_flat.jsonl")
MAX_IMAGE_SIZE = 512


@dataclass(frozen=True)
class RowSelection:
    included: list[dict[str, Any]]
    synthetic: list[dict[str, Any]]
    excluded: list[dict[str, Any]]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Repair satellite-disruption-triage-aux-v2 into a self-contained v2.1 "
            "real-image subset for diagnostic VLM SFT."
        )
    )
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--max-image-size", type=int, default=MAX_IMAGE_SIZE)
    parser.add_argument(
        "--skip-image-materialization",
        action="store_true",
        help="Only rewrite metadata files. Intended for debugging.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_root = args.source_root
    output_root = args.output_root
    if not source_root.exists():
        raise FileNotFoundError(
            f"{source_root} does not exist. Download {DATASET_REPO} first, or pass --source-root."
        )

    if not _is_safe_generated_output(output_root):
        raise ValueError(f"refusing to overwrite unsafe output path: {output_root}")
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    rows_by_file = {filename: _load_jsonl(source_root / filename) for filename in FLAT_FILES}
    selection = _select_rows(rows_by_file)
    materialized = _rewrite_included_rows(
        rows_by_file=rows_by_file,
        included_ids={row["row_id"] for row in selection.included},
        output_root=output_root,
        max_image_size=args.max_image_size,
        skip_image_materialization=args.skip_image_materialization,
    )

    _write_flat_files(output_root=output_root, rows_by_file=materialized)
    _write_sft_files(output_root=output_root, rows_by_file=materialized)
    _write_excluded_files(output_root=output_root, selection=selection)
    validation = _validate_output(output_root=output_root, rows_by_file=materialized)
    _write_metadata(
        output_root=output_root,
        rows_by_file=materialized,
        selection=selection,
        validation=validation,
    )
    _write_validation_report(output_root=output_root, validation=validation, selection=selection)
    _write_source_audit(output_root=output_root, selection=selection)
    _write_readme(output_root=output_root, rows_by_file=materialized, validation=validation)
    _write_gitattributes(output_root=output_root)

    print(json.dumps(validation["summary"], indent=2, sort_keys=True))
    print(f"wrote {output_root}")
    return 0 if validation["overall_pass"] else 1


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _is_safe_generated_output(path: Path) -> bool:
    resolved = path.resolve()
    work_root = (ROOT / "work").resolve()
    return resolved == DEFAULT_OUTPUT_ROOT.resolve() or work_root in resolved.parents


def _select_rows(rows_by_file: dict[str, list[dict[str, Any]]]) -> RowSelection:
    included: list[dict[str, Any]] = []
    synthetic: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for filename, rows in rows_by_file.items():
        for row in rows:
            row = dict(row)
            row["_source_file"] = filename
            source = row.get("source_dataset")
            if source == INCLUDE_SOURCE:
                included.append(row)
            elif source == SYNTHETIC_SOURCE:
                synthetic.append(_with_exclusion(row, "synthetic_metadata_only"))
            elif source == UNKNOWN_LICENSE_SOURCE:
                excluded.append(_with_exclusion(row, "unknown_license"))
            elif source == UNRESOLVABLE_SOURCE:
                excluded.append(_with_exclusion(row, "unresolvable_source_reference"))
            else:
                excluded.append(_with_exclusion(row, f"unsupported_source:{source}"))
    return RowSelection(included=included, synthetic=synthetic, excluded=excluded)


def _with_exclusion(row: dict[str, Any], reason: str) -> dict[str, Any]:
    row = dict(row)
    row["exclusion_reason"] = reason
    return row


def _rewrite_included_rows(
    *,
    rows_by_file: dict[str, list[dict[str, Any]]],
    included_ids: set[str],
    output_root: Path,
    max_image_size: int,
    skip_image_materialization: bool,
) -> dict[str, list[dict[str, Any]]]:
    rewritten: dict[str, list[dict[str, Any]]] = {}
    image_names = {}
    for filename, rows in rows_by_file.items():
        rewritten[filename] = []
        for row in rows:
            if row["row_id"] not in included_ids:
                continue
            row = _normalize_row(row)
            image_name = _bright_image_name(row["baseline_image"])
            image_names[row["row_id"]] = image_name
            row["baseline_image"] = f"images/baseline/{row['row_id']}_baseline.png"
            row["current_image"] = f"images/current/{row['row_id']}_current.png"
            rewritten[filename].append(row)

    if not skip_image_materialization:
        _materialize_bright_images(
            output_root=output_root,
            rows=[row for rows in rewritten.values() for row in rows],
            image_names=image_names,
            max_image_size=max_image_size,
        )
    return rewritten


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = {key: value for key, value in row.items() if not key.startswith("_")}
    EvidenceFirstCandidate.model_validate(normalized)
    return normalized


def _bright_image_name(image_ref: str) -> str:
    for split in ("train", "val", "test"):
        marker = f"{split}/images/"
        if marker in image_ref:
            name = image_ref[image_ref.index(marker) :]
            for suffix in ("_pre", "_post"):
                if name.endswith(suffix):
                    return name[: -len(suffix)]
            return name
    raise ValueError(f"cannot parse BRIGHT image reference: {image_ref}")


def _materialize_bright_images(
    *,
    output_root: Path,
    rows: list[dict[str, Any]],
    image_names: dict[str, str],
    max_image_size: int,
) -> None:
    needed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        needed[image_names[row["row_id"]]].append(row)
    baseline_dir = output_root / "images" / "baseline"
    current_dir = output_root / "images" / "current"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    current_dir.mkdir(parents=True, exist_ok=True)

    by_split: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(dict)
    for image_name, rows_for_image in needed.items():
        split = image_name.split("/", maxsplit=1)[0]
        by_split[split][image_name] = rows_for_image

    missing = set(needed)
    for split, split_needed in sorted(by_split.items()):
        dataset = load_dataset(INCLUDE_SOURCE, split=split, streaming=True)
        for source_row in dataset:
            image_name = source_row["image_name"]
            if image_name not in split_needed:
                continue
            for row in split_needed[image_name]:
                _save_image(
                    source_row["t1_image"], output_root / row["baseline_image"], max_image_size
                )
                _save_image(
                    source_row["t2_image"], output_root / row["current_image"], max_image_size
                )
            missing.discard(image_name)
            if not missing:
                return
    if missing:
        sample = ", ".join(sorted(missing)[:10])
        raise RuntimeError(f"failed to materialize {len(missing)} BRIGHT image pairs: {sample}")


def _save_image(image: Image.Image, path: Path, max_image_size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    prepared = image.convert("RGB")
    prepared.thumbnail((max_image_size, max_image_size), Image.Resampling.LANCZOS)
    prepared.save(path, format="PNG", optimize=True)


def _write_flat_files(*, output_root: Path, rows_by_file: dict[str, list[dict[str, Any]]]) -> None:
    for filename, rows in rows_by_file.items():
        _write_jsonl(output_root / filename, rows)


def _write_sft_files(*, output_root: Path, rows_by_file: dict[str, list[dict[str, Any]]]) -> None:
    mapping = {
        "train_flat.jsonl": "train_sft.jsonl",
        "eval_flat.jsonl": "eval_sft.jsonl",
        "eval_calibration_flat.jsonl": "eval_calibration_sft.jsonl",
    }
    for flat_name, sft_name in mapping.items():
        _write_jsonl(output_root / sft_name, [_sft_row(row) for row in rows_by_file[flat_name]])


def _sft_row(row: dict[str, Any]) -> dict[str, Any]:
    answer = {
        "visual_evidence_tags": row["visual_evidence_tags"],
        "evidence_strength": row["evidence_strength"],
        "damage_mechanism": row["damage_mechanism"],
        "visibility_quality": row["visibility_quality"],
        "negative_type": row["negative_type"],
        "bbox_norm": row["bbox_norm"],
        "bbox_quality": row["bbox_quality"],
        "change_confidence": row["change_confidence"],
        "civilian_infrastructure_type": row["civilian_infrastructure_type"],
        "rationale": row["rationale"],
        "triage_action": row["triage_action"],
    }
    user = (
        "Compare the baseline and current satellite images. "
        "Identify macro-visible civilian infrastructure disruption only. "
        "Return strict JSON with visual evidence fields first and triage_action last.\n\n"
        f"Location: {row['location_name']}, {row['country']}\n"
        f"Event: {row['source_event']}\n"
        f"Modality: {row['modality']}\n"
        f"Baseline image: {row['baseline_image']}\n"
        f"Current image: {row['current_image']}"
    )
    return {
        "row_id": row["row_id"],
        "images": [row["baseline_image"], row["current_image"]],
        "messages": [
            {
                "role": "system",
                "content": "You are Blackline Atlas evidence-first satellite disruption triage.",
            },
            {"role": "user", "content": user},
            {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)},
        ],
        "metadata": {
            "source_dataset": row["source_dataset"],
            "source_event": row["source_event"],
            "event_family": row["event_family"],
            "modality": row["modality"],
            "triage_action": row["triage_action"],
            "license": row["license"],
        },
    }


def _write_excluded_files(*, output_root: Path, selection: RowSelection) -> None:
    synthetic = [_strip_private_keys(row) for row in selection.synthetic]
    excluded_unknown = [
        _strip_private_keys(row)
        for row in selection.excluded
        if row["exclusion_reason"] == "unknown_license"
    ]
    excluded_unresolvable = [
        _strip_private_keys(row)
        for row in selection.excluded
        if row["exclusion_reason"] == "unresolvable_source_reference"
    ]
    _write_jsonl(output_root / "synthetic_reasoning_flat.jsonl", synthetic)
    _write_jsonl(
        output_root / "synthetic_reasoning_sft.jsonl",
        [_synthetic_sft_row(row) for row in synthetic],
    )
    _write_jsonl(output_root / "excluded_unknown_license.jsonl", excluded_unknown)
    _write_jsonl(output_root / "excluded_unresolvable_references.jsonl", excluded_unresolvable)


def _synthetic_sft_row(row: dict[str, Any]) -> dict[str, Any]:
    clean = _strip_private_keys(row)
    answer = {
        "visual_evidence_tags": clean["visual_evidence_tags"],
        "evidence_strength": clean["evidence_strength"],
        "damage_mechanism": clean["damage_mechanism"],
        "visibility_quality": clean["visibility_quality"],
        "negative_type": clean["negative_type"],
        "bbox_norm": clean["bbox_norm"],
        "bbox_quality": clean["bbox_quality"],
        "change_confidence": clean["change_confidence"],
        "civilian_infrastructure_type": clean["civilian_infrastructure_type"],
        "rationale": clean["rationale"],
        "triage_action": clean["triage_action"],
    }
    return {
        "row_id": clean["row_id"],
        "messages": [
            {"role": "system", "content": "Schema-only synthetic reasoning row. No images."},
            {"role": "user", "content": f"Reason from metadata for {clean['location_name']}."},
            {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)},
        ],
        "metadata": {
            "source_dataset": clean["source_dataset"],
            "exclusion_reason": clean["exclusion_reason"],
            "triage_action": clean["triage_action"],
        },
    }


def _strip_private_keys(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not key.startswith("_")}


def _validate_output(
    *,
    output_root: Path,
    rows_by_file: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    issues: list[str] = []
    event_sets: dict[str, set[str]] = {}
    location_sets: dict[str, set[str]] = {}
    duplicate_row_ids_by_file: dict[str, list[str]] = {}
    image_count = 0
    for filename, rows in rows_by_file.items():
        split = filename.removesuffix("_flat.jsonl")
        event_sets[split] = {row["source_event"] for row in rows}
        location_sets[split] = {row["location_name"] for row in rows}
        row_ids: set[str] = set()
        duplicate_row_ids = []
        for row in rows:
            if row["row_id"] in row_ids:
                duplicate_row_ids.append(row["row_id"])
            row_ids.add(row["row_id"])
            try:
                EvidenceFirstCandidate.model_validate(row)
            except Exception as exc:  # pragma: no cover - reported in validation artifact
                issues.append(f"{row['row_id']}: schema failed: {exc}")
            for field in ("baseline_image", "current_image"):
                path = output_root / row[field]
                if not path.exists():
                    issues.append(f"{row['row_id']}: missing image {row[field]}")
                    continue
                try:
                    with Image.open(path) as image:
                        image.verify()
                    image_count += 1
                except Exception as exc:  # pragma: no cover - reported in validation artifact
                    issues.append(f"{row['row_id']}: invalid image {row[field]}: {exc}")
        if duplicate_row_ids:
            duplicate_row_ids_by_file[filename] = duplicate_row_ids

    train_events = event_sets.get("train", set())
    eval_events = event_sets.get("eval", set())
    train_locations = location_sets.get("train", set())
    eval_locations = location_sets.get("eval", set())
    event_overlap = sorted(train_events & eval_events)
    location_overlap = sorted(train_locations & eval_locations)
    if event_overlap:
        issues.append(f"train/eval event overlap: {event_overlap}")
    if location_overlap:
        issues.append(f"train/eval location overlap: {location_overlap}")
    if duplicate_row_ids_by_file:
        issues.append(f"duplicate row ids within split: {duplicate_row_ids_by_file}")

    summary = {
        "row_counts": {filename: len(rows) for filename, rows in rows_by_file.items()},
        "action_balance": {
            filename: dict(Counter(row["triage_action"] for row in rows))
            for filename, rows in rows_by_file.items()
        },
        "modality_balance": {
            filename: dict(Counter(row["modality"] for row in rows))
            for filename, rows in rows_by_file.items()
        },
        "bbox_quality": {
            filename: dict(Counter(row["bbox_quality"] for row in rows))
            for filename, rows in rows_by_file.items()
        },
        "image_count": image_count,
        "event_overlap": event_overlap,
        "location_overlap": location_overlap,
        "duplicate_row_ids_by_file": duplicate_row_ids_by_file,
    }
    return {"overall_pass": not issues, "issues": issues, "summary": summary}


def _write_metadata(
    *,
    output_root: Path,
    rows_by_file: dict[str, list[dict[str, Any]]],
    selection: RowSelection,
    validation: dict[str, Any],
) -> None:
    metadata = {
        "dataset_name": "satellite-disruption-triage-aux-v2-1",
        "version": "2.1.0",
        "source_dataset": DATASET_REPO,
        "repair_policy": "real-image, license-safe subset only",
        "included_source": INCLUDE_SOURCE,
        "excluded_counts": dict(Counter(row["exclusion_reason"] for row in selection.excluded)),
        "synthetic_reasoning_rows": len(selection.synthetic),
        "real_image_rows": sum(len(rows) for rows in rows_by_file.values()),
        "validation": validation,
        "notes": [
            "Synthetic rows are separated from VLM SFT files.",
            "SEN12MSCR rows are excluded because license is unknown.",
            "sda-kr/xbd-ukraine rows are excluded because v2 references are not resolvable.",
            "Images are resized to 512px max side for diagnostic VLM SFT.",
        ],
    }
    (output_root / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_validation_report(
    *,
    output_root: Path,
    validation: dict[str, Any],
    selection: RowSelection,
) -> None:
    excluded_unknown_count = sum(
        1 for row in selection.excluded if row["exclusion_reason"] == "unknown_license"
    )
    excluded_unresolvable_count = sum(
        1
        for row in selection.excluded
        if row["exclusion_reason"] == "unresolvable_source_reference"
    )
    action_balance = json.dumps(validation["summary"]["action_balance"], sort_keys=True)
    modality_balance = json.dumps(validation["summary"]["modality_balance"], sort_keys=True)
    bbox_quality = json.dumps(validation["summary"]["bbox_quality"], sort_keys=True)
    lines = [
        "# Validation Report",
        "",
        f"- overall_pass: `{validation['overall_pass']}`",
        f"- real_image_rows: `{validation['summary']['row_counts']}`",
        f"- image_count: `{validation['summary']['image_count']}`",
        f"- synthetic_reasoning_rows: `{len(selection.synthetic)}`",
        f"- excluded_unknown_license: `{excluded_unknown_count}`",
        f"- excluded_unresolvable_references: `{excluded_unresolvable_count}`",
        f"- action_balance: `{action_balance}`",
        f"- modality_balance: `{modality_balance}`",
        f"- bbox_quality: `{bbox_quality}`",
        f"- event_overlap: `{validation['summary']['event_overlap']}`",
        f"- location_overlap: `{validation['summary']['location_overlap']}`",
        f"- duplicate_row_ids_by_file: `{validation['summary']['duplicate_row_ids_by_file']}`",
        "",
        "## Issues",
        "",
    ]
    lines.extend([f"- {issue}" for issue in validation["issues"]] or ["- none"])
    (output_root / "validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_source_audit(*, output_root: Path, selection: RowSelection) -> None:
    lines = [
        "# Source Audit",
        "",
        "## Included",
        "",
        (
            f"- `{INCLUDE_SOURCE}`: real image pairs materialized from streaming parquet. "
            "License inherited as CC-BY-NC-4.0."
        ),
        "",
        "## Separated",
        "",
        f"- `{SYNTHETIC_SOURCE}`: schema/reasoning rows only. Excluded from VLM SFT image files.",
        "",
        "## Excluded",
        "",
        f"- `{UNKNOWN_LICENSE_SOURCE}`: excluded because license is unknown.",
        (
            f"- `{UNRESOLVABLE_SOURCE}`: excluded because v2 refs such as "
            "`train/12_pre` are not files in the source repo."
        ),
        "",
        "## Counts",
        "",
        f"- included rows: `{len(selection.included)}`",
        f"- synthetic rows: `{len(selection.synthetic)}`",
        f"- excluded rows: `{len(selection.excluded)}`",
    ]
    (output_root / "source_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_readme(
    *,
    output_root: Path,
    rows_by_file: dict[str, list[dict[str, Any]]],
    validation: dict[str, Any],
) -> None:
    action_balance = json.dumps(validation["summary"]["action_balance"], sort_keys=True)
    lines = [
        "---",
        "license: cc-by-nc-4.0",
        "size_categories:",
        "- 1K<n<10K",
        "task_categories:",
        "- image-to-text",
        "tags:",
        "- satellite-imagery",
        "- vision-language",
        "- conflict-disruption-triage",
        "- evidence-first",
        "- blackline-atlas",
        "---",
        "",
        "# Satellite Disruption Triage Aux v2.1",
        "",
        "Self-contained real-image repair of `ChrisRPL/satellite-disruption-triage-aux-v2`.",
        "",
        (
            "This version keeps only resolvable BRIGHT real-image rows in VLM SFT files. "
            "Synthetic reasoning rows are separated, SEN12MSCR is excluded because the "
            "license is unknown, and xBD-Ukraine rows from v2 are excluded because their "
            "image references are not resolvable in the stated source repo."
        ),
        "",
        "## Files",
        "",
        "- `train_flat.jsonl` / `train_sft.jsonl`: real-image train rows",
        "- `eval_flat.jsonl` / `eval_sft.jsonl`: event-held-out real-image eval rows",
        (
            "- `eval_calibration_flat.jsonl` / `eval_calibration_sft.jsonl`: "
            "reduced real-image calibration rows"
        ),
        (
            "- `synthetic_reasoning_flat.jsonl` / `synthetic_reasoning_sft.jsonl`: "
            "metadata-only rows, not for VLM SFT"
        ),
        "- `excluded_unknown_license.jsonl`: SEN12MSCR rows",
        "- `excluded_unresolvable_references.jsonl`: xBD-Ukraine rows with bad refs",
        "",
        "## Counts",
        "",
    ]
    for filename, rows in rows_by_file.items():
        lines.append(f"- `{filename}`: `{len(rows)}`")
    lines.extend(
        [
            "",
            "## Validation",
            "",
            f"- overall_pass: `{validation['overall_pass']}`",
            f"- image_count: `{validation['summary']['image_count']}`",
            f"- action_balance: `{action_balance}`",
            "",
            "## Limitations",
            "",
            (
                "- BRIGHT uses optical baseline to SAR current imagery, so modality "
                "artifacts remain a risk."
            ),
            "- License is CC-BY-NC-4.0 inherited from BRIGHT; non-commercial use only.",
            "- Bboxes are still source-derived/synthetic approximations, not manual polygons.",
            (
                "- Calibration split is no longer balanced after filtering to real-image, "
                "license-safe rows."
            ),
            (
                "- Intended for civilian disruption triage only; not for tactical "
                "targeting, strike support, or military asset ranking."
            ),
        ]
    )
    (output_root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_gitattributes(*, output_root: Path) -> None:
    lines = [
        "*.png filter=lfs diff=lfs merge=lfs -text",
        "*.jpg filter=lfs diff=lfs merge=lfs -text",
        "*.jpeg filter=lfs diff=lfs merge=lfs -text",
        "*.zip filter=lfs diff=lfs merge=lfs -text",
    ]
    (output_root / ".gitattributes").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
