from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from pydantic import ValidationError

from app.schemas.agent import (
    AtlasAgentPlan,
    AtlasAgentPlannerMode,
    AtlasAgentPlannerReason,
)
from app.schemas.asset import Asset
from app.schemas.lead import Lead
from app.schemas.planner_payload import PlannerRequestPayload, PlannerTextInput
from app.services.agent_prompt_builder import AgentPlannerPrompt, AgentPlannerPromptBuilder
from app.services.agent_provider import HttpAgentPlannerProvider
from app.services.model_gateway import ModelGateway


class RawAgentPlannerBackend(Protocol):
    def generate(
        self,
        *,
        payload: PlannerRequestPayload,
        fallback_plan: AtlasAgentPlan,
    ) -> "AgentPlannerBackendResult": ...


@dataclass(frozen=True)
class AgentPlannerBackendResult:
    raw_text: str
    reason: AtlasAgentPlannerReason | None = None


@dataclass(frozen=True)
class AgentPlannerDecision:
    plan: AtlasAgentPlan
    mode: AtlasAgentPlannerMode
    reason: AtlasAgentPlannerReason | None = None


class FixtureAgentPlannerBackend:
    def generate(
        self,
        *,
        payload: PlannerRequestPayload,
        fallback_plan: AtlasAgentPlan,
    ) -> AgentPlannerBackendResult:
        _ = payload
        return AgentPlannerBackendResult(raw_text=fallback_plan.model_dump_json(exclude_none=True))


class HttpAgentPlannerBackend:
    def __init__(
        self,
        *,
        endpoint: str,
        provider: HttpAgentPlannerProvider,
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
        payload: PlannerRequestPayload,
        fallback_plan: AtlasAgentPlan,
    ) -> AgentPlannerBackendResult:
        fallback = fallback_plan.model_dump_json(exclude_none=True)
        result = self.gateway.invoke(
            endpoint=self.endpoint,
            provider=self.provider,
            payload=payload,
            api_key=self.api_key,
            fallback=fallback,
            request_kind="planner",
        )
        return AgentPlannerBackendResult(
            raw_text=result.output_text,
            reason=(
                "planner_http_failed"
                if result.telemetry.fallback_reason == "http_error"
                or result.telemetry.fallback_reason == "http_status"
                else None
            ),
        )


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
        leads: list[Lead],
        selected_asset: Asset | None,
        selected_lead: Lead | None,
    ) -> AgentPlannerPrompt:
        return self.prompt_builder.build(
            query=query,
            assets=assets,
            leads=leads,
            selected_asset=selected_asset,
            selected_lead=selected_lead,
        )

    def build_payload(
        self,
        *,
        query: str,
        assets: list[Asset],
        leads: list[Lead],
        selected_asset: Asset | None,
        selected_lead: Lead | None,
    ) -> PlannerRequestPayload:
        prompt = self.build_prompt(
            query=query,
            assets=assets,
            leads=leads,
            selected_asset=selected_asset,
            selected_lead=selected_lead,
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
        leads: list[Lead],
        selected_asset: Asset | None,
        selected_lead: Lead | None,
        fallback_plan: AtlasAgentPlan,
    ) -> AgentPlannerDecision:
        payload = self.build_payload(
            query=query,
            assets=assets,
            leads=leads,
            selected_asset=selected_asset,
            selected_lead=selected_lead,
        )
        backend_result = self.backend.generate(
            payload=payload,
            fallback_plan=fallback_plan,
        )
        if backend_result.reason is not None:
            return AgentPlannerDecision(
                plan=fallback_plan,
                mode="fallback",
                reason=backend_result.reason,
            )

        parsed = self.parse_plan(
            raw_text=backend_result.raw_text,
            fallback_plan=fallback_plan,
        )
        if parsed is None:
            return AgentPlannerDecision(
                plan=fallback_plan,
                mode="fallback",
                reason="planner_invalid_json",
            )
        return AgentPlannerDecision(plan=parsed, mode="live")

    def parse_plan(
        self,
        *,
        raw_text: str,
        fallback_plan: AtlasAgentPlan,
    ) -> AtlasAgentPlan | None:
        _ = fallback_plan
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
        return None


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
