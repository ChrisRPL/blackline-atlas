from __future__ import annotations

from typing import Protocol

from app.schemas.asset import Asset
from app.schemas.frame import FrameEnvelope
from app.services.prompt_builder import CandidatePrompt, CandidatePromptBuilder
from app.services.scenario_fixtures import ScenarioFixture


class RawCandidateBackend(Protocol):
    def generate(
        self,
        *,
        prompt: CandidatePrompt,
        model_version: str,
        scenario: ScenarioFixture,
    ) -> str: ...


class FixtureRawCandidateBackend:
    def generate(
        self,
        *,
        prompt: CandidatePrompt,
        model_version: str,
        scenario: ScenarioFixture,
    ) -> str:
        _ = prompt
        _ = model_version
        return scenario.model_output_text


class PromptedCandidateModel:
    def __init__(
        self,
        *,
        model_version: str,
        backend: RawCandidateBackend,
        prompt_builder: CandidatePromptBuilder | None = None,
    ) -> None:
        self.model_version = model_version
        self.backend = backend
        self.prompt_builder = prompt_builder or CandidatePromptBuilder()

    def build_prompt(
        self,
        *,
        asset: Asset,
        current: FrameEnvelope,
        baseline: FrameEnvelope,
    ) -> CandidatePrompt:
        return self.prompt_builder.build(
            asset=asset,
            current=current,
            baseline=baseline,
        )

    def generate_candidate_text(
        self,
        *,
        asset: Asset,
        scenario: ScenarioFixture,
        current: FrameEnvelope,
        baseline: FrameEnvelope,
    ) -> str:
        prompt = self.build_prompt(
            asset=asset,
            current=current,
            baseline=baseline,
        )
        return self.backend.generate(
            prompt=prompt,
            model_version=self.model_version,
            scenario=scenario,
        )

    def generate_raw_candidate_text(
        self,
        *,
        asset: Asset,
        scenario: ScenarioFixture,
        current: FrameEnvelope,
        baseline: FrameEnvelope,
    ) -> str:
        return self.generate_candidate_text(
            asset=asset,
            scenario=scenario,
            current=current,
            baseline=baseline,
        )
