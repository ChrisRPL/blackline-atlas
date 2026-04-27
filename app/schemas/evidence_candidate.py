from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.alert import Action, CivilianImpact, EventType, Severity

VisualEvidenceTag = Literal[
    "no_visible_change",
    "low_visibility",
    "sar_speckle_or_modality_artifact",
    "seasonal_or_lighting_change",
    "construction_or_non_conflict_change",
    "collapsed_building",
    "roof_loss",
    "missing_building_footprint",
    "debris_field",
    "burn_scar",
    "blast_or_crater_scarring",
    "damaged_warehouse_block",
    "damaged_port_or_logistics_apron",
    "damaged_bridge_or_access_span",
    "damaged_water_or_power_facility",
    "damaged_market_or_civilian_cluster",
    "large_rubble_field",
    "broad_urban_destruction",
]
EvidenceStrength = Literal["none", "weak", "moderate", "strong"]
DamageMechanism = Literal[
    "none",
    "explosion_or_blast",
    "explosion_blast",
    "fire_or_burn",
    "fire_burning",
    "structural_collapse",
    "access_obstruction",
    "airstrike_or_artillery",
    "ground_assault",
    "earthquake_shaking",
    "flood_inundation",
    "unknown_conflict_damage",
    "unknown_conflict",
    "unclear_human_made",
    "non_conflict_change",
    "modality_artifact",
    "low_visibility",
]
VisibilityQuality = Literal[
    "excellent",
    "good",
    "fair",
    "poor",
    "unusable",
    "clear",
    "usable",
    "low_visibility",
    "obscured",
    "cross_modality",
]
NegativeType = Literal[
    "none",
    "unchanged_control",
    "unchanged_civilian_site",
    "near_conflict_no_damage",
    "low_visibility",
    "low_visibility_cloud",
    "sar_speckle_or_modality_artifact",
    "sar_speckle_artifact",
    "seasonal_or_lighting_change",
    "seasonal_lighting_change",
    "construction_or_non_conflict_change",
    "construction_non_conflict",
    "modality_mismatch",
    "unrelated_land_change",
]
BBoxQuality = Literal["none", "null", "tight", "coarse", "weak_whole_tile"]
CivilianInfrastructureType = Literal[
    "none",
    "grain_port",
    "grain_storage_complex",
    "container_port",
    "bridge",
    "civilian_building_cluster",
    "road_access_corridor",
    "water_infrastructure",
    "logistics_hub",
    "rail_yard",
    "aid_corridor_node",
    "aid_shelter_campus",
    "aid_warehouse_cluster",
    "medical_aid_node",
    "market_or_commercial_cluster",
    "power_or_energy_infrastructure",
    "unknown_civilian_infrastructure",
    "residential_block",
    "apartment_complex",
    "port_logistics_apron",
    "market_bazaar",
    "warehouse_storage",
    "water_treatment",
    "hospital_clinic",
    "school_university",
    "bridge_access_span",
]


class EvidenceFirstCandidate(BaseModel):
    visual_evidence_tags: list[VisualEvidenceTag] = Field(min_length=1)
    evidence_strength: EvidenceStrength
    damage_mechanism: DamageMechanism
    visibility_quality: VisibilityQuality
    negative_type: NegativeType
    bbox_norm: tuple[float, float, float, float] | None
    bbox_quality: BBoxQuality
    change_confidence: float = Field(ge=0.0, le=1.0)
    civilian_infrastructure_type: CivilianInfrastructureType
    rationale: str
    triage_action: Action
    event_type: EventType | None = None
    severity: Severity | None = None
    civilian_impact: CivilianImpact | None = None

    @field_validator("bbox_norm")
    @classmethod
    def validate_bbox_norm(
        cls,
        value: tuple[float, float, float, float] | None,
    ) -> tuple[float, float, float, float] | None:
        if value is None:
            return value
        x1, y1, x2, y2 = value
        if not all(0.0 <= component <= 1.0 for component in value):
            raise ValueError("bbox_norm coordinates must be normalized between 0 and 1")
        if x1 >= x2 or y1 >= y2:
            raise ValueError("bbox_norm coordinates must define a positive rectangle")
        return value

    @model_validator(mode="after")
    def validate_bbox_policy(self) -> EvidenceFirstCandidate:
        if self.triage_action == "downlink_now" and self.bbox_norm is None:
            raise ValueError("downlink_now requires a defensible bbox_norm")
        if self.bbox_norm is None and self.bbox_quality not in {"none", "null"}:
            raise ValueError("bbox_quality must be none or null when bbox_norm is null")
        if self.bbox_norm is not None and self.bbox_quality in {"none", "null"}:
            raise ValueError("bbox_quality must describe any non-null bbox_norm")
        return self


EVIDENCE_FIRST_KEYS = {
    "visual_evidence_tags",
    "evidence_strength",
    "damage_mechanism",
    "visibility_quality",
    "negative_type",
    "bbox_norm",
    "bbox_quality",
    "change_confidence",
    "civilian_infrastructure_type",
    "rationale",
    "triage_action",
}


def is_evidence_first_payload(payload: dict[str, object]) -> bool:
    return bool(EVIDENCE_FIRST_KEYS.intersection(payload))


def normalize_evidence_first_payload(payload: dict[str, object]) -> dict[str, object]:
    evidence = EvidenceFirstCandidate.model_validate(payload)
    bbox = evidence.bbox_norm or (0.0, 0.0, 1.0, 1.0)
    return {
        "event_type": evidence.event_type or _derive_event_type(evidence),
        "severity": evidence.severity or _derive_severity(evidence),
        "confidence": evidence.change_confidence,
        "bbox": bbox,
        "civilian_impact": evidence.civilian_impact or _derive_civilian_impact(evidence),
        "why": evidence.rationale,
        "action": evidence.triage_action,
    }


def _derive_event_type(evidence: EvidenceFirstCandidate) -> EventType:
    if evidence.triage_action == "discard":
        return "no_event"
    if (
        "damaged_bridge_or_access_span" in evidence.visual_evidence_tags
        or evidence.damage_mechanism == "access_obstruction"
        or evidence.civilian_infrastructure_type == "bridge_access_span"
    ):
        return "probable_access_obstruction"
    if evidence.triage_action == "defer" or evidence.evidence_strength in {"weak", "moderate"}:
        return "probable_surface_change"
    return "probable_large_scale_disruption"


def _derive_severity(evidence: EvidenceFirstCandidate) -> Severity:
    if evidence.triage_action == "discard":
        return "low"
    if evidence.triage_action == "defer" or evidence.evidence_strength == "moderate":
        return "medium"
    return "high"


def _derive_civilian_impact(evidence: EvidenceFirstCandidate) -> CivilianImpact:
    if evidence.triage_action == "discard":
        return "no_material_impact"
    infrastructure = evidence.civilian_infrastructure_type
    if infrastructure in {"water_infrastructure", "water_treatment"}:
        return "water_service_disruption"
    if infrastructure in {"bridge", "bridge_access_span", "road_access_corridor", "rail_yard"}:
        return "public_mobility_disruption"
    if infrastructure in {
        "grain_port",
        "grain_storage_complex",
        "container_port",
        "port_logistics_apron",
        "logistics_hub",
        "aid_corridor_node",
        "aid_warehouse_cluster",
        "warehouse_storage",
    }:
        return "shipping_or_aid_disruption"
    return "civilian_facility_disruption"
