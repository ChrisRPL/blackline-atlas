from __future__ import annotations

from dataclasses import dataclass

from app.schemas.alert import Alert
from app.schemas.frame import FrameEnvelope
from app.schemas.metrics import Metrics
from app.services.alert_pipeline import StructuredAlertPipeline
from app.services.baseline_compare import FixtureBaselineComparator
from app.services.frame_filters import FrameFilterPolicy
from app.services.scenario_fixtures import ScenarioFixture


@dataclass(frozen=True)
class ScenarioEvaluation:
    current_frame: FrameEnvelope
    baseline_frame: FrameEnvelope
    alerts: list[Alert]
    metrics: Metrics


class ScenarioEvaluator:
    def __init__(
        self,
        *,
        comparator: FixtureBaselineComparator,
        frame_filter_policy: FrameFilterPolicy,
        alert_pipeline: StructuredAlertPipeline,
    ) -> None:
        self.comparator = comparator
        self.frame_filter_policy = frame_filter_policy
        self.alert_pipeline = alert_pipeline

    def evaluate(
        self,
        *,
        scenario: ScenarioFixture,
        current: FrameEnvelope,
        baseline: FrameEnvelope,
    ) -> ScenarioEvaluation:
        compared = self.comparator.compare(current=current, baseline=baseline)
        decision = self.frame_filter_policy.evaluate(current=compared, baseline=baseline)
        alerts: list[Alert] = []
        accepted_for_alerting = False
        final_reason = decision.reason

        if decision.accepted:
            resolution = self.alert_pipeline.resolve(
                raw_output_text=scenario.model_output_text,
                alert_seed=scenario.alerts[0] if scenario.alerts else None,
                current_frame_id=compared.frame.frame_id,
                baseline_frame_id=compared.baseline_frame_id or baseline.frame.frame_id,
            )
            final_reason = resolution.reason
            if resolution.alert is not None:
                alerts = [resolution.alert]
                accepted_for_alerting = True

        current_frame = compared.model_copy(
            update={
                "accepted_for_alerting": accepted_for_alerting,
                "filter_reason": final_reason,
                "overlay_ref": compared.overlay_ref if accepted_for_alerting else None,
            }
        )
        metrics = _derive_metrics(
            seed=scenario.metrics,
            expected_alert_count=len(scenario.alerts),
            emitted_alert_count=len(alerts),
        )
        return ScenarioEvaluation(
            current_frame=current_frame,
            baseline_frame=baseline,
            alerts=alerts,
            metrics=metrics,
        )


def _derive_metrics(
    *,
    seed: Metrics,
    expected_alert_count: int,
    emitted_alert_count: int,
) -> Metrics:
    suppressed_delta = max(expected_alert_count - emitted_alert_count, 0)
    alerts_emitted = max(seed.alerts_emitted - suppressed_delta, 0)
    return seed.model_copy(
        update={
            "alerts_emitted": alerts_emitted,
            "raw_frames_suppressed": seed.raw_frames_suppressed + suppressed_delta,
            "downlink_rate": round(alerts_emitted / seed.frames_scanned, 3),
        }
    )
