from __future__ import annotations

import json
from typing import Protocol, get_args

from pydantic import ValidationError

from app.schemas.alert import Alert
from app.schemas.asset import Asset
from app.schemas.evidence_candidate import VisualEvidenceTag
from app.schemas.frame import FrameEnvelope
from app.schemas.liquid_analyst import LiquidAnalystBackendMode, LiquidAnalystReport
from app.schemas.model_payload import (
    CandidateImageInput,
    CandidateRequestPayload,
    CandidateTextInput,
)
from app.schemas.sam3_evidence import Sam3EvidenceReport
from app.services.model_gateway import ModelGateway
from app.services.model_provider import HttpCandidateProvider


class LiquidAnalystBackend(Protocol):
    backend_id: LiquidAnalystBackendMode

    def analyze(
        self,
        *,
        asset: Asset,
        current: FrameEnvelope,
        baseline: FrameEnvelope,
        evidence: Sam3EvidenceReport | None,
        alert: Alert | None,
        model_version: str,
    ) -> LiquidAnalystReport: ...


class FixtureLiquidAnalystBackend:
    backend_id: LiquidAnalystBackendMode = "fixture"

    def analyze(
        self,
        *,
        asset: Asset,
        current: FrameEnvelope,
        baseline: FrameEnvelope,
        evidence: Sam3EvidenceReport | None,
        alert: Alert | None,
        model_version: str,
    ) -> LiquidAnalystReport:
        tags = list(evidence.visual_evidence_tags if evidence else [])
        action = alert.action if alert else (evidence.triage_action if evidence else "discard")
        confidence = alert.confidence if alert else _evidence_confidence(evidence)
        severity_hint = _severity_hint(action=action, confidence=confidence)
        if action == "discard":
            summary = (
                "No defensible macro-scale civilian disruption is confirmed in the " "loaded pair."
            )
            negative_evidence = ["no_visible_change"] if not tags else tags
        else:
            tag_summary = (
                ", ".join(tag.replace("_", " ") for tag in tags) or "visible civilian disruption"
            )
            summary = (
                f"{asset.asset_name} shows {tag_summary} "
                "between the baseline and current images."
            )
            negative_evidence = []

        return LiquidAnalystReport(
            asset_id=asset.asset_id,
            current_frame_id=current.frame.frame_id,
            baseline_frame_id=baseline.frame.frame_id,
            current_image_ref=current.frame.image_ref,
            baseline_image_ref=baseline.frame.image_ref,
            model_version=model_version,
            backend="fixture",
            status="ready",
            visible_change_summary=summary,
            civilian_disruption_evidence=tags,
            negative_evidence=negative_evidence,
            uncertainty_factors=_uncertainty_factors(current=current, baseline=baseline),
            severity_hint=severity_hint,
            recommended_action=action,
            confidence=confidence,
            short_rationale=alert.why if alert else (evidence.summary if evidence else summary),
        )


class HttpLiquidAnalystBackend:
    backend_id: LiquidAnalystBackendMode = "liquid_vlm_http"

    def __init__(
        self,
        *,
        endpoint: str,
        provider: HttpCandidateProvider,
        api_key: str | None = None,
        timeout_seconds: float = 20.0,
        gateway: ModelGateway | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.provider = provider
        self.api_key = api_key
        self.gateway = gateway or ModelGateway(timeout_seconds=timeout_seconds)

    def analyze(
        self,
        *,
        asset: Asset,
        current: FrameEnvelope,
        baseline: FrameEnvelope,
        evidence: Sam3EvidenceReport | None,
        alert: Alert | None,
        model_version: str,
    ) -> LiquidAnalystReport:
        fallback = _unavailable_report(
            asset=asset,
            current=current,
            baseline=baseline,
            evidence=evidence,
            model_version=model_version,
            backend="liquid_vlm_http",
            reason="Liquid analyst endpoint did not return a valid civilian report.",
        )
        payload = _build_payload(
            asset=asset,
            current=current,
            baseline=baseline,
            evidence=evidence,
            model_version=model_version,
        )
        result = self.gateway.invoke(
            endpoint=self.endpoint,
            provider=self.provider,
            payload=payload,
            api_key=self.api_key,
            fallback=fallback.model_dump_json(),
            request_kind="liquid_analyst",
            frame_ids=(current.frame.frame_id, baseline.frame.frame_id),
        )
        parsed = parse_liquid_analyst_report(
            result.output_text,
            asset=asset,
            current=current,
            baseline=baseline,
            evidence=evidence,
            model_version=model_version,
            backend="liquid_vlm_http",
        )
        return parsed or fallback


class LiquidAnalystService:
    def __init__(
        self,
        *,
        model_version: str,
        backend: LiquidAnalystBackend,
    ) -> None:
        self.model_version = model_version
        self.backend = backend

    def analyze(
        self,
        *,
        asset: Asset,
        current: FrameEnvelope,
        baseline: FrameEnvelope,
        evidence: Sam3EvidenceReport | None,
        alert: Alert | None,
    ) -> LiquidAnalystReport:
        return self.backend.analyze(
            asset=asset,
            current=current,
            baseline=baseline,
            evidence=evidence,
            alert=alert,
            model_version=self.model_version,
        )


def parse_liquid_analyst_report(
    raw_text: str,
    *,
    asset: Asset,
    current: FrameEnvelope,
    baseline: FrameEnvelope,
    evidence: Sam3EvidenceReport | None,
    model_version: str,
    backend: LiquidAnalystBackendMode,
) -> LiquidAnalystReport | None:
    for blob in _json_blobs(raw_text):
        try:
            payload = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        normalized = {
            **payload,
            "asset_id": asset.asset_id,
            "current_frame_id": current.frame.frame_id,
            "baseline_frame_id": baseline.frame.frame_id,
            "current_image_ref": current.frame.image_ref,
            "baseline_image_ref": baseline.frame.image_ref,
            "model_version": model_version,
            "backend": backend,
            "status": "ready",
        }
        normalized["civilian_disruption_evidence"] = _normalize_visual_tags(
            normalized.get("civilian_disruption_evidence")
        )
        normalized["negative_evidence"] = _normalize_visual_tags(
            normalized.get("negative_evidence")
        )
        if "uncertainty_factors" not in normalized:
            normalized["uncertainty_factors"] = _uncertainty_factors(
                current=current,
                baseline=baseline,
            )
        normalized["confidence"] = _normalize_confidence(
            normalized.get("confidence", _evidence_confidence(evidence))
        )
        normalized["severity_hint"] = _normalize_severity_hint_value(
            normalized.get("severity_hint"),
            action=str(normalized.get("recommended_action") or ""),
            confidence=normalized["confidence"],
        )
        try:
            return LiquidAnalystReport.model_validate(normalized)
        except ValidationError:
            continue
    return None


def _build_payload(
    *,
    asset: Asset,
    current: FrameEnvelope,
    baseline: FrameEnvelope,
    evidence: Sam3EvidenceReport | None,
    model_version: str,
) -> CandidateRequestPayload:
    system = (
        "You are a civilian satellite before/after analyst. Compare the baseline image and "
        "current image. The source report is context, not something to validate from imagery. "
        "Report only visible macro-scale civilian infrastructure impact and imagery limits. "
        "Do not mention tactical targets, troops, weapons, bases, convoys, or strike support. "
        "Do not repeat the input. Return one compact JSON object only, with no markdown."
    )
    user = _analyst_user_prompt(asset=asset, current=current, baseline=baseline, evidence=evidence)
    inputs: list[CandidateTextInput | CandidateImageInput] = [
        CandidateTextInput(type="input_text", role="system", text=system),
        CandidateTextInput(type="input_text", role="user", text=user),
    ]
    if baseline.frame.image_ref:
        inputs.append(
            CandidateImageInput(
                type="input_image",
                role="baseline",
                image_ref=baseline.frame.image_ref,
            )
        )
    if current.frame.image_ref:
        inputs.append(
            CandidateImageInput(
                type="input_image",
                role="current",
                image_ref=current.frame.image_ref,
            )
        )
    return CandidateRequestPayload(
        model_version=model_version,
        asset_id=asset.asset_id,
        scenario_id=f"analyst_{current.frame.frame_id}",
        inputs=inputs,
    )


def _analyst_user_prompt(
    *,
    asset: Asset,
    current: FrameEnvelope,
    baseline: FrameEnvelope,
    evidence: Sam3EvidenceReport | None,
) -> str:
    allowed_tags = ", ".join(get_args(VisualEvidenceTag))
    evidence_hint = (
        f"SAM3 hint: {evidence.summary}; tags={evidence.visual_evidence_tags}"
        if evidence
        else "SAM3 hint: none. Use only the two images and visibility metadata."
    )
    source_context = evidence.source_context if evidence else None
    source_hint = (
        "\n".join(
            [
                f"Source event: {source_context.title}",
                f"Source summary: {source_context.summary or 'not provided'}",
                f"Satellite relevance: {source_context.satellite_relevance}",
                f"Dynamic SAM3 prompts: {source_context.target_prompts}",
                f"Ignore from imagery: {source_context.ignore_terms}",
                f"Source-to-visual rationale: {source_context.rationale}",
            ]
        )
        if source_context is not None
        else "Source event: none; analyze only the selected civilian site."
    )
    return "\n".join(
        [
            "Compare the two images in this order: baseline first, current second.",
            f"Site: {asset.asset_name}",
            f"Region: {asset.region}",
            f"Civilian infrastructure type: {asset.asset_type}",
            source_hint,
            f"Baseline timestamp: {baseline.frame.captured_at}; cloud={baseline.frame.cloud_cover}",
            f"Current timestamp: {current.frame.captured_at}; cloud={current.frame.cloud_cover}",
            evidence_hint,
            "Allowed evidence tags:",
            allowed_tags,
            "Return exactly this JSON shape:",
            "{",
            '  "visible_change_summary": "one short sentence",',
            '  "civilian_disruption_evidence": ["one or more allowed tags, or empty list"],',
            '  "negative_evidence": ["allowed tags such as no_visible_change or low_visibility"],',
            '  "uncertainty_factors": ["short non-tactical uncertainty flags"],',
            '  "severity_hint": "none | low | moderate | severe",',
            '  "recommended_action": "discard | defer | downlink_now",',
            '  "confidence": 0.0,',
            '  "short_rationale": "one short sentence"',
            "}",
            "If cloud, blur, SAR artifacts, or low resolution prevent a defensible read, use "
            "recommended_action=discard, severity_hint=none, confidence below 0.3, and include "
            "low_visibility in negative_evidence.",
            "Do not say the source report is proven by imagery unless visible before/after change "
            "is clear. Use the source context to decide what visual objects to inspect.",
        ]
    )


def _unavailable_report(
    *,
    asset: Asset,
    current: FrameEnvelope,
    baseline: FrameEnvelope,
    evidence: Sam3EvidenceReport | None,
    model_version: str,
    backend: LiquidAnalystBackendMode,
    reason: str,
) -> LiquidAnalystReport:
    return LiquidAnalystReport(
        asset_id=asset.asset_id,
        current_frame_id=current.frame.frame_id,
        baseline_frame_id=baseline.frame.frame_id,
        current_image_ref=current.frame.image_ref,
        baseline_image_ref=baseline.frame.image_ref,
        model_version=model_version,
        backend=backend,
        status="unavailable",
        visible_change_summary=reason,
        civilian_disruption_evidence=list(evidence.visual_evidence_tags if evidence else []),
        negative_evidence=[],
        uncertainty_factors=_uncertainty_factors(current=current, baseline=baseline),
        severity_hint="none",
        recommended_action="discard",
        confidence=0.0,
        short_rationale="Analyst output was unavailable or failed safety/schema validation.",
    )


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
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and first < last:
        excerpt = text[first : last + 1]
        if excerpt not in blobs:
            blobs.append(excerpt)
    return blobs


def _normalize_visual_tags(value: object) -> list[str]:
    if value is None:
        return []
    raw_items = value if isinstance(value, list) else [value]
    allowed = set(get_args(VisualEvidenceTag))
    normalized: list[str] = []
    for item in raw_items:
        if not isinstance(item, str):
            continue
        tag = _VISUAL_TAG_ALIASES.get(item.strip().lower().replace(" ", "_"), item.strip())
        if tag in allowed and tag not in normalized:
            normalized.append(tag)
    return normalized


def _normalize_confidence(value: object) -> float:
    if isinstance(value, str):
        value = value.strip().rstrip("%")
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    if confidence > 1.0:
        confidence /= 100.0
    return max(min(confidence, 1.0), 0.0)


def _normalize_severity_hint_value(
    value: object,
    *,
    action: str,
    confidence: float,
) -> str:
    if not isinstance(value, str) or "|" not in value:
        return str(value or _severity_hint(action=action, confidence=confidence))
    return _severity_hint(action=action, confidence=confidence)


_VISUAL_TAG_ALIASES = {
    "none": "no_visible_change",
    "no_change": "no_visible_change",
    "no_visible_damage": "no_visible_change",
    "low_resolution": "low_visibility",
    "cloud": "low_visibility",
    "clouds": "low_visibility",
    "cloud_cover": "low_visibility",
    "rubble": "debris_field",
    "debris": "debris_field",
    "crater": "blast_or_crater_scarring",
    "craters": "blast_or_crater_scarring",
    "burned_area": "burn_scar",
    "fire_damage": "burn_scar",
    "collapsed_structure": "collapsed_building",
    "destroyed_building": "collapsed_building",
    "damaged_building": "collapsed_building",
    "damaged_road": "damaged_bridge_or_access_span",
    "road_damage": "damaged_bridge_or_access_span",
    "urban_damage": "broad_urban_destruction",
}


def _severity_hint(*, action: str, confidence: float) -> str:
    if action == "downlink_now" and confidence >= 0.75:
        return "severe"
    if action in {"downlink_now", "defer"}:
        return "moderate"
    if confidence >= 0.35:
        return "low"
    return "none"


def _evidence_confidence(evidence: Sam3EvidenceReport | None) -> float:
    if evidence is None or not evidence.masks:
        return 0.0
    return max(mask.temporal_change_score or mask.score for mask in evidence.masks)


def _uncertainty_factors(*, current: FrameEnvelope, baseline: FrameEnvelope) -> list[str]:
    factors: list[str] = []
    current_cloud = current.frame.cloud_cover
    baseline_cloud = baseline.frame.cloud_cover
    if (
        current_cloud is not None
        and current_cloud >= 0.35
        or baseline_cloud is not None
        and baseline_cloud >= 0.35
    ):
        factors.append("cloud_or_visibility_limit")
    if current.frame.source != baseline.frame.source:
        factors.append("source_or_modality_mismatch")
    if current.accepted_for_alerting is False:
        factors.append("current_frame_filtered_below_alert_threshold")
    return factors
