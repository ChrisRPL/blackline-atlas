from __future__ import annotations

import os
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.schemas.asset import Asset
from app.schemas.frame import FrameEnvelope
from app.schemas.sam3_evidence import (
    Sam3EvidenceBackendMode,
    Sam3EvidenceMask,
    Sam3EvidenceReport,
    Sam3SourceContext,
)
from app.services.sam3_evidence import (
    build_sam3_report_from_masks,
    score_temporal_change_masks,
)

BridgeBackend = Literal["transformers", "official"]

DEFAULT_MODEL_ID = "facebook/sam3"
DEFAULT_BACKEND: BridgeBackend = "transformers"
DEFAULT_SCORE_THRESHOLD = 0.5
DEFAULT_MASK_THRESHOLD = 0.5


class Sam3BridgeRequest(BaseModel):
    asset: dict[str, Any]
    current_frame: dict[str, Any]
    baseline_frame: dict[str, Any]
    alert: dict[str, Any] | None = None
    source_context: dict[str, Any] | None = None
    prompts: list[str] = Field(default_factory=list)
    model_version: str = DEFAULT_MODEL_ID


class LocalSam3Runner:
    def __init__(
        self,
        *,
        backend: BridgeBackend,
        model_id: str,
        score_threshold: float,
        mask_threshold: float,
        allow_cpu: bool,
    ) -> None:
        self.backend = backend
        self.model_id = model_id
        self.score_threshold = score_threshold
        self.mask_threshold = mask_threshold
        self.allow_cpu = allow_cpu
        self.device: str | None = None
        self.model: Any | None = None
        self.processor: Any | None = None

    @property
    def loaded(self) -> bool:
        return self.model is not None and self.processor is not None

    def analyze(
        self,
        *,
        asset: Asset,
        current: FrameEnvelope,
        baseline: FrameEnvelope,
        prompts: list[str],
        source_context: Sam3SourceContext | None,
    ) -> Sam3EvidenceReport:
        current_path = _resolve_local_image_ref(current.frame.image_ref)
        baseline_path = _resolve_local_image_ref(baseline.frame.image_ref)
        if current_path is None or baseline_path is None:
            return _bridge_unavailable_report(
                asset=asset,
                current=current,
                baseline=baseline,
                prompts=prompts,
                source_context=source_context,
                model_version=self.model_id,
                backend=self._report_backend,
                summary="Local SAM3 bridge could not resolve both local image paths.",
            )

        if not prompts:
            return build_sam3_report_from_masks(
                asset=asset,
                current=current,
                baseline=baseline,
                prompts=[],
                masks=[],
                model_version=self.model_id,
                backend=self._report_backend,
                source_context=source_context,
            )

        self._load()
        current_masks = self._frame_masks(
            image_path=current_path,
            prompts=prompts,
            frame_role="current",
        )
        baseline_masks = self._frame_masks(
            image_path=baseline_path,
            prompts=prompts,
            frame_role="baseline",
        )
        masks = score_temporal_change_masks(
            current_masks=current_masks,
            baseline_masks=baseline_masks,
        )
        return build_sam3_report_from_masks(
            asset=asset,
            current=current,
            baseline=baseline,
            prompts=prompts,
            masks=masks,
            model_version=self.model_id,
            backend=self._report_backend,
            source_context=source_context,
        )

    @property
    def _report_backend(self) -> Sam3EvidenceBackendMode:
        return "sam3_official" if self.backend == "official" else "sam3_transformers"

    def _load(self) -> None:
        if self.loaded:
            return
        if self.backend == "official":
            self._load_official()
        else:
            self._load_transformers()

    def _load_transformers(self) -> None:
        try:
            import torch
            from transformers import Sam3Model, Sam3Processor
        except ImportError as exc:
            raise RuntimeError(
                "Local SAM3 bridge requires torch and transformers with Sam3Model support."
            ) from exc

        device = _select_torch_device(torch, allow_cpu=self.allow_cpu)
        self.model = Sam3Model.from_pretrained(self.model_id).to(device)
        self.processor = Sam3Processor.from_pretrained(self.model_id)
        self.device = device

    def _load_official(self) -> None:
        try:
            import torch
            from sam3.model.sam3_image_processor import Sam3Processor
            from sam3.model_builder import build_sam3_image_model
        except ImportError as exc:
            raise RuntimeError(
                "Official local SAM3 bridge requires Meta's facebookresearch/sam3 package."
            ) from exc

        if not torch.cuda.is_available():
            raise RuntimeError(
                "Official SAM3 bridge requires CUDA. Use SAM3_BRIDGE_BACKEND=transformers."
            )
        self.device = "cuda"
        self.model = build_sam3_image_model(device=self.device)
        self.processor = Sam3Processor(self.model)

    def _frame_masks(
        self,
        *,
        image_path: Path,
        prompts: list[str],
        frame_role: Literal["current", "baseline"],
    ) -> list[Sam3EvidenceMask]:
        if self.backend == "official":
            return self._official_frame_masks(
                image_path=image_path,
                prompts=prompts,
                frame_role=frame_role,
            )
        return self._transformers_frame_masks(
            image_path=image_path,
            prompts=prompts,
            frame_role=frame_role,
        )

    def _transformers_frame_masks(
        self,
        *,
        image_path: Path,
        prompts: list[str],
        frame_role: Literal["current", "baseline"],
    ) -> list[Sam3EvidenceMask]:
        import torch
        from PIL import Image

        assert self.model is not None
        assert self.processor is not None
        assert self.device is not None

        image = Image.open(image_path).convert("RGB")
        width, height = image.size
        masks: list[Sam3EvidenceMask] = []
        for prompt in prompts:
            inputs = self.processor(images=image, text=prompt, return_tensors="pt")
            if hasattr(inputs, "to"):
                inputs = inputs.to(self.device)
            with torch.inference_mode():
                outputs = self.model(**inputs)
            target_sizes = inputs.get("original_sizes")
            if hasattr(target_sizes, "tolist"):
                target_sizes = target_sizes.tolist()
            results = self.processor.post_process_instance_segmentation(
                outputs,
                threshold=self.score_threshold,
                mask_threshold=self.mask_threshold,
                target_sizes=target_sizes,
            )[0]
            masks.extend(
                _masks_from_boxes(
                    boxes=results.get("boxes", []),
                    scores=results.get("scores", []),
                    prompt=prompt,
                    width=width,
                    height=height,
                    score_threshold=self.score_threshold,
                    frame_role=frame_role,
                )
            )
        return masks

    def _official_frame_masks(
        self,
        *,
        image_path: Path,
        prompts: list[str],
        frame_role: Literal["current", "baseline"],
    ) -> list[Sam3EvidenceMask]:
        import torch
        from PIL import Image

        assert self.processor is not None
        assert self.device is not None

        image = Image.open(image_path).convert("RGB")
        width, height = image.size
        context = (
            torch.autocast(device_type="cuda", dtype=torch.bfloat16)
            if self.device == "cuda"
            else nullcontext()
        )
        masks: list[Sam3EvidenceMask] = []
        with torch.inference_mode(), context:
            inference_state = self.processor.set_image(image)
            for prompt in prompts:
                output = self.processor.set_text_prompt(state=inference_state, prompt=prompt)
                boxes, scores = _normalize_boxes_scores(output)
                masks.extend(
                    _masks_from_boxes(
                        boxes=boxes,
                        scores=scores,
                        prompt=prompt,
                        width=width,
                        height=height,
                        score_threshold=self.score_threshold,
                        frame_role=frame_role,
                    )
                )
        return masks


def create_app() -> FastAPI:
    app = FastAPI(
        title="Blackline Atlas Local SAM3 Bridge",
        version="0.1.0",
        description="Local promptable concept segmentation bridge for Blackline selected sites.",
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        runner = _get_runner()
        return {
            "status": "ready",
            "backend": runner.backend,
            "model_id": runner.model_id,
            "model_loaded": runner.loaded,
            "device": runner.device or "lazy",
            "local_filesystem": True,
        }

    @app.post("/sam3", response_model=Sam3EvidenceReport)
    def analyze(payload: Sam3BridgeRequest) -> Sam3EvidenceReport:
        asset = Asset.model_validate(payload.asset)
        current = FrameEnvelope.model_validate(payload.current_frame)
        baseline = FrameEnvelope.model_validate(payload.baseline_frame)
        source_context = (
            Sam3SourceContext.model_validate(payload.source_context)
            if payload.source_context
            else None
        )
        try:
            return _get_runner().analyze(
                asset=asset,
                current=current,
                baseline=baseline,
                prompts=payload.prompts,
                source_context=source_context,
            )
        except Exception as exc:
            return _bridge_unavailable_report(
                asset=asset,
                current=current,
                baseline=baseline,
                prompts=payload.prompts,
                source_context=source_context,
                model_version=payload.model_version,
                backend=_get_runner()._report_backend,
                summary=f"Local SAM3 bridge unavailable: {exc}",
            )

    return app


def _get_runner() -> LocalSam3Runner:
    global _RUNNER
    if _RUNNER is None:
        backend = os.getenv("SAM3_BRIDGE_BACKEND", DEFAULT_BACKEND).strip().lower()
        if backend not in {"transformers", "official"}:
            raise RuntimeError("SAM3_BRIDGE_BACKEND must be transformers or official.")
        _RUNNER = LocalSam3Runner(
            backend=backend,  # type: ignore[arg-type]
            model_id=os.getenv("SAM3_MODEL_VERSION", DEFAULT_MODEL_ID),
            score_threshold=float(os.getenv("SAM3_SCORE_THRESHOLD", DEFAULT_SCORE_THRESHOLD)),
            mask_threshold=float(os.getenv("SAM3_MASK_THRESHOLD", DEFAULT_MASK_THRESHOLD)),
            allow_cpu=_env_flag("SAM3_ALLOW_CPU", default=True),
        )
    return _RUNNER


def _resolve_local_image_ref(image_ref: str | None) -> Path | None:
    if not image_ref or image_ref.startswith(("pending://", "http://", "https://")):
        return None
    path = Path(image_ref)
    if path.exists():
        return path
    rooted = Path.cwd() / image_ref
    return rooted if rooted.exists() else None


def _select_torch_device(torch: Any, *, allow_cpu: bool) -> str:
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    if allow_cpu:
        return "cpu"
    raise RuntimeError("No local CUDA/MPS device available and SAM3_ALLOW_CPU=false.")


def _masks_from_boxes(
    *,
    boxes: Any,
    scores: Any,
    prompt: str,
    width: int,
    height: int,
    score_threshold: float,
    frame_role: Literal["current", "baseline"],
) -> list[Sam3EvidenceMask]:
    masks = []
    for box, score in zip(_tensor_to_list(boxes), _tensor_to_list(scores), strict=False):
        score_value = float(score)
        if score_value < score_threshold:
            continue
        bbox = _normalize_box(
            [float(value) for value in _tensor_to_list(box)],
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
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


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


def _bridge_unavailable_report(
    *,
    asset: Asset,
    current: FrameEnvelope,
    baseline: FrameEnvelope,
    prompts: list[str],
    source_context: Sam3SourceContext | None,
    model_version: str,
    backend: Sam3EvidenceBackendMode,
    summary: str,
) -> Sam3EvidenceReport:
    return Sam3EvidenceReport(
        asset_id=asset.asset_id,
        current_frame_id=current.frame.frame_id,
        baseline_frame_id=baseline.frame.frame_id,
        current_image_ref=current.frame.image_ref,
        baseline_image_ref=baseline.frame.image_ref,
        overlay_ref=current.overlay_ref,
        model_version=model_version,
        backend=backend,
        decision="unavailable",
        source_context=source_context,
        prompts=prompts,
        triage_action="discard",
        summary=summary,
    )


def _env_flag(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


_RUNNER: LocalSam3Runner | None = None
app = create_app()
