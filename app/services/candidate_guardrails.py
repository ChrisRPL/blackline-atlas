from __future__ import annotations

import json

from pydantic import ValidationError

from app.schemas.alert import AlertCandidate
from app.schemas.evidence_candidate import (
    is_evidence_first_payload,
    normalize_evidence_first_payload,
)

NEGATIVE_EVIDENCE_TAGS = {
    "no_visible_change",
    "low_visibility",
    "sar_speckle_or_modality_artifact",
    "seasonal_or_lighting_change",
    "construction_or_non_conflict_change",
}
NEGATIVE_TYPES = {
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
}
ACTION_ALIASES = {
    "alert": "downlink_now",
    "download_now": "downlink_now",
    "downlink": "downlink_now",
    "downlink now": "downlink_now",
    "inspect": "defer",
    "review": "defer",
    "hold": "defer",
    "ignore": "discard",
    "none": "discard",
    "no_action": "discard",
}


def parse_alert_candidate(raw_output_text: str) -> AlertCandidate | None:
    for blob in candidate_json_blobs(raw_output_text):
        try:
            payload = json.loads(blob)
        except json.JSONDecodeError:
            continue

        candidate = parse_candidate_payload(payload)
        if candidate is not None:
            return candidate

    return None


def parse_candidate_payload(payload: object) -> AlertCandidate | None:
    payload = unwrap_payload(payload)
    if not isinstance(payload, dict):
        return None

    normalized = normalize_candidate_payload(payload)
    try:
        return AlertCandidate.model_validate(normalized)
    except ValidationError:
        return None


def normalize_candidate_payload(payload: dict[str, object]) -> dict[str, object]:
    normalized = dict(payload)
    _normalize_common_aliases(normalized)

    if is_evidence_first_payload(normalized):
        _apply_evidence_guardrails(normalized)
        try:
            normalized = normalize_evidence_first_payload(normalized)
        except ValidationError:
            return normalized

    _normalize_common_aliases(normalized)
    _apply_alert_guardrails(normalized)
    _repair_safe_discard_payload(normalized)
    return normalized


def candidate_json_blobs(raw_output_text: str) -> list[str]:
    text = raw_output_text.strip()
    if not text:
        return []

    blobs = [text]
    fenced = strip_json_fence(text)
    if fenced != text:
        blobs.append(fenced)

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
        excerpt = text[first_brace : last_brace + 1]
        if excerpt not in blobs:
            blobs.append(excerpt)

    return blobs


def strip_json_fence(text: str) -> str:
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def unwrap_payload(payload: object) -> object:
    if isinstance(payload, list) and len(payload) == 1 and isinstance(payload[0], dict):
        return payload[0]

    if not isinstance(payload, dict):
        return payload

    for key in ("candidate", "alert", "output"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            return nested
    return payload


def _normalize_common_aliases(payload: dict[str, object]) -> None:
    for action_key in ("action", "triage_action"):
        action = payload.get(action_key)
        if isinstance(action, str):
            normalized = action.strip().lower().replace("-", "_")
            payload[action_key] = ACTION_ALIASES.get(normalized, normalized)

    if "visual_evidence_tags" not in payload and "visual_evidence_tag" in payload:
        tag = payload["visual_evidence_tag"]
        payload["visual_evidence_tags"] = [tag] if isinstance(tag, str) else tag

    if "bbox" not in payload and "bounding_box" in payload:
        payload["bbox"] = payload["bounding_box"]
    if "bbox_norm" not in payload and "bbox" in payload and is_evidence_first_payload(payload):
        payload["bbox_norm"] = payload["bbox"]

    confidence = payload.get("confidence")
    if isinstance(confidence, str):
        mapped = _normalize_confidence_string(confidence)
        if mapped is not None:
            payload["confidence"] = mapped

    change_confidence = payload.get("change_confidence")
    if isinstance(change_confidence, str):
        mapped = _normalize_confidence_string(change_confidence)
        if mapped is not None:
            payload["change_confidence"] = mapped


def _apply_evidence_guardrails(payload: dict[str, object]) -> None:
    tags = payload.get("visual_evidence_tags")
    evidence_tags = (
        {tag for tag in tags if isinstance(tag, str)} if isinstance(tags, list) else set()
    )
    positive_tags = evidence_tags - NEGATIVE_EVIDENCE_TAGS
    negative_type = payload.get("negative_type")
    evidence_strength = payload.get("evidence_strength")
    visibility_quality = payload.get("visibility_quality")
    action = payload.get("triage_action")
    low_visibility = visibility_quality in {"poor", "unusable", "low_visibility", "obscured"}
    negative_only = bool(evidence_tags) and not positive_tags
    negative_context = negative_type in NEGATIVE_TYPES or negative_only
    weak_evidence = evidence_strength in {"none", "weak"}

    if action == "downlink_now" and (
        negative_context or weak_evidence or (low_visibility and not positive_tags)
    ):
        payload["triage_action"] = "discard"
    elif action == "defer" and negative_context and weak_evidence:
        payload["triage_action"] = "discard"

    if payload.get("triage_action") == "discard":
        payload["bbox_norm"] = None
        payload["bbox_quality"] = "null"
        confidence = payload.get("change_confidence")
        if isinstance(confidence, (int, float)):
            payload["change_confidence"] = min(float(confidence), 0.35)


def _apply_alert_guardrails(payload: dict[str, object]) -> None:
    action = payload.get("action")
    confidence = payload.get("confidence")
    if action not in {"downlink_now", "defer"} or not isinstance(confidence, (int, float)):
        return

    if confidence < 0.5:
        payload["action"] = "discard"


def _repair_safe_discard_payload(payload: dict[str, object]) -> None:
    if payload.get("action") != "discard":
        return

    payload["event_type"] = "no_event"
    payload["severity"] = "low"
    payload.setdefault("confidence", 0.0)
    payload.setdefault("bbox", [0.0, 0.0, 1.0, 1.0])
    payload["civilian_impact"] = "no_material_impact"
    payload.setdefault("why", "Model returned discard with insufficient disruption evidence.")


def _normalize_confidence_string(value: str) -> float | None:
    normalized = value.strip().lower()
    mapping = {
        "low": 0.25,
        "medium": 0.6,
        "high": 0.9,
    }
    if normalized in mapping:
        return mapping[normalized]
    if normalized.endswith("%"):
        try:
            return max(min(float(normalized[:-1]) / 100.0, 1.0), 0.0)
        except ValueError:
            return None
    try:
        numeric = float(normalized)
    except ValueError:
        return None
    return max(min(numeric, 1.0), 0.0)
