from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol
from urllib.parse import urlencode

from app.schemas.frame import FrameEnvelope
from app.services.frame_types import FrameRequest
from app.services.scenario_fixtures import ScenarioFixture


class SentinelSource(Protocol):
    def get_current_frame(self, request: FrameRequest) -> FrameEnvelope: ...

    def get_baseline_frame(self, request: FrameRequest) -> FrameEnvelope: ...


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
        self.current_endpoint = current_endpoint
        self.baseline_endpoint = baseline_endpoint

    def build_current_plan(self, request: FrameRequest) -> SentinelRequestPlan:
        if not self.current_endpoint:
            raise ValueError("current Sentinel endpoint is not configured")
        return SentinelRequestPlan(
            endpoint=self.current_endpoint,
            params={
                "asset_id": request.asset_id,
                "scenario_id": request.scenario_id,
                "mode": "current",
            },
        )

    def build_baseline_plan(self, request: FrameRequest) -> SentinelRequestPlan:
        if not self.baseline_endpoint:
            raise ValueError("baseline Sentinel endpoint is not configured")
        return SentinelRequestPlan(
            endpoint=self.baseline_endpoint,
            params={
                "asset_id": request.asset_id,
                "scenario_id": request.scenario_id,
                "mode": "baseline",
            },
        )
