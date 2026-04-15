from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol
from urllib.parse import urlencode

from app.schemas.frame import FrameEnvelope, FrameRecord
from app.services.frame_types import FrameRequest
from app.services.scenario_fixtures import ScenarioFixture


class SentinelSource(Protocol):
    def get_current_frame(self, request: FrameRequest) -> FrameEnvelope: ...

    def get_baseline_frame(self, request: FrameRequest) -> FrameEnvelope: ...


class SentinelPayloadTransport(Protocol):
    def fetch(self, plan: SentinelRequestPlan) -> Mapping[str, object] | None: ...


@dataclass(frozen=True)
class SentinelRequestPlan:
    endpoint: str
    params: dict[str, str]

    @property
    def url(self) -> str:
        query = urlencode(self.params)
        return f"{self.endpoint}?{query}" if query else self.endpoint


class FixtureSentinelSource:
    def __init__(self, scenarios: Mapping[str, ScenarioFixture]) -> None:
        self._scenarios = dict(scenarios)

    def get_current_frame(self, request: FrameRequest) -> FrameEnvelope:
        return self._scenario(request.scenario_id).current_frame

    def get_baseline_frame(self, request: FrameRequest) -> FrameEnvelope:
        return self._scenario(request.scenario_id).baseline_frame

    def _scenario(self, scenario_id: str) -> ScenarioFixture:
        if scenario_id not in self._scenarios:
            raise KeyError(f"Unknown scenario fixture: {scenario_id}")
        return self._scenarios[scenario_id]


class ConfiguredSentinelEndpointSource:
    def __init__(
        self,
        *,
        current_endpoint: str | None,
        baseline_endpoint: str | None,
    ) -> None:
        self.current_endpoint = current_endpoint.rstrip("/") if current_endpoint else None
        self.baseline_endpoint = baseline_endpoint.rstrip("/") if baseline_endpoint else None

    def build_current_plan(self, request: FrameRequest) -> SentinelRequestPlan | None:
        if not self.current_endpoint:
            return None
        return SentinelRequestPlan(
            endpoint=self.current_endpoint,
            params={
                "asset_id": request.asset_id,
                "scenario_id": request.scenario_id,
                "mode": "current",
            },
        )

    def build_baseline_plan(self, request: FrameRequest) -> SentinelRequestPlan | None:
        if not self.baseline_endpoint:
            return None
        return SentinelRequestPlan(
            endpoint=self.baseline_endpoint,
            params={
                "asset_id": request.asset_id,
                "scenario_id": request.scenario_id,
                "mode": "baseline",
            },
        )

    def build_current_envelope(
        self, request: FrameRequest, payload: Mapping[str, object]
    ) -> FrameEnvelope:
        return self._build_envelope(
            request=request,
            payload=payload,
            plan=self.build_current_plan(request),
        )

    def build_baseline_envelope(
        self, request: FrameRequest, payload: Mapping[str, object]
    ) -> FrameEnvelope:
        return self._build_envelope(
            request=request,
            payload=payload,
            plan=self.build_baseline_plan(request),
        )

    def _build_envelope(
        self,
        *,
        request: FrameRequest,
        payload: Mapping[str, object],
        plan: SentinelRequestPlan | None,
    ) -> FrameEnvelope:
        source = _string_or_none(payload.get("source")) or (
            plan.url if plan else "sentinel_payload"
        )
        return FrameEnvelope(
            frame=FrameRecord(
                frame_id=_required_string(payload, "frame_id"),
                asset_id=_string_or_none(payload.get("asset_id")) or request.asset_id,
                captured_at=_required_string(payload, "captured_at"),
                image_ref=_string_or_none(payload.get("image_ref")),
                cloud_cover=_float_or_none(payload.get("cloud_cover")),
                source=source,
            ),
            baseline_frame_id=_string_or_none(payload.get("baseline_frame_id")),
            overlay_ref=_string_or_none(payload.get("overlay_ref")),
            accepted_for_alerting=_bool_or_none(payload.get("accepted_for_alerting")),
            filter_reason=_string_or_none(payload.get("filter_reason")),
        )


class CurrentSentinelAdapter:
    def __init__(
        self,
        *,
        planner: ConfiguredSentinelEndpointSource,
        fallback: SentinelSource,
        transport: SentinelPayloadTransport | None = None,
    ) -> None:
        self._planner = planner
        self._fallback = fallback
        self._transport = transport

    def get_current_frame(self, request: FrameRequest) -> FrameEnvelope:
        plan = self._planner.build_current_plan(request)
        if plan is None:
            return self._fallback.get_current_frame(request)

        if self._transport is not None:
            payload = self._transport.fetch(plan)
            if payload is not None:
                return self._planner.build_current_envelope(request, payload)

        envelope = self._fallback.get_current_frame(request)

        return envelope.model_copy(
            update={
                "frame": envelope.frame.model_copy(
                    update={
                        "source": plan.url,
                    }
                )
            }
        )

    def get_baseline_frame(self, request: FrameRequest) -> FrameEnvelope:
        return self._fallback.get_baseline_frame(request)


class BaselineSentinelAdapter:
    def __init__(
        self,
        *,
        planner: ConfiguredSentinelEndpointSource,
        fallback: SentinelSource,
        transport: SentinelPayloadTransport | None = None,
    ) -> None:
        self._planner = planner
        self._fallback = fallback
        self._transport = transport

    def get_current_frame(self, request: FrameRequest) -> FrameEnvelope:
        return self._fallback.get_current_frame(request)

    def get_baseline_frame(self, request: FrameRequest) -> FrameEnvelope:
        plan = self._planner.build_baseline_plan(request)
        if plan is None:
            return self._fallback.get_baseline_frame(request)

        if self._transport is not None:
            payload = self._transport.fetch(plan)
            if payload is not None:
                return self._planner.build_baseline_envelope(request, payload)

        envelope = self._fallback.get_baseline_frame(request)

        return envelope.model_copy(
            update={
                "frame": envelope.frame.model_copy(
                    update={
                        "source": plan.url,
                    }
                )
            }
        )


def _required_string(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Sentinel payload missing required string field: {key}")
    return value


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raise ValueError("Sentinel payload field cloud_cover must be numeric when provided")


def _bool_or_none(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise ValueError("Sentinel payload boolean fields must be bool when provided")
