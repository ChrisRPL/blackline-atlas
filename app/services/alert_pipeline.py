from __future__ import annotations

from dataclasses import dataclass

from app.schemas.alert import Alert, AlertCandidate, AlertSource
from app.services.candidate_guardrails import parse_alert_candidate


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
        return parse_alert_candidate(raw_output_text)
