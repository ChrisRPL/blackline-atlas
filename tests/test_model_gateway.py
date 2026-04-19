from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request

from app.services.model_gateway import ModelGateway


def test_model_gateway_caches_by_prompt_hash_and_frame_ids() -> None:
    calls = {"count": 0}
    telemetry = []

    def fake_urlopen(request: Request, timeout: float):
        calls["count"] += 1
        assert timeout == 3.0
        assert request.full_url == "https://example.test/model"
        return _FakeHTTPResponse(body=b'{"output_text":"{\\"action\\":\\"discard\\"}"}')

    gateway = ModelGateway(
        timeout_seconds=3.0,
        telemetry_sink=telemetry,
        opener=fake_urlopen,
    )
    provider = _Provider()
    payload = _Payload(
        {
            "model_version": "LiquidAI/LFM2.5-VL-450M",
            "prompt": "compare current and baseline",
        }
    )

    first = gateway.invoke(
        endpoint="https://example.test/model",
        provider=provider,
        payload=payload,
        api_key="token",
        fallback='{"action":"discard"}',
        request_kind="candidate",
        frame_ids=("cur_1", "base_1"),
    )
    second = gateway.invoke(
        endpoint="https://example.test/model",
        provider=provider,
        payload=payload,
        api_key="token",
        fallback='{"action":"discard"}',
        request_kind="candidate",
        frame_ids=("cur_1", "base_1"),
    )

    assert calls["count"] == 1
    assert first.output_text == '{"action":"discard"}'
    assert first.telemetry.cache_hit is False
    assert first.telemetry.frame_ids == ("cur_1", "base_1")
    assert second.output_text == '{"action":"discard"}'
    assert second.telemetry.cache_hit is True
    assert len(telemetry) == 2


def test_model_gateway_reports_http_error_fallback() -> None:
    telemetry = []

    def fake_urlopen(request: Request, timeout: float):
        _ = request
        _ = timeout
        raise URLError("offline")

    gateway = ModelGateway(telemetry_sink=telemetry, opener=fake_urlopen)

    result = gateway.invoke(
        endpoint="https://example.test/model",
        provider=_Provider(),
        payload=_Payload({"model_version": "planner-model", "prompt": "latest alerts"}),
        api_key=None,
        fallback='{"tool":"latest_alerts"}',
        request_kind="planner",
    )

    assert result.output_text == '{"tool":"latest_alerts"}'
    assert result.telemetry.parse_ok is False
    assert result.telemetry.fallback_reason == "http_error"
    assert result.telemetry.cache_hit is False
    assert telemetry[0].request_kind == "planner"


class _Payload:
    def __init__(self, data: dict[str, object]) -> None:
        self.model_version = str(data["model_version"])
        self._data = data

    def model_dump(self, mode: str = "json") -> dict[str, object]:
        _ = mode
        return dict(self._data)


class _Provider:
    provider_id = "atlas_json_http"

    def build_request(
        self,
        *,
        endpoint: str,
        payload: _Payload,
        api_key: str | None,
    ) -> Request:
        return Request(
            endpoint,
            data=json.dumps(payload.model_dump()).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            method="POST",
        )

    def parse_response(self, *, body: str, fallback: str) -> str:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return fallback
        return str(payload.get("output_text", fallback))


class _FakeHTTPResponse:
    def __init__(self, *, body: bytes, status: int = 200) -> None:
        self._body = body
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = exc_type
        _ = exc
        _ = tb
