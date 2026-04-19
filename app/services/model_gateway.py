from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any, Callable, Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen


class GatewayHttpProvider(Protocol):
    provider_id: str

    def build_request(
        self,
        *,
        endpoint: str,
        payload: Any,
        api_key: str | None,
    ) -> Request: ...

    def parse_response(self, *, body: str, fallback: str) -> str: ...


@dataclass(frozen=True)
class ModelGatewayTelemetry:
    request_kind: str
    model_version: str
    provider_id: str
    endpoint: str
    prompt_hash: str
    frame_ids: tuple[str, ...]
    latency_ms: int
    parse_ok: bool
    cache_hit: bool
    seen_at: datetime
    fallback_reason: str | None = None


@dataclass(frozen=True)
class ModelGatewayResult:
    output_text: str
    telemetry: ModelGatewayTelemetry


class ModelGateway:
    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        telemetry_sink: list[ModelGatewayTelemetry] | None = None,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.telemetry_sink = telemetry_sink
        self._opener = opener or urlopen
        self._cache: dict[str, str] = {}

    def invoke(
        self,
        *,
        endpoint: str,
        provider: GatewayHttpProvider,
        payload: Any,
        api_key: str | None,
        fallback: str,
        request_kind: str,
        frame_ids: tuple[str, ...] = (),
    ) -> ModelGatewayResult:
        model_version = str(payload.model_version)
        prompt_hash = _prompt_hash(payload)
        cache_key = _cache_key(
            endpoint=endpoint,
            provider_id=provider.provider_id,
            model_version=model_version,
            prompt_hash=prompt_hash,
            frame_ids=frame_ids,
        )

        if cache_key in self._cache:
            return self._result(
                output_text=self._cache[cache_key],
                request_kind=request_kind,
                model_version=model_version,
                provider_id=provider.provider_id,
                endpoint=endpoint,
                prompt_hash=prompt_hash,
                frame_ids=frame_ids,
                latency_ms=0,
                parse_ok=True,
                cache_hit=True,
            )

        request = provider.build_request(
            endpoint=endpoint,
            payload=payload,
            api_key=api_key,
        )

        started = monotonic()
        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                status = getattr(response, "status", None)
                if status is None:
                    status = response.getcode()
                if status != 200:
                    return self._result(
                        output_text=fallback,
                        request_kind=request_kind,
                        model_version=model_version,
                        provider_id=provider.provider_id,
                        endpoint=endpoint,
                        prompt_hash=prompt_hash,
                        frame_ids=frame_ids,
                        latency_ms=_elapsed_ms(started),
                        parse_ok=False,
                        cache_hit=False,
                        fallback_reason="http_status",
                    )
                body = response.read().decode("utf-8")
        except (OSError, TimeoutError, URLError, UnicodeDecodeError):
            return self._result(
                output_text=fallback,
                request_kind=request_kind,
                model_version=model_version,
                provider_id=provider.provider_id,
                endpoint=endpoint,
                prompt_hash=prompt_hash,
                frame_ids=frame_ids,
                latency_ms=_elapsed_ms(started),
                parse_ok=False,
                cache_hit=False,
                fallback_reason="http_error",
            )

        output_text = provider.parse_response(body=body, fallback=fallback)
        parse_ok = output_text != fallback or not fallback.strip()
        self._cache[cache_key] = output_text
        return self._result(
            output_text=output_text,
            request_kind=request_kind,
            model_version=model_version,
            provider_id=provider.provider_id,
            endpoint=endpoint,
            prompt_hash=prompt_hash,
            frame_ids=frame_ids,
            latency_ms=_elapsed_ms(started),
            parse_ok=parse_ok,
            cache_hit=False,
            fallback_reason=None if parse_ok else "provider_fallback",
        )

    def _result(
        self,
        *,
        output_text: str,
        request_kind: str,
        model_version: str,
        provider_id: str,
        endpoint: str,
        prompt_hash: str,
        frame_ids: tuple[str, ...],
        latency_ms: int,
        parse_ok: bool,
        cache_hit: bool,
        fallback_reason: str | None = None,
    ) -> ModelGatewayResult:
        telemetry = ModelGatewayTelemetry(
            request_kind=request_kind,
            model_version=model_version,
            provider_id=provider_id,
            endpoint=endpoint,
            prompt_hash=prompt_hash,
            frame_ids=frame_ids,
            latency_ms=latency_ms,
            parse_ok=parse_ok,
            cache_hit=cache_hit,
            seen_at=datetime.now(tz=UTC),
            fallback_reason=fallback_reason,
        )
        if self.telemetry_sink is not None:
            self.telemetry_sink.append(telemetry)
        return ModelGatewayResult(output_text=output_text, telemetry=telemetry)


def _cache_key(
    *,
    endpoint: str,
    provider_id: str,
    model_version: str,
    prompt_hash: str,
    frame_ids: tuple[str, ...],
) -> str:
    payload = {
        "endpoint": endpoint,
        "provider_id": provider_id,
        "model_version": model_version,
        "prompt_hash": prompt_hash,
        "frame_ids": frame_ids,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _prompt_hash(payload: Any) -> str:
    serialized = json.dumps(payload.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def _elapsed_ms(started: float) -> int:
    return int((monotonic() - started) * 1000)
