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
none | explosion_blast | airstrike_or_artillery | ground_assault |
fire_burning | structural_collapse | access_obstruction | flood_inundation |
earthquake_shaking | unknown_conflict | unclear_human_made |
non_conflict_change | modality_artifact | low_visibility
Allowed visibility_quality: excellent | good | fair | poor | unusable
Allowed negative_type:
none | unchanged_civilian_site | near_conflict_no_damage |
low_visibility_cloud | sar_speckle_artifact | seasonal_lighting_change |
construction_non_conflict | modality_mismatch
Allowed bbox_quality: null | tight | coarse | weak_whole_tile
Allowed civilian_infrastructure_type:
none | residential_block | apartment_complex | port_logistics_apron |
market_bazaar | warehouse_storage | water_treatment | hospital_clinic |
school_university | bridge_access_span
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

Action guidance:
- downlink_now: clear macro-visible civilian disruption
- defer: plausible disruption but still ambiguous; use this instead of no_event
  when a large civilian facility appears damaged but visibility is imperfect
- discard: no event, malformed output, or weak evidence

Formatting guidance:
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
- if major civilian infrastructure damage is clearly visible, do not use no_visible_change
- if a large civilian facility block is visibly lost or burned, prefer positive
  visual_evidence_tags and defer over discard
- never invent alert_id, timestamp, asset metadata, or source fields"""


def _format_optional_float(value: float | None) -> str:
    if value is None:
        return "none"
    return f"{value:.2f}"
