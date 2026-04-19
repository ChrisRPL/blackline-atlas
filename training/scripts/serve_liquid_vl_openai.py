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


class LocalLiquidVisionServer:
    def __init__(self, *, model_id: str) -> None:
        self.model_id = model_id
        self._loaded = False
        self._model = None
        self._processor = None
        self._generate = None

    def generate(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float,
    ) -> str:
        self._ensure_loaded()
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

    def _ensure_loaded(self) -> None:
        if self._loaded:
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


def create_app(*, model_id: str) -> FastAPI:
    runner = LocalLiquidVisionServer(model_id=model_id)
    app = FastAPI(title="Blackline Local Liquid VL Bridge")

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "model": model_id}

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
        default=os.getenv("LOCAL_VLM_MODEL_ID", DEFAULT_MODEL_ID),
        help=f"Liquid MLX model id. Default: {DEFAULT_MODEL_ID}",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    app = create_app(model_id=args.model_id)
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
