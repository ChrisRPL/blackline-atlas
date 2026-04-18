from __future__ import annotations

import json
from typing import Protocol
from urllib.request import Request

from app.schemas.planner_payload import PlannerRequestPayload, PlannerResponsePayload
from app.services.model_provider import (
    DEFAULT_MODEL_PROVIDER,
    OPENAI_RESPONSES_PROVIDER,
)

OPENAI_CHAT_COMPLETIONS_PROVIDER = "openai_chat_completions_http"


class HttpAgentPlannerProvider(Protocol):
    provider_id: str

    def build_request(
        self,
        *,
        endpoint: str,
        payload: PlannerRequestPayload,
        api_key: str | None,
    ) -> Request: ...

    def parse_response(self, *, body: str, fallback: str) -> str: ...


class AtlasJsonHttpAgentPlannerProvider:
    provider_id = DEFAULT_MODEL_PROVIDER

    def build_request(
        self,
        *,
        endpoint: str,
        payload: PlannerRequestPayload,
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


class OpenAIResponsesAgentPlannerProvider:
    provider_id = OPENAI_RESPONSES_PROVIDER

    def build_request(
        self,
        *,
        endpoint: str,
        payload: PlannerRequestPayload,
        api_key: str | None,
    ) -> Request:
        system_content = [
            {"type": "input_text", "text": item.text}
            for item in payload.inputs
            if item.role == "system"
        ]
        user_content = [
            {"type": "input_text", "text": item.text}
            for item in payload.inputs
            if item.role == "user"
        ]
        messages: list[dict[str, object]] = []
        if system_content:
            messages.append({"role": "system", "content": system_content})
        messages.append({"role": "user", "content": user_content})

        return Request(
            endpoint,
            data=json.dumps(
                {
                    "model": payload.model_version,
                    "input": messages,
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
        return fallback


class OpenAIChatCompletionsAgentPlannerProvider:
    provider_id = OPENAI_CHAT_COMPLETIONS_PROVIDER

    def build_request(
        self,
        *,
        endpoint: str,
        payload: PlannerRequestPayload,
        api_key: str | None,
    ) -> Request:
        return Request(
            endpoint,
            data=json.dumps(
                {
                    "model": payload.model_version,
                    "messages": [
                        {
                            "role": item.role,
                            "content": item.text,
                        }
                        for item in payload.inputs
                    ],
                    "temperature": 0,
                    "max_tokens": 64,
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

        if not isinstance(payload, dict):
            return fallback

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return fallback

        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message, dict):
            return fallback

        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())
            if chunks:
                return "\n".join(chunks)
        return fallback


def resolve_http_agent_planner_provider(
    provider_id: str,
) -> HttpAgentPlannerProvider | None:
    if provider_id == DEFAULT_MODEL_PROVIDER:
        return AtlasJsonHttpAgentPlannerProvider()
    if provider_id == OPENAI_RESPONSES_PROVIDER:
        return OpenAIResponsesAgentPlannerProvider()
    if provider_id == OPENAI_CHAT_COMPLETIONS_PROVIDER:
        return OpenAIChatCompletionsAgentPlannerProvider()
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
        payload = PlannerResponsePayload.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValueError):
        return text
    return payload.output_text
