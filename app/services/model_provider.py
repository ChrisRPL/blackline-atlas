from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Protocol
from urllib.request import Request

from app.schemas.model_payload import CandidateRequestPayload, CandidateResponsePayload

DEFAULT_MODEL_PROVIDER = "atlas_json_http"
OPENAI_RESPONSES_PROVIDER = "openai_responses_http"
OPENAI_CHAT_COMPLETIONS_PROVIDER = "openai_chat_completions_http"


class HttpCandidateProvider(Protocol):
    provider_id: str

    def build_request(
        self,
        *,
        endpoint: str,
        payload: CandidateRequestPayload,
        api_key: str | None,
    ) -> Request: ...

    def parse_response(self, *, body: str, fallback: str) -> str: ...


class AtlasJsonHttpCandidateProvider:
    provider_id = DEFAULT_MODEL_PROVIDER

    def build_request(
        self,
        *,
        endpoint: str,
        payload: CandidateRequestPayload,
        api_key: str | None,
    ) -> Request:
        return Request(
            endpoint,
            data=json.dumps(payload.model_dump(mode="json")).encode("utf-8"),
            headers=_headers(api_key),
            method="POST",
        )

    def parse_response(self, *, body: str, fallback: str) -> str:
        return _extract_output_text(body, fallback=fallback)


class OpenAIResponsesCandidateProvider:
    provider_id = OPENAI_RESPONSES_PROVIDER

    def build_request(
        self,
        *,
        endpoint: str,
        payload: CandidateRequestPayload,
        api_key: str | None,
    ) -> Request:
        return Request(
            endpoint,
            data=json.dumps(
                {
                    "model": payload.model_version,
                    "input": _build_openai_input(payload),
                }
            ).encode("utf-8"),
            headers=_headers(api_key),
            method="POST",
        )

    def parse_response(self, *, body: str, fallback: str) -> str:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return fallback

        output_text = payload.get("output_text") if isinstance(payload, dict) else None
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        extracted = _extract_openai_output_text(payload)
        return extracted or fallback


class OpenAIChatCompletionsCandidateProvider:
    provider_id = OPENAI_CHAT_COMPLETIONS_PROVIDER

    def build_request(
        self,
        *,
        endpoint: str,
        payload: CandidateRequestPayload,
        api_key: str | None,
    ) -> Request:
        return Request(
            endpoint,
            data=json.dumps(
                {
                    "model": payload.model_version,
                    "messages": _build_openai_chat_messages(payload),
                    "temperature": 0,
                    "max_tokens": 768,
                    "response_format": {"type": "json_object"},
                }
            ).encode("utf-8"),
            headers=_headers(api_key),
            method="POST",
        )

    def parse_response(self, *, body: str, fallback: str) -> str:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return fallback
        extracted = _extract_chat_completions_output_text(payload)
        return extracted or fallback


def resolve_http_candidate_provider(provider_id: str) -> HttpCandidateProvider | None:
    if provider_id == DEFAULT_MODEL_PROVIDER:
        return AtlasJsonHttpCandidateProvider()
    if provider_id == OPENAI_RESPONSES_PROVIDER:
        return OpenAIResponsesCandidateProvider()
    if provider_id == OPENAI_CHAT_COMPLETIONS_PROVIDER:
        return OpenAIChatCompletionsCandidateProvider()
    return None


def _headers(api_key: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _extract_output_text(body: str, *, fallback: str) -> str:
    text = body.strip()
    if not text:
        return fallback

    try:
        payload = CandidateResponsePayload.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValueError):
        return text
    return payload.output_text


def _build_openai_input(payload: CandidateRequestPayload) -> list[dict[str, object]]:
    system_items: list[dict[str, str]] = []
    user_items: list[dict[str, str]] = []

    for item in payload.inputs:
        if item.type == "input_text" and item.role == "system":
            system_items.append({"type": "input_text", "text": item.text})
            continue
        if item.type == "input_text":
            user_items.append({"type": "input_text", "text": item.text})
            continue

        image_item = _openai_image_content(item.image_ref)
        if image_item is not None:
            user_items.append(image_item)
        else:
            user_items.append(
                {
                    "type": "input_text",
                    "text": f"{item.role}_image_ref unavailable to provider: {item.image_ref}",
                }
            )

    messages: list[dict[str, object]] = []
    if system_items:
        messages.append({"role": "system", "content": system_items})
    messages.append({"role": "user", "content": user_items})
    return messages


def _build_openai_chat_messages(payload: CandidateRequestPayload) -> list[dict[str, object]]:
    system_chunks: list[dict[str, object]] = []
    user_chunks: list[dict[str, object]] = []

    for item in payload.inputs:
        if item.type == "input_text" and item.role == "system":
            system_chunks.append({"type": "text", "text": item.text})
            continue
        if item.type == "input_text":
            user_chunks.append({"type": "text", "text": item.text})
            continue

        image_chunk = _openai_chat_image_content(item.image_ref)
        if image_chunk is not None:
            user_chunks.append(image_chunk)
        else:
            user_chunks.append(
                {
                    "type": "text",
                    "text": f"{item.role}_image_ref unavailable to provider: {item.image_ref}",
                }
            )

    messages: list[dict[str, object]] = []
    if system_chunks:
        messages.append({"role": "system", "content": system_chunks})
    messages.append({"role": "user", "content": user_chunks})
    return messages


def _openai_image_content(image_ref: str) -> dict[str, str] | None:
    if image_ref.startswith(("http://", "https://", "data:")):
        return {
            "type": "input_image",
            "image_url": image_ref,
            "detail": "low",
        }

    path = Path(image_ref)
    if not path.exists() or not path.is_file():
        return None

    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {
        "type": "input_image",
        "image_url": f"data:{mime_type};base64,{encoded}",
        "detail": "low",
    }


def _openai_chat_image_content(image_ref: str) -> dict[str, object] | None:
    image_item = _openai_image_content(image_ref)
    if image_item is None:
        return None
    return {
        "type": "image_url",
        "image_url": {
            "url": image_item["image_url"],
            "detail": image_item["detail"],
        },
    }


def _extract_openai_output_text(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None

    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output = payload.get("output")
    if not isinstance(output, list):
        return None

    chunks: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())

    if not chunks:
        return None
    return "\n".join(chunks)


def _extract_chat_completions_output_text(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None

    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return None

    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if not isinstance(content, list):
        return None

    chunks: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            chunks.append(text.strip())

    if not chunks:
        return None
    return "\n".join(chunks)
