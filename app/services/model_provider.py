from __future__ import annotations

import json
from typing import Protocol
from urllib.request import Request

from app.schemas.model_payload import CandidateRequestPayload, CandidateResponsePayload

DEFAULT_MODEL_PROVIDER = "atlas_json_http"


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


def resolve_http_candidate_provider(provider_id: str) -> HttpCandidateProvider | None:
    if provider_id == DEFAULT_MODEL_PROVIDER:
        return AtlasJsonHttpCandidateProvider()
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
