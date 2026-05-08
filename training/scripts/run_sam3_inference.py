from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.sam3_eval import Sam3EvalCase  # noqa: E402
from app.schemas.sam3_evidence import (  # noqa: E402
    Sam3EvidenceBackendMode,
    Sam3EvidenceMask,
    Sam3EvidenceReport,
)
from app.services.sam3_evidence import (  # noqa: E402
    build_sam3_report_from_masks,
    score_temporal_change_masks,
)

DEFAULT_DATASET = ROOT / "training" / "replay_pack" / "sam3_eval_pack.jsonl"
DEFAULT_OUTPUT = ROOT / "training" / "eval_runs" / "sam3_eval" / "reports.jsonl"


def run_sam3_inference(
    *,
    dataset_path: Path,
    output_path: Path,
    backend: str,
    model_id: str,
    image_root: Path | None = None,
    score_threshold: float = 0.5,
    mask_threshold: float = 0.5,
    max_cases: int | None = None,
) -> dict[str, Any]:
    cases = _load_cases(dataset_path)
    if max_cases is not None:
        cases = cases[:max_cases]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if backend == "fixture":
        reports = [_fixture_report(case, model_id=model_id) for case in cases]
    elif backend == "transformers":
        reports = _run_transformers_backend(
            cases,
            model_id=model_id,
            image_root=image_root,
            score_threshold=score_threshold,
            mask_threshold=mask_threshold,
        )
    elif backend == "official":
        reports = _run_official_backend(
            cases,
            model_id=model_id,
            image_root=image_root,
            score_threshold=score_threshold,
        )
    else:
        raise ValueError(f"unsupported backend: {backend}")

    output_path.write_text(
        "".join(
            json.dumps(report.model_dump(mode="json"), sort_keys=True) + "\n" for report in reports
        ),
        encoding="utf-8",
    )
    summary = {
        "dataset": str(dataset_path),
        "output": str(output_path),
        "backend": backend,
        "model_id": model_id,
        "case_count": len(cases),
        "segmentation_ready": sum(report.decision == "segmentation_ready" for report in reports),
        "no_evidence": sum(report.decision == "no_evidence" for report in reports),
        "unavailable": sum(report.decision == "unavailable" for report in reports),
    }
    summary_path = output_path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run SAM3/SAM3.1 promptable concept segmentation over a Blackline eval pack.",
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--backend",
        choices=("fixture", "transformers", "official"),
        default="fixture",
        help="fixture, Transformers facebook/sam3, or official Meta sam3 package",
    )
    parser.add_argument("--model-id", default="facebook/sam3")
    parser.add_argument("--image-root", type=Path, default=None)
    parser.add_argument("--score-threshold", type=float, default=0.5)
    parser.add_argument("--mask-threshold", type=float, default=0.5)
    parser.add_argument("--max-cases", type=int, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run_sam3_inference(
        dataset_path=args.dataset,
        output_path=args.output,
        backend=args.backend,
        model_id=args.model_id,
        image_root=args.image_root,
        score_threshold=args.score_threshold,
        mask_threshold=args.mask_threshold,
        max_cases=args.max_cases,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _load_cases(path: Path) -> list[Sam3EvalCase]:
    return [
        Sam3EvalCase.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _fixture_report(case: Sam3EvalCase, *, model_id: str) -> Sam3EvidenceReport:
    masks = []
    if case.expected_bbox_norm is not None and case.expected_visual_evidence_tags:
        prompt = case.prompts[0]
        masks.append(
            Sam3EvidenceMask(
                label=case.expected_visual_evidence_tags[0].replace("_", " "),
                prompt=prompt,
                score=0.9,
                bbox_norm=case.expected_bbox_norm,
                area_ratio=_bbox_area(case.expected_bbox_norm),
            )
        )
    return build_sam3_report_from_masks(
        asset=case.asset,
        current=case.current_frame,
        baseline=case.baseline_frame,
        prompts=case.prompts,
        masks=masks,
        model_version=model_id,
        backend="fixture",
    )


def _run_transformers_backend(
    cases: list[Sam3EvalCase],
    *,
    model_id: str,
    image_root: Path | None,
    score_threshold: float,
    mask_threshold: float,
) -> list[Sam3EvidenceReport]:
    if "sam3.1" in model_id.lower():
        raise RuntimeError(
            "facebook/sam3.1 is not a Transformers checkpoint. "
            "Use --backend official with Meta's sam3 package installed."
        )
    try:
        import torch
        from PIL import Image
        from transformers import Sam3Model, Sam3Processor
    except ImportError as exc:
        raise RuntimeError(
            "Real SAM3 inference requires torch, pillow, and transformers with SAM3 support."
        ) from exc

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device != "cuda":
        raise RuntimeError("SAM3 transformers backend requires CUDA for this workflow.")

    model = Sam3Model.from_pretrained(model_id).to(device)
    processor = Sam3Processor.from_pretrained(model_id)
    reports: list[Sam3EvidenceReport] = []
    for case in cases:
        current_image_path = _resolve_image_ref(
            case.current_frame.frame.image_ref,
            image_root=image_root,
        )
        baseline_image_path = _resolve_image_ref(
            case.baseline_frame.frame.image_ref,
            image_root=image_root,
        )
        if current_image_path is None or baseline_image_path is None:
            reports.append(
                _unavailable_case_report(
                    case,
                    model_id=model_id,
                    backend="sam3_transformers",
                )
            )
            continue

        current_masks = _run_transformers_frame_masks(
            model=model,
            processor=processor,
            image=Image.open(current_image_path).convert("RGB"),
            prompts=case.prompts,
            device=device,
            score_threshold=score_threshold,
            mask_threshold=mask_threshold,
            frame_role="current",
        )
        baseline_masks = _run_transformers_frame_masks(
            model=model,
            processor=processor,
            image=Image.open(baseline_image_path).convert("RGB"),
            prompts=case.prompts,
            device=device,
            score_threshold=score_threshold,
            mask_threshold=mask_threshold,
            frame_role="baseline",
        )
        masks = score_temporal_change_masks(
            current_masks=current_masks,
            baseline_masks=baseline_masks,
        )
        reports.append(
            build_sam3_report_from_masks(
                asset=case.asset,
                current=case.current_frame,
                baseline=case.baseline_frame,
                prompts=case.prompts,
                masks=masks,
                model_version=model_id,
                backend="sam3_transformers",
            )
        )
    return reports


def _run_transformers_frame_masks(
    *,
    model: Any,
    processor: Any,
    image: Any,
    prompts: list[str],
    device: str,
    score_threshold: float,
    mask_threshold: float,
    frame_role: str,
) -> list[Sam3EvidenceMask]:
    width, height = image.size
    masks: list[Sam3EvidenceMask] = []
    for prompt in prompts:
        inputs = processor(images=image, text=prompt, return_tensors="pt").to(device)
        with __import__("torch").no_grad():
            outputs = model(**inputs)
        results = processor.post_process_instance_segmentation(
            outputs,
            threshold=score_threshold,
            mask_threshold=mask_threshold,
            target_sizes=inputs.get("original_sizes").tolist(),
        )[0]
        boxes = results.get("boxes", [])
        scores = results.get("scores", [])
        masks.extend(
            _masks_from_boxes(
                boxes=boxes,
                scores=scores,
                prompt=prompt,
                width=width,
                height=height,
                score_threshold=score_threshold,
                frame_role=frame_role,
            )
        )
    return masks


def _run_official_backend(
    cases: list[Sam3EvalCase],
    *,
    model_id: str,
    image_root: Path | None,
    score_threshold: float,
) -> list[Sam3EvidenceReport]:
    if "sam3.1" in model_id.lower():
        raise RuntimeError(
            "facebook/sam3.1 currently publishes the multiplex/video-style checkpoint. "
            "The still-image SAM3 evidence eval uses --backend official --model-id facebook/sam3. "
            "Wire a separate multiplex predictor path before using SAM3.1 here."
        )
    try:
        import torch
        from PIL import Image
        from sam3.model.sam3_image_processor import Sam3Processor
        from sam3.model_builder import build_sam3_image_model
    except ImportError as exc:
        raise RuntimeError(
            "SAM3/SAM3.1 official backend requires Meta's sam3 package, torch, and pillow. "
            "Run this in an HF Job image that installs facebookresearch/sam3."
        ) from exc

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device != "cuda":
        raise RuntimeError("SAM3 official backend requires CUDA for this workflow.")

    model = build_sam3_image_model(device=device)
    processor = Sam3Processor(model)
    reports: list[Sam3EvidenceReport] = []
    for case in cases:
        current_image_path = _resolve_image_ref(
            case.current_frame.frame.image_ref,
            image_root=image_root,
        )
        baseline_image_path = _resolve_image_ref(
            case.baseline_frame.frame.image_ref,
            image_root=image_root,
        )
        if current_image_path is None or baseline_image_path is None:
            reports.append(
                _unavailable_case_report(
                    case,
                    model_id=model_id,
                    backend="sam3_official",
                )
            )
            continue

        with torch.inference_mode(), torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            current_masks = _run_official_frame_masks(
                processor=processor,
                image=Image.open(current_image_path).convert("RGB"),
                prompts=case.prompts,
                score_threshold=score_threshold,
                frame_role="current",
            )
            baseline_masks = _run_official_frame_masks(
                processor=processor,
                image=Image.open(baseline_image_path).convert("RGB"),
                prompts=case.prompts,
                score_threshold=score_threshold,
                frame_role="baseline",
            )
        masks = score_temporal_change_masks(
            current_masks=current_masks,
            baseline_masks=baseline_masks,
        )
        reports.append(
            build_sam3_report_from_masks(
                asset=case.asset,
                current=case.current_frame,
                baseline=case.baseline_frame,
                prompts=case.prompts,
                masks=masks,
                model_version=model_id,
                backend="sam3_official",
            )
        )
    return reports


def _run_official_frame_masks(
    *,
    processor: Any,
    image: Any,
    prompts: list[str],
    score_threshold: float,
    frame_role: str,
) -> list[Sam3EvidenceMask]:
    width, height = image.size
    masks: list[Sam3EvidenceMask] = []
    inference_state = processor.set_image(image)
    for prompt in prompts:
        output = processor.set_text_prompt(state=inference_state, prompt=prompt)
        boxes, scores = _normalize_boxes_scores(output)
        masks.extend(
            _masks_from_boxes(
                boxes=boxes,
                scores=scores,
                prompt=prompt,
                width=width,
                height=height,
                score_threshold=score_threshold,
                frame_role=frame_role,
            )
        )
    return masks


def _masks_from_boxes(
    *,
    boxes: Any,
    scores: Any,
    prompt: str,
    width: int,
    height: int,
    score_threshold: float,
    frame_role: str = "current",
) -> list[Sam3EvidenceMask]:
    masks = []
    for box, score in zip(boxes, scores, strict=False):
        score_value = float(score.item() if hasattr(score, "item") else score)
        if score_value < score_threshold:
            continue
        bbox = _normalize_box(
            [float(value.item() if hasattr(value, "item") else value) for value in box],
            width=width,
            height=height,
        )
        masks.append(
            Sam3EvidenceMask(
                label=prompt,
                prompt=prompt,
                score=score_value,
                bbox_norm=bbox,
                area_ratio=_bbox_area(bbox),
                frame_role=frame_role,
            )
        )
    return masks


def _normalize_boxes_scores(output: dict[str, Any]) -> tuple[list[Any], list[float]]:
    boxes = _tensor_to_list(output.get("boxes", []))
    scores = _tensor_to_list(output.get("scores", []))
    if boxes and isinstance(boxes[0], (int, float)):
        boxes = [boxes]
    if boxes and isinstance(boxes[0], list) and boxes[0] and isinstance(boxes[0][0], list):
        boxes = boxes[0]
    if scores and isinstance(scores[0], list):
        scores = scores[0]
    return boxes, [float(score) for score in scores]


def _tensor_to_list(value: Any) -> Any:
    if hasattr(value, "detach"):
        return value.detach().cpu().tolist()
    return value


def _resolve_image_ref(image_ref: str | None, *, image_root: Path | None) -> Path | None:
    if not image_ref or image_ref.startswith("pending://"):
        return None
    path = Path(image_ref)
    if path.exists():
        return path
    if image_root is None:
        return None
    rooted = image_root / image_ref
    return rooted if rooted.exists() else None


def _normalize_box(
    box: list[float],
    *,
    width: int,
    height: int,
) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = box
    if max(box) > 1.0:
        x1, x2 = x1 / width, x2 / width
        y1, y2 = y1 / height, y2 / height
    return (
        max(min(x1, 1.0), 0.0),
        max(min(y1, 1.0), 0.0),
        max(min(x2, 1.0), 0.0),
        max(min(y2, 1.0), 0.0),
    )


def _bbox_area(bbox: tuple[float, float, float, float]) -> float:
    return round(max((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]), 0.0), 3)


def _unavailable_case_report(
    case: Sam3EvalCase,
    *,
    model_id: str,
    backend: Sam3EvidenceBackendMode,
) -> Sam3EvidenceReport:
    return Sam3EvidenceReport(
        asset_id=case.asset.asset_id,
        current_frame_id=case.current_frame.frame.frame_id,
        baseline_frame_id=case.baseline_frame.frame.frame_id,
        current_image_ref=case.current_frame.frame.image_ref,
        baseline_image_ref=case.baseline_frame.frame.image_ref,
        overlay_ref=case.current_frame.overlay_ref,
        model_version=model_id,
        backend=backend,
        decision="unavailable",
        prompts=case.prompts,
        triage_action="discard",
        summary="Current image is unavailable to the SAM3 inference runner.",
    )


if __name__ == "__main__":
    raise SystemExit(main())
