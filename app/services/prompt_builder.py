from __future__ import annotations

from dataclasses import dataclass

from app.schemas.asset import Asset
from app.schemas.frame import FrameEnvelope


@dataclass(frozen=True)
class CandidatePrompt:
    system: str
    user: str

    def render(self) -> str:
        return f"{self.system}\n\n{self.user}".strip()


class CandidatePromptBuilder:
    def build(
        self,
        *,
        asset: Asset,
        current: FrameEnvelope,
        baseline: FrameEnvelope,
    ) -> CandidatePrompt:
        return CandidatePrompt(
            system=_SYSTEM_PROMPT,
            user=_build_user_prompt(
                asset=asset,
                current=current,
                baseline=baseline,
            ),
        )


_SYSTEM_PROMPT = """You are Blackline Atlas candidate generation.
Return one JSON object only.
Return a candidate, not a full alert.
Do not add markdown, prose, or code fences.
Confidence must be a numeric decimal between 0.0 and 1.0.
Never use words like low, medium, or high for confidence.

Allowed event_type:
probable_large_scale_disruption | probable_surface_change |
probable_access_obstruction | no_event
Allowed severity: low | medium | high
Allowed civilian_impact:
shipping_or_aid_disruption | logistics_delay | trade_disruption |
public_mobility_disruption | no_material_impact
Allowed action: discard | defer | downlink_now

Required JSON keys only:
event_type
severity
confidence
bbox
civilian_impact
why
action

Event guidance:
- probable_large_scale_disruption: major structural loss, burn scar,
  collapse, or large facility-footprint damage
- probable_access_obstruction: bridge, berth, road, or access path
  materially blocked while the wider facility mostly remains
- no_event: no clear macro-visible civilian disruption, weak signal, or weather-limited read

Action guidance:
- downlink_now: clear macro-visible civilian disruption
- defer: plausible disruption but still ambiguous
- discard: no event, malformed output, or weak evidence"""


def _build_user_prompt(
    *,
    asset: Asset,
    current: FrameEnvelope,
    baseline: FrameEnvelope,
) -> str:
    current_image = current.frame.image_ref or "none"
    current_overlay = current.overlay_ref or "none"
    baseline_image = baseline.frame.image_ref or "none"

    return f"""Asset
- asset_id: {asset.asset_id}
- asset_name: {asset.asset_name}
- asset_type: {asset.asset_type}
- region: {asset.region}
- hero: {str(asset.hero).lower()}

Current frame
- frame_id: {current.frame.frame_id}
- captured_at: {current.frame.captured_at}
- image_ref: {current_image}
- overlay_ref: {current_overlay}
- cloud_cover: {_format_optional_float(current.frame.cloud_cover)}

Baseline frame
- frame_id: {baseline.frame.frame_id}
- captured_at: {baseline.frame.captured_at}
- image_ref: {baseline_image}
- cloud_cover: {_format_optional_float(baseline.frame.cloud_cover)}

Task
- compare current frame against baseline
- focus on macro-scale civilian disruption only
- bbox must be normalized [x1, y1, x2, y2]
- confidence must be numeric like 0.84, never a word
- use action=discard for malformed, weak, or no-event cases
- if major civilian infrastructure damage is clearly visible, do not use no_event
- never invent alert_id, timestamp, asset metadata, or source fields"""


def _format_optional_float(value: float | None) -> str:
    if value is None:
        return "none"
    return f"{value:.2f}"
