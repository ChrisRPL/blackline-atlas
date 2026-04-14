from __future__ import annotations

from typing import Mapping, Protocol

from app.schemas.frame import FrameEnvelope
from app.services.frame_types import FrameRequest
from app.services.scenario_fixtures import ScenarioFixture


class SentinelSource(Protocol):
    def get_current_frame(self, request: FrameRequest) -> FrameEnvelope: ...

    def get_baseline_frame(self, request: FrameRequest) -> FrameEnvelope: ...


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
