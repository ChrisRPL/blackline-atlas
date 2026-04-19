from __future__ import annotations

from typing import Protocol

from app.schemas.asset import Asset
from app.schemas.frame import FrameEnvelope
from app.schemas.model_payload import (
    CandidateImageInput,
    CandidateRequestPayload,
    CandidateTextInput,
)
from app.services.model_gateway import ModelGateway
from app.services.model_provider import HttpCandidateProvider
from app.services.prompt_builder import CandidatePrompt, CandidatePromptBuilder
from app.services.scenario_fixtures import ScenarioFixture


class RawCandidateBackend(Protocol):
    def generate(
        self,
        *,
        payload: CandidateRequestPayload,
        scenario: ScenarioFixture,
    ) -> str: ...


class FixtureRawCandidateBackend:
    def generate(
        self,
        *,
        payload: CandidateRequestPayload,
        scenario: ScenarioFixture,
    ) -> str:
        _ = payload
        return scenario.model_output_text


class HttpRawCandidateBackend:
    def __init__(
        self,
        *,
        endpoint: str,
        provider: HttpCandidateProvider,
        api_key: str | None = None,
        timeout_seconds: float = 10.0,
        gateway: ModelGateway | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.provider = provider
        self.api_key = api_key
        self.gateway = gateway or ModelGateway(timeout_seconds=timeout_seconds)

    def generate(
        self,
        *,
        payload: CandidateRequestPayload,
        scenario: ScenarioFixture,
    ) -> str:
        result = self.gateway.invoke(
            endpoint=self.endpoint,
            provider=self.provider,
            payload=payload,
            api_key=self.api_key,
            fallback=scenario.model_output_text,
            request_kind="candidate",
            frame_ids=(
                scenario.current_frame.frame.frame_id,
                scenario.baseline_frame.frame.frame_id,
            ),
        )
        return result.output_text


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

    def build_payload(
        self,
        *,
        asset: Asset,
        scenario: ScenarioFixture,
        current: FrameEnvelope,
        baseline: FrameEnvelope,
    ) -> CandidateRequestPayload:
        prompt = self.build_prompt(
            asset=asset,
            current=current,
            baseline=baseline,
        )
        inputs: list[CandidateTextInput | CandidateImageInput] = [
            CandidateTextInput(type="input_text", role="system", text=prompt.system),
            CandidateTextInput(type="input_text", role="user", text=prompt.user),
        ]

        if current.frame.image_ref:
            inputs.append(
                CandidateImageInput(
                    type="input_image",
                    role="current",
                    image_ref=current.frame.image_ref,
                )
            )
        if baseline.frame.image_ref:
            inputs.append(
                CandidateImageInput(
                    type="input_image",
                    role="baseline",
                    image_ref=baseline.frame.image_ref,
                )
            )
        if current.overlay_ref:
            inputs.append(
                CandidateImageInput(
                    type="input_image",
                    role="overlay",
                    image_ref=current.overlay_ref,
                )
            )

        return CandidateRequestPayload(
            model_version=self.model_version,
            asset_id=asset.asset_id,
            scenario_id=scenario.scenario_id,
            inputs=inputs,
        )

    def generate_candidate_text(
        self,
        *,
        asset: Asset,
        scenario: ScenarioFixture,
        current: FrameEnvelope,
        baseline: FrameEnvelope,
    ) -> str:
        payload = self.build_payload(
            asset=asset,
            scenario=scenario,
            current=current,
            baseline=baseline,
        )
        return self.backend.generate(
            payload=payload,
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
