from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.sam3_eval import Sam3EvalCase  # noqa: E402

DEFAULT_INPUT_DATASET = (
    ROOT / "training" / "eval_runs" / "sam3_real_eval_pack" / "sam3_eval_pack.jsonl"
)
DEFAULT_INPUT_MANIFEST = (
    ROOT / "training" / "eval_runs" / "sam3_real_eval_pack" / "sam3_eval_manifest.json"
)
DEFAULT_OUTPUT_DIR = ROOT / "training" / "eval_runs" / "sam3_hf_dataset"
DATASET_VERSION = "sam3-real-eval-v2"


def package_sam3_eval_hf_dataset(
    *,
    input_dataset: Path = DEFAULT_INPUT_DATASET,
    input_manifest: Path = DEFAULT_INPUT_MANIFEST,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    dataset_version: str = DATASET_VERSION,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    rows = _load_cases(input_dataset)
    packaged_rows = []
    for row in rows:
        packaged_rows.append(_package_case(row, images_dir=images_dir))

    dataset_path = output_dir / "sam3_eval_pack.jsonl"
    dataset_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in packaged_rows),
        encoding="utf-8",
    )

    source_manifest = json.loads(input_manifest.read_text(encoding="utf-8"))
    metadata = {
        "dataset_version": dataset_version,
        "source_manifest": source_manifest,
        "case_count": len(packaged_rows),
        "image_count": len(list(images_dir.glob("*/*.png"))),
        "files": {
            "dataset": "sam3_eval_pack.jsonl",
            "images": "images/<source_case_id>/{current,baseline}.png",
        },
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "README.md").write_text(_dataset_card(metadata), encoding="utf-8")
    return metadata


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package a materialized SAM3 eval pack as a Hub-safe image dataset.",
    )
    parser.add_argument("--input-dataset", type=Path, default=DEFAULT_INPUT_DATASET)
    parser.add_argument("--input-manifest", type=Path, default=DEFAULT_INPUT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dataset-version", default=DATASET_VERSION)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    metadata = package_sam3_eval_hf_dataset(
        input_dataset=args.input_dataset,
        input_manifest=args.input_manifest,
        output_dir=args.output_dir,
        dataset_version=args.dataset_version,
    )
    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


def _load_cases(path: Path) -> list[Sam3EvalCase]:
    return [
        Sam3EvalCase.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _package_case(row: Sam3EvalCase, *, images_dir: Path) -> dict[str, Any]:
    current_source = _existing_image_path(row.current_frame.frame.image_ref)
    baseline_source = _existing_image_path(row.baseline_frame.frame.image_ref)
    case_dir = images_dir / row.source_case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    current_rel = Path("images") / row.source_case_id / "current.png"
    baseline_rel = Path("images") / row.source_case_id / "baseline.png"
    shutil.copy2(current_source, case_dir / "current.png")
    shutil.copy2(baseline_source, case_dir / "baseline.png")

    payload = row.model_dump(mode="json")
    payload["current_frame"]["frame"]["image_ref"] = current_rel.as_posix()
    payload["baseline_frame"]["frame"]["image_ref"] = baseline_rel.as_posix()
    return payload


def _existing_image_path(image_ref: str | None) -> Path:
    if not image_ref:
        raise ValueError("missing image_ref")
    path = Path(image_ref)
    if not path.exists() or path.stat().st_size == 0:
        raise ValueError(f"missing or empty image file: {image_ref}")
    return path


def _dataset_card(metadata: dict[str, Any]) -> str:
    case_count = metadata["case_count"]
    image_count = metadata["image_count"]
    return f"""---
license: cc-by-4.0
tags:
- blackline-atlas
- sam3
- sam3.1
- satellite-imagery
- conflict-disruption-triage
- segmentation-eval
task_categories:
- image-segmentation
size_categories:
- n<1K
---

# Blackline Atlas SAM3 Real-Image Eval Pack

This dataset packages the Blackline Atlas SAM3/SAM3.1 selected-site evidence eval pack
with real SimSat Sentinel image pairs.

It is an evaluation and integration dataset, not a training benchmark. The cases are exact
civilian lifeline sites with current/baseline satellite frames, text prompts, expected
visual evidence tags, expected triage action, and optional normalized bboxes.

## Contents

- Cases: `{case_count}`
- Images: `{image_count}` PNG files
- Dataset file: `sam3_eval_pack.jsonl`
- Image layout: `images/<source_case_id>/current.png` and `images/<source_case_id>/baseline.png`

## Intended Use

Use this dataset to run SAM3/SAM3.1 zero-shot promptable segmentation against selected
civilian disruption sites before deciding whether any segmentation fine-tuning is justified.

## Important Limitations

- This is not a tactical targeting dataset.
- Labels are Blackline operational eval labels, not expert pixel masks.
- Fine-tuning SAM3/SAM3.1 still requires real binary mask supervision; these rows are
  for inference/eval gating.
- Sentinel resolution limits small-object and fine-grained damage claims.
"""


if __name__ == "__main__":
    raise SystemExit(main())
