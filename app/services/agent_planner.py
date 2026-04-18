from __future__ import annotations

import json
from typing import Protocol
from urllib.error import URLError
from urllib.request import urlopen

from pydantic import ValidationError

from app.schemas.agent import AtlasAgentPlan
from app.schemas.asset import Asset
from app.schemas.planner_payload import PlannerRequestPayload, PlannerTextInput
from app.services.agent_prompt_builder import AgentPlannerPrompt, AgentPlannerPromptBuilder
from app.services.agent_provider import HttpAgentPlannerProvider


class RawAgentPlannerBackend(Protocol):
    def generate(
        self,
        *,
        payload: PlannerRequestPayload,
        fallback_plan: AtlasAgentPlan,
    ) -> str: ...


class FixtureAgentPlannerBackend:
    def generate(
        self,
        *,
        payload: PlannerRequestPayload,
        fallback_plan: AtlasAgentPlan,
    ) -> str:
        _ = payload
        return fallback_plan.model_dump_json(exclude_none=True)


class HttpAgentPlannerBackend:
    def __init__(
        self,
        *,
        endpoint: str,
        provider: HttpAgentPlannerProvider,
        api_key: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.endpoint = endpoint
        self.provider = provider
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def generate(
        self,
        *,
        payload: PlannerRequestPayload,
        fallback_plan: AtlasAgentPlan,
    ) -> str:
        request = self.provider.build_request(
            endpoint=self.endpoint,
            payload=payload,
            api_key=self.api_key,
        )
        fallback = fallback_plan.model_dump_json(exclude_none=True)

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                if response.status != 200:
                    return fallback
                body = response.read().decode("utf-8")
        except (OSError, URLError, UnicodeDecodeError):
            return fallback

        return self.provider.parse_response(body=body, fallback=fallback)


class PromptedAtlasAgentPlanner:
    def __init__(
        self,
        *,
        model_version: str,
        backend: RawAgentPlannerBackend,
        prompt_builder: AgentPlannerPromptBuilder | None = None,
    ) -> None:
        self.model_version = model_version
        self.backend = backend
        self.prompt_builder = prompt_builder or AgentPlannerPromptBuilder()

    def build_prompt(
        self,
        *,
        query: str,
        assets: list[Asset],
        selected_asset: Asset | None,
    ) -> AgentPlannerPrompt:
        return self.prompt_builder.build(
            query=query,
            assets=assets,
            selected_asset=selected_asset,
        )

    def build_payload(
        self,
        *,
        query: str,
        assets: list[Asset],
        selected_asset: Asset | None,
    ) -> PlannerRequestPayload:
        prompt = self.build_prompt(
            query=query,
            assets=assets,
            selected_asset=selected_asset,
        )
        return PlannerRequestPayload(
            model_version=self.model_version,
            inputs=[
                PlannerTextInput(type="input_text", role="system", text=prompt.system),
                PlannerTextInput(type="input_text", role="user", text=prompt.user),
            ],
        )

    def plan(
        self,
        *,
        query: str,
        assets: list[Asset],
        selected_asset: Asset | None,
        fallback_plan: AtlasAgentPlan,
    ) -> AtlasAgentPlan:
        payload = self.build_payload(
            query=query,
            assets=assets,
            selected_asset=selected_asset,
        )
        raw_text = self.backend.generate(
            payload=payload,
            fallback_plan=fallback_plan,
        )
        return self.parse_plan(raw_text=raw_text, fallback_plan=fallback_plan)

    def parse_plan(self, *, raw_text: str, fallback_plan: AtlasAgentPlan) -> AtlasAgentPlan:
        for blob in _json_blobs(raw_text):
            try:
                payload = json.loads(blob)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            try:
                return AtlasAgentPlan.model_validate(payload)
            except ValidationError:
                continue
        return fallback_plan


def _json_blobs(raw_text: str) -> list[str]:
    text = raw_text.strip()
    if not text:
        return []

    blobs = [text]
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
        if stripped and stripped not in blobs:
            blobs.append(stripped)

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
        excerpt = text[first_brace : last_brace + 1]
        if excerpt not in blobs:
            blobs.append(excerpt)

    return blobs
