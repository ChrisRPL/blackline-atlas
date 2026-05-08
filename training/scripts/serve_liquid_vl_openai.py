from __future__ import annotations

import argparse
import base64
import binascii
import os
import sys
import time
from io import BytesIO
from pathlib import Path
from typing import Any, Callable
from urllib.request import urlopen

from fastapi import FastAPI, HTTPException

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8014
DEFAULT_MODEL_ID = "LiquidAI/LFM2.5-VL-450M-MLX-4bit"
DEFAULT_TRANSFORMERS_MODEL_ID = "LiquidAI/LFM2.5-VL-450M"
DEFAULT_ADAPTER_REF = "ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter"


class LocalLiquidVisionServer:
    def __init__(self, *, model_id: str, backend: str, adapter_ref: str | None = None) -> None:
        self.model_id = model_id
        self.backend = backend
        self.adapter_ref = adapter_ref
        self._loaded = False
        self._model = None
        self._processor = None
        self._generate = None
        self._torch = None

    def generate(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float,
    ) -> str:
        self._ensure_loaded()
        if self.backend == "transformers":
            return self._generate_transformers(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        template_messages, images = build_template_messages(messages, image_loader=load_image_ref)
        if not template_messages:
            raise ValueError("chat request missing usable message content")
        prompt = self._processor.apply_chat_template(
            template_messages,
            add_generation_prompt=True,
        )
        try:
            result = self._generate(
                self._model,
                self._processor,
                prompt,
                images,
                max_tokens=max_tokens,
                temp=temperature,
                min_p=0.15,
                repetition_penalty=1.05,
                verbose=False,
            )
        except TypeError:
            result = self._generate(
                self._model,
                self._processor,
                prompt,
                images,
                temp=temperature,
                min_p=0.15,
                repetition_penalty=1.05,
                verbose=False,
            )
        return render_generation_text(result)

    def _generate_transformers(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float,
    ) -> str:
        conversation = build_transformers_messages(messages, image_loader=load_image_ref)
        if not conversation:
            raise ValueError("chat request missing usable message content")
        inputs = self._processor.apply_chat_template(
            conversation,
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
            tokenize=True,
        ).to(self._model.device)
        with self._torch.no_grad():
            output = self._model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                do_sample=temperature > 0,
                temperature=max(temperature, 1e-5),
            )
        generated = output[:, inputs["input_ids"].shape[1] :]
        return self._processor.batch_decode(generated, skip_special_tokens=True)[0].strip()

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self.backend == "transformers":
            self._load_transformers()
            return
        try:
            from mlx_vlm import generate, load
        except ImportError as exc:
            raise RuntimeError(
                "Missing local Liquid vision runtime. Install with "
                '`uv pip install -e ".[dev,local-vlm]"`.'
            ) from exc
        self._model, self._processor = load(self.model_id)
        self._generate = generate
        self._loaded = True

    def _load_transformers(self) -> None:
        try:
            import torch
            from transformers import AutoModelForImageTextToText, AutoProcessor
        except ImportError as exc:
            raise RuntimeError(
                "Missing adapter-capable local VLM runtime. Install with "
                '`uv pip install -e ".[dev,vlm]"`.'
            ) from exc

        token = os.getenv("HF_TOKEN")
        self._processor = AutoProcessor.from_pretrained(self.model_id, token=token)
        self._model = AutoModelForImageTextToText.from_pretrained(
            self.model_id,
            token=token,
            dtype="auto",
            device_map="auto",
        )
        if self.adapter_ref:
            try:
                from peft import PeftModel
            except ImportError as exc:
                raise RuntimeError(
                    "Missing PEFT dependency for adapter serving. Install peft or omit "
                    "--adapter-ref."
                ) from exc
            self._model = PeftModel.from_pretrained(self._model, self.adapter_ref, token=token)
        self._model.eval()
        self._torch = torch
        self._loaded = True


def build_template_messages(
    messages: list[dict[str, Any]],
    *,
    image_loader: Callable[[str], object],
) -> tuple[list[dict[str, Any]], list[object]]:
    template_messages: list[dict[str, Any]] = []
    images: list[object] = []

    for message in messages:
        role = str(message.get("role") or "user")
        content = message.get("content")
        content_parts, content_images = normalize_content_parts(content, image_loader=image_loader)
        if not content_parts:
            continue
        template_messages.append({"role": role, "content": content_parts})
        images.extend(content_images)

    return template_messages, images


def build_transformers_messages(
    messages: list[dict[str, Any]],
    *,
    image_loader: Callable[[str], object],
) -> list[dict[str, Any]]:
    conversation: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role") or "user")
        content = message.get("content")
        parts = normalize_transformers_content_parts(content, image_loader=image_loader)
        if parts:
            conversation.append({"role": role, "content": parts})
    return conversation


def normalize_transformers_content_parts(
    content: Any,
    *,
    image_loader: Callable[[str], object],
) -> list[dict[str, Any]]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if not isinstance(content, list):
        return []

    content_parts: list[dict[str, Any]] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "text":
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                content_parts.append({"type": "text", "text": text})
            continue
        if item_type != "image_url":
            continue
        url = _extract_image_url(item.get("image_url"))
        if url:
            content_parts.append({"type": "image", "image": image_loader(url)})
    return content_parts


def normalize_content_parts(
    content: Any,
    *,
    image_loader: Callable[[str], object],
) -> tuple[list[dict[str, Any]], list[object]]:
    if isinstance(content, str):
        return ([{"type": "text", "text": content}], [])
    if not isinstance(content, list):
        return ([], [])

    content_parts: list[dict[str, Any]] = []
    images: list[object] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "text":
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                content_parts.append({"type": "text", "text": text})
            continue
        if item_type != "image_url":
            continue
        image_url = item.get("image_url")
        url = _extract_image_url(image_url)
        if not url:
            continue
        images.append(image_loader(url))
        content_parts.append({"type": "image"})

    return content_parts, images


def load_image_ref(image_ref: str) -> object:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Missing Pillow for local Liquid vision bridge. Install with "
            '`uv pip install -e ".[dev,local-vlm]"`.'
        ) from exc

    if image_ref.startswith("data:"):
        header, _, encoded = image_ref.partition(",")
        if ";base64" not in header:
            raise ValueError("data image refs must be base64 encoded")
        try:
            payload = base64.b64decode(encoded)
        except binascii.Error as exc:
            raise ValueError("invalid base64 image payload") from exc
        return Image.open(BytesIO(payload)).convert("RGB")

    if image_ref.startswith(("http://", "https://")):
        with urlopen(image_ref) as response:
            payload = response.read()
        return Image.open(BytesIO(payload)).convert("RGB")

    path = Path(image_ref)
    if not path.is_file():
        raise ValueError(f"image ref missing file bytes: {image_ref}")
    return Image.open(path).convert("RGB")


def render_generation_text(result: object) -> str:
    text = getattr(result, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    return str(result).strip()


def create_app(*, model_id: str, backend: str, adapter_ref: str | None = None) -> FastAPI:
    runner = LocalLiquidVisionServer(
        model_id=model_id,
        backend=backend,
        adapter_ref=adapter_ref,
    )
    app = FastAPI(title="Blackline Local Liquid VL Bridge")

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "model": model_id,
            "backend": backend,
            "adapter_ref": adapter_ref,
        }

    @app.post("/v1/chat/completions")
    def chat_completions(payload: dict[str, Any]) -> dict[str, Any]:
        messages = payload.get("messages")
        if not isinstance(messages, list) or not messages:
            raise HTTPException(status_code=400, detail="messages list required")

        request_model = str(payload.get("model") or model_id)
        max_tokens = int(payload.get("max_tokens") or 256)
        temperature = float(payload.get("temperature") or 0.0)

        try:
            text = runner.generate(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return {
            "id": f"chatcmpl-local-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request_model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    return app


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Serve LiquidAI LFM2.5-VL on Apple Silicon behind an "
            "OpenAI-compatible chat endpoint."
        ),
    )
    parser.add_argument(
        "--host",
        default=os.getenv("LOCAL_VLM_HOST", DEFAULT_HOST),
        help=f"Bind host. Default: {DEFAULT_HOST}",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("LOCAL_VLM_PORT", str(DEFAULT_PORT))),
        help=f"Bind port. Default: {DEFAULT_PORT}",
    )
    parser.add_argument(
        "--model-id",
        default=os.getenv("LOCAL_VLM_MODEL_ID"),
        help=(
            "Liquid model id. Defaults to the MLX model for --backend mlx, or "
            f"{DEFAULT_TRANSFORMERS_MODEL_ID} for --backend transformers."
        ),
    )
    parser.add_argument(
        "--backend",
        choices=("mlx", "transformers"),
        default=os.getenv("LOCAL_VLM_BACKEND", "mlx"),
        help="Local serving backend. Use transformers to load PEFT adapters.",
    )
    parser.add_argument(
        "--adapter-ref",
        default=os.getenv("LOCAL_VLM_ADAPTER_REF"),
        help=(
            "Optional PEFT adapter repo/path. Only supported with --backend transformers. "
            f"Current Blackline adapter: {DEFAULT_ADAPTER_REF}"
        ),
    )
    args = parser.parse_args(argv)
    if args.model_id is None:
        args.model_id = (
            DEFAULT_TRANSFORMERS_MODEL_ID if args.backend == "transformers" else DEFAULT_MODEL_ID
        )
    if args.adapter_ref and args.backend != "transformers":
        parser.error("--adapter-ref requires --backend transformers")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    app = create_app(model_id=args.model_id, backend=args.backend, adapter_ref=args.adapter_ref)
    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def _extract_image_url(image_url: Any) -> str | None:
    if isinstance(image_url, str) and image_url:
        return image_url
    if isinstance(image_url, dict):
        url = image_url.get("url")
        if isinstance(url, str) and url:
            return url
    return None


if __name__ == "__main__":
    raise SystemExit(main())
