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
Return an evidence-first candidate, not a full alert.
Do not add markdown, prose, or code fences.
Never omit required keys.
change_confidence must be a numeric decimal between 0.0 and 1.0.
Never use words like low, medium, or high for confidence.

Required JSON keys only, in this order:
visual_evidence_tags
evidence_strength
damage_mechanism
visibility_quality
negative_type
bbox_norm
bbox_quality
change_confidence
civilian_infrastructure_type
event_type
severity
civilian_impact
rationale
triage_action

Allowed visual_evidence_tags:
no_visible_change | low_visibility | sar_speckle_or_modality_artifact |
seasonal_or_lighting_change | construction_or_non_conflict_change |
collapsed_building | roof_loss | missing_building_footprint | debris_field |
burn_scar | blast_or_crater_scarring | damaged_warehouse_block |
damaged_port_or_logistics_apron | damaged_bridge_or_access_span |
damaged_water_or_power_facility | damaged_market_or_civilian_cluster |
large_rubble_field | broad_urban_destruction
Allowed evidence_strength: none | weak | moderate | strong
Allowed damage_mechanism:
none | explosion_or_blast | fire_or_burn | structural_collapse |
access_obstruction | unknown_conflict_damage | non_conflict_change |
modality_artifact | low_visibility
Allowed visibility_quality: clear | usable | low_visibility | obscured | cross_modality
Allowed negative_type:
none | unchanged_control | low_visibility | sar_speckle_or_modality_artifact |
seasonal_or_lighting_change | construction_or_non_conflict_change |
unrelated_land_change
Allowed bbox_quality: none | tight | coarse | weak_whole_tile

Allowed event_type:
probable_large_scale_disruption | probable_surface_change |
probable_access_obstruction | no_event
Allowed severity: low | medium | high
Allowed civilian_impact:
shipping_or_aid_disruption | logistics_delay | trade_disruption |
civilian_facility_disruption | public_mobility_disruption |
water_service_disruption | no_material_impact
Allowed triage_action: discard | defer | downlink_now

Visual evidence guidance:
- positive tags must be visible in the image pair, not inferred from the region name
- no_visible_change means the civilian site looks materially stable versus baseline
- sar_speckle_or_modality_artifact means apparent change is likely caused by modality,
  radar speckle, or viewing geometry rather than disruption
- construction_or_non_conflict_change means visible change is plausible but not
  conflict disruption
- weak whole-tile boxes should be marked bbox_quality=weak_whole_tile and downgraded
  unless broad_urban_destruction genuinely fills the tile

Derived event guidance:
- probable_large_scale_disruption: major structural loss, burn scar,
  collapse, or large facility-footprint damage
- if an intact civilian facility block in the baseline is visibly blown out,
  collapsed, burned, or removed in the current image, use
  probable_large_scale_disruption even if the exact sub-facility name is unclear
- examples of probable_large_scale_disruption:
  grain silos destroyed, warehouse block burned, port terminal apron scarred,
  a large water-plant treatment block destroyed,
  or a civilian building cluster heavily damaged after disaster
- probable_access_obstruction: bridge, berth, road, or access path
  materially blocked while the wider facility mostly remains
- no_event: no clear macro-visible civilian disruption, weak signal, or weather-limited read

Action guidance:
- downlink_now: clear macro-visible civilian disruption
- defer: plausible disruption but still ambiguous; use this instead of no_event
  when a large civilian facility appears damaged but visibility is imperfect
- discard: no event, malformed output, or weak evidence

Formatting guidance:
- if event_type=no_event then civilian_impact must be no_material_impact
- if event_type=no_event then triage_action must be discard
- if triage_action=discard then evidence_strength should be none or weak
- bbox_norm may be null when no defensible visible evidence box exists
- rationale must always be one short plain sentence"""


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
- label visible evidence first, then derive triage_action
- bbox_norm must be normalized [x1, y1, x2, y2] or null
- change_confidence must be numeric like 0.84, never a word
- always return all required keys, even for no_event
- use triage_action=discard for malformed, weak, or no-event cases
- if major civilian infrastructure damage is clearly visible, do not use no_event
- if a large civilian facility block is visibly lost or burned, prefer
  probable_large_scale_disruption or defer over no_event
- if you choose no_event, use civilian_impact=no_material_impact
- never invent alert_id, timestamp, asset metadata, or source fields"""


def _format_optional_float(value: float | None) -> str:
    if value is None:
        return "none"
    return f"{value:.2f}"
