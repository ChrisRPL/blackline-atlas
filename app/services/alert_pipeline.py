from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import ValidationError

from app.schemas.alert import Alert, AlertCandidate, AlertSource


@dataclass(frozen=True)
class AlertResolution:
    reason: str
    candidate: AlertCandidate | None = None
    alert: Alert | None = None


class StructuredAlertPipeline:
    def __init__(self, *, model_version: str) -> None:
        self.model_version = model_version

    def resolve(
        self,
        *,
        raw_output_text: str,
        alert_seed: Alert | None,
        current_frame_id: str,
        baseline_frame_id: str,
    ) -> AlertResolution:
        candidate = self.parse_candidate(raw_output_text)
        if candidate is None:
            return AlertResolution(reason="invalid_model_output")

        if candidate.action == "discard":
            return AlertResolution(reason="model_discarded", candidate=candidate)

        if alert_seed is None:
            return AlertResolution(reason="missing_alert_seed", candidate=candidate)

        return AlertResolution(
            reason="accepted",
            candidate=candidate,
            alert=Alert(
                alert_id=alert_seed.alert_id,
                timestamp=alert_seed.timestamp,
                asset_id=alert_seed.asset_id,
                asset_name=alert_seed.asset_name,
                asset_type=alert_seed.asset_type,
                event_type=candidate.event_type,
                severity=candidate.severity,
                confidence=candidate.confidence,
                bbox=candidate.bbox,
                civilian_impact=candidate.civilian_impact,
                why=candidate.why,
                action=candidate.action,
                source=AlertSource(
                    current_frame_id=current_frame_id,
                    baseline_frame_id=baseline_frame_id,
                    model_version=self.model_version,
                ),
            ),
        )

    def parse_candidate(self, raw_output_text: str) -> AlertCandidate | None:
        for blob in _candidate_json_blobs(raw_output_text):
            try:
                payload = json.loads(blob)
            except json.JSONDecodeError:
                continue

            payload = _unwrap_payload(payload)
            if not isinstance(payload, dict):
                continue

            try:
                return AlertCandidate.model_validate(payload)
            except ValidationError:
                continue

        return None


def _candidate_json_blobs(raw_output_text: str) -> list[str]:
    text = raw_output_text.strip()
    if not text:
        return []

    blobs = [text]
    fenced = _strip_json_fence(text)
    if fenced != text:
        blobs.append(fenced)

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
        excerpt = text[first_brace : last_brace + 1]
        if excerpt not in blobs:
            blobs.append(excerpt)

    return blobs


def _strip_json_fence(text: str) -> str:
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _unwrap_payload(payload: object) -> object:
    if not isinstance(payload, dict):
        return payload

    for key in ("candidate", "alert", "output"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            return nested
    return payload
