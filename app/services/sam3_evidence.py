from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from app.schemas.alert import Alert
from app.schemas.asset import Asset
from app.schemas.evidence_candidate import VisualEvidenceTag
from app.schemas.frame import FrameEnvelope
from app.schemas.lead import Lead
from app.schemas.sam3_evidence import (
    Sam3EvidenceBackendMode,
    Sam3EvidenceMask,
    Sam3EvidenceReport,
    Sam3SourceContext,
)

MAX_EVIDENCE_MASK_AREA_RATIO = 0.45
MIN_DAMAGE_CHANGE_SCORE = 0.35
MIN_MISSING_STRUCTURE_SCORE = 0.4
SAME_OBJECT_IOU_THRESHOLD = 0.25


class Sam3EvidenceBackend:
    backend_id = "fixture"

    def analyze(
        self,
        *,
        asset: Asset,
        current: FrameEnvelope,
        baseline: FrameEnvelope,
        alert: Alert | None,
        prompts: list[str],
        source_context: Sam3SourceContext | None,
        model_version: str,
    ) -> Sam3EvidenceReport:
        raise NotImplementedError


class FixtureSam3EvidenceBackend(Sam3EvidenceBackend):
    backend_id = "fixture"

    def analyze(
        self,
        *,
        asset: Asset,
        current: FrameEnvelope,
        baseline: FrameEnvelope,
        alert: Alert | None,
        prompts: list[str],
        source_context: Sam3SourceContext | None,
        model_version: str,
    ) -> Sam3EvidenceReport:
        if alert is None or alert.action == "discard":
            return Sam3EvidenceReport(
                asset_id=asset.asset_id,
                current_frame_id=current.frame.frame_id,
                baseline_frame_id=baseline.frame.frame_id,
                current_image_ref=current.frame.image_ref,
                baseline_image_ref=baseline.frame.image_ref,
                overlay_ref=current.overlay_ref,
                model_version=model_version,
                backend="fixture",
                decision="no_evidence",
                source_context=source_context,
                prompts=prompts,
                triage_action="discard",
                summary=("SAM3 evidence lane has no accepted disruption seed for this site yet."),
            )

        label, tag = _evidence_label_for_alert(alert)
        bbox = alert.bbox
        area_ratio = round(max((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]), 0.0), 3)
        return Sam3EvidenceReport(
            asset_id=asset.asset_id,
            current_frame_id=current.frame.frame_id,
            baseline_frame_id=baseline.frame.frame_id,
            current_image_ref=current.frame.image_ref,
            baseline_image_ref=baseline.frame.image_ref,
            overlay_ref=current.overlay_ref,
            model_version=model_version,
            backend="fixture",
            decision="segmentation_ready",
            source_context=source_context,
            prompts=prompts,
            masks=[
                Sam3EvidenceMask(
                    label=label,
                    prompt=prompts[0] if prompts else label,
                    score=alert.confidence,
                    bbox_norm=bbox,
                    area_ratio=area_ratio,
                )
            ],
            visual_evidence_tags=[tag],
            triage_action=alert.action,
            summary=(
                f"Fixture SAM3 lane seeded one {label} mask from the accepted "
                f"{alert.action} alert bbox."
            ),
        )


class HttpSam3EvidenceBackend(Sam3EvidenceBackend):
    backend_id = "sam3_http"

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def analyze(
        self,
        *,
        asset: Asset,
        current: FrameEnvelope,
        baseline: FrameEnvelope,
        alert: Alert | None,
        prompts: list[str],
        source_context: Sam3SourceContext | None,
        model_version: str,
    ) -> Sam3EvidenceReport:
        payload = {
            "asset": asset.model_dump(mode="json"),
            "current_frame": current.model_dump(mode="json"),
            "baseline_frame": baseline.model_dump(mode="json"),
            "alert": alert.model_dump(mode="json") if alert else None,
            "source_context": source_context.model_dump(mode="json") if source_context else None,
            "prompts": prompts,
            "model_version": model_version,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            return _unavailable_report(
                asset=asset,
                current=current,
                baseline=baseline,
                prompts=prompts,
                source_context=source_context,
                model_version=model_version,
                backend="sam3_http",
            )

        try:
            report = Sam3EvidenceReport.model_validate(json.loads(body))
        except (json.JSONDecodeError, ValidationError, TypeError):
            return _unavailable_report(
                asset=asset,
                current=current,
                baseline=baseline,
                prompts=prompts,
                source_context=source_context,
                model_version=model_version,
                backend="sam3_http",
            )
        report = _suppress_autonomous_sam3_report(report=report, alert=alert)
        return report.model_copy(update={"backend": "sam3_http", "model_version": model_version})


class Sam3EvidenceService:
    def __init__(
        self,
        *,
        model_version: str,
        backend: Sam3EvidenceBackend,
    ) -> None:
        self.model_version = model_version
        self.backend = backend

    def analyze(
        self,
        *,
        asset: Asset,
        current: FrameEnvelope,
        baseline: FrameEnvelope,
        alert: Alert | None,
        source_context: Sam3SourceContext | None = None,
    ) -> Sam3EvidenceReport:
        prompts = prompts_for_asset(asset, alert, source_context=source_context)
        return self.backend.analyze(
            asset=asset,
            current=current,
            baseline=baseline,
            alert=alert,
            prompts=prompts,
            source_context=source_context,
            model_version=self.model_version,
        )


def build_sam3_report_from_masks(
    *,
    asset: Asset,
    current: FrameEnvelope,
    baseline: FrameEnvelope,
    prompts: list[str],
    masks: list[Sam3EvidenceMask],
    model_version: str,
    backend: Sam3EvidenceBackendMode,
    source_context: Sam3SourceContext | None = None,
) -> Sam3EvidenceReport:
    masks = [mask for mask in masks if mask.area_ratio <= MAX_EVIDENCE_MASK_AREA_RATIO]
    tags = [
        tag
        for tag in (
            evidence_tag_for_prompt(mask.label) or evidence_tag_for_prompt(mask.prompt)
            for mask in masks
        )
        if tag is not None
    ]
    unique_tags = list(dict.fromkeys(tags))
    triage_action = _action_from_masks(masks)
    decision = "segmentation_ready" if masks else "no_evidence"
    summary = (
        f"SAM3 returned {len(masks)} candidate mask"
        f"{'' if len(masks) == 1 else 's'} for selected disruption prompts."
        if masks
        else "SAM3 returned no candidate disruption masks for selected prompts."
    )
    return Sam3EvidenceReport(
        asset_id=asset.asset_id,
        current_frame_id=current.frame.frame_id,
        baseline_frame_id=baseline.frame.frame_id,
        current_image_ref=current.frame.image_ref,
        baseline_image_ref=baseline.frame.image_ref,
        overlay_ref=current.overlay_ref,
        model_version=model_version,
        backend=backend,
        decision=decision,
        source_context=source_context,
        prompts=prompts,
        masks=masks,
        visual_evidence_tags=unique_tags,
        triage_action=triage_action,
        summary=summary,
    )


def prompts_for_asset(
    asset: Asset,
    alert: Alert | None,
    *,
    source_context: Sam3SourceContext | None = None,
) -> list[str]:
    common_damage = ["rubble pile", "debris field", "collapsed building", "burn scar", "crater"]
    by_asset = {
        "grain_port": ["warehouse", "container yard", "port crane", "pier"],
        "grain_storage_complex": ["warehouse", "grain silo", "storage tank"],
        "container_port": ["container yard", "shipping container", "port crane", "pier"],
        "bridge": ["bridge span", "bridge deck", "road bridge"],
        "road_access_corridor": ["road", "bridge span", "blocked vehicle"],
        "water_infrastructure": ["water tank", "reservoir", "treatment basin", "pump station"],
        "logistics_hub": ["warehouse", "loading dock", "truck yard"],
        "medical_aid_node": ["hospital building", "civilian building", "rubble pile"],
        "aid_warehouse_cluster": ["warehouse", "aid truck", "loading dock"],
        "aid_shelter_campus": ["shelter building", "civilian building", "tent camp"],
        "civilian_building_cluster": ["building", "apartment block", "rubble pile"],
    }
    source_prompts = list(source_context.target_prompts if source_context else [])
    context_prompts = _context_prompts_for_asset(
        asset=asset,
        alert=alert,
        source_context=source_context,
    )
    asset_prompts = by_asset.get(asset.asset_type, [])
    prompts = (
        source_prompts + context_prompts + asset_prompts + common_damage
        if _is_conflict_context(asset=asset, alert=alert, source_context=source_context)
        else asset_prompts + source_prompts + context_prompts + common_damage
    )
    if alert and alert.event_type == "probable_access_obstruction":
        prompts.insert(0, "blocked road")
    return list(dict.fromkeys(_short_visual_prompt(prompt) for prompt in prompts if prompt))[:8]


def source_context_for_lead(lead: Lead) -> Sam3SourceContext:
    text = _sam3_context_text(asset=None, alert=None, source_text=_lead_context_text(lead))
    target_prompts = _source_target_prompts(text)
    source_only = _contains_any(
        text,
        (
            "ambush",
            "arrest",
            "casualties",
            "clash",
            "fighter",
            "fighters",
            "injured",
            "killed",
            "militant",
            "peacekeeper",
            "soldier",
            "troop",
            "wounded",
        ),
    )
    relevance = "high" if target_prompts else ("low" if source_only else "medium")
    rationale = (
        "Source context mentions visible physical damage or infrastructure."
        if target_prompts
        else "Source context does not describe a clear satellite-visible damage target."
    )
    return Sam3SourceContext(
        title=lead.title,
        summary=lead.summary,
        region=lead.region,
        satellite_relevance=relevance,
        target_prompts=target_prompts,
        ignore_terms=[
            "casualties",
            "fatalities",
            "injuries",
            "soldiers",
            "fighters",
            "responsibility claims",
            "political claims",
        ],
        rationale=rationale,
    )


def _context_prompts_for_asset(
    *,
    asset: Asset,
    alert: Alert | None,
    source_context: Sam3SourceContext | None = None,
) -> list[str]:
    text = _sam3_context_text(asset=asset, alert=alert, source_context=source_context)
    prompts: list[str] = []
    if any(
        token in text
        for token in (
            "airstrike",
            "artillery",
            "blast",
            "bomb",
            "drone",
            "explosion",
            "missile",
            "rocket",
            "shell",
            "strike",
        )
    ):
        prompts.extend(["collapsed building", "rubble pile", "debris field", "crater", "burn scar"])
    if any(
        token in text
        for token in (
            "apartment",
            "civilian",
            "district",
            "hospital",
            "market",
            "residential",
            "school",
        )
    ):
        prompts.extend(["civilian building", "apartment block", "rubble pile"])
    if any(token in text for token in ("shop", "shops", "pharmacy", "commercial")):
        prompts.extend(["commercial building", "market building", "rubble pile"])
    if any(token in text for token in ("bridge", "checkpoint", "crossing", "road")):
        prompts.extend(["bridge span", "blocked road", "road bridge"])
    if any(token in text for token in ("grain", "logistics", "port", "warehouse")):
        prompts.extend(["warehouse", "container yard", "loading dock", "truck yard"])
    if any(token in text for token in ("power", "pump", "reservoir", "water")):
        prompts.extend(["water tank", "pump station", "reservoir"])
    if any(token in text for token in ("camp", "displaced", "refugee", "shelter", "tent")):
        prompts.extend(["tent camp", "shelter building", "aid truck"])
    if any(token in text for token in ("cartel", "riot", "unrest")):
        prompts.extend(["burn scar", "blocked road", "debris field", "civilian building"])
    return list(dict.fromkeys(prompts))


def _is_conflict_context(
    *,
    asset: Asset,
    alert: Alert | None,
    source_context: Sam3SourceContext | None = None,
) -> bool:
    text = _sam3_context_text(asset=asset, alert=alert, source_context=source_context)
    return any(
        token in text
        for token in (
            "airstrike",
            "artillery",
            "bomb",
            "conflict",
            "drone",
            "missile",
            "rocket",
            "shell",
            "strike",
            "war",
        )
    )


def _sam3_context_text(
    *,
    asset: Asset | None,
    alert: Alert | None,
    source_context: Sam3SourceContext | None = None,
    source_text: str | None = None,
) -> str:
    parts = []
    if asset is not None:
        parts.extend(
            [
                asset.asset_name,
                asset.asset_type.replace("_", " "),
                asset.region,
            ]
        )
    if alert is not None:
        parts.extend(
            [
                alert.asset_name,
                alert.event_type.replace("_", " "),
                alert.civilian_impact.replace("_", " "),
                alert.why,
            ]
        )
    if source_context is not None:
        parts.extend(
            [
                source_context.title,
                source_context.summary or "",
                source_context.region or "",
                source_context.rationale,
                " ".join(source_context.target_prompts),
            ]
        )
    if source_text:
        parts.append(source_text)
    return " ".join(parts).lower()


def _lead_context_text(lead: Lead) -> str:
    return " ".join(
        part
        for part in (
            lead.title,
            lead.summary or "",
            lead.region,
        )
        if part
    )


def _source_target_prompts(text: str) -> list[str]:
    prompts: list[str] = []
    attack_context = _contains_any(
        text,
        (
            "airstrike",
            "artillery",
            "blast",
            "bomb",
            "drone attack",
            "explosion",
            "missile",
            "rocket",
            "shell",
            "strike",
        ),
    )
    damage_context = not _contains_any(
        text,
        (
            "no damage",
            "no damage site",
            "no physical damage",
            "without damage",
            "without visible damage",
        ),
    ) and _contains_any(
        text,
        (
            "blast",
            "burned",
            "burning",
            "collapsed",
            "crater",
            "damage",
            "damaged",
            "damages",
            "destroyed",
            "explosion",
            "rubble",
            "smoke",
        ),
    )
    if attack_context or damage_context:
        prompts.extend(["rubble pile", "debris field", "crater", "burn scar"])
    if _contains_any(text, ("apartment", "residential", "neighborhood", "district")):
        prompts.extend(["apartment block", "civilian building"])
    if _contains_any(text, ("shop", "shops", "pharmacy", "market", "commercial")):
        prompts.extend(["commercial building", "market building"])
    if _contains_any(text, ("hospital", "clinic", "school")):
        prompts.extend(["hospital building", "school building"])
    if _contains_any(text, ("warehouse", "logistics", "port", "harbor", "dock")):
        prompts.extend(["warehouse", "container yard", "loading dock"])
    if _contains_any(text, ("bridge", "crossing", "road", "rail")):
        prompts.extend(["bridge span", "blocked road", "rail line"])
    if _contains_any(text, ("power", "substation", "electric", "refinery", "plant")):
        prompts.extend(["power plant", "substation", "industrial building"])
    if _contains_any(text, ("water", "reservoir", "pump", "treatment")):
        prompts.extend(["water tank", "reservoir", "pump station"])
    return list(dict.fromkeys(_short_visual_prompt(prompt) for prompt in prompts))


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    normalized = f" {_normalize_text(text)} "
    return any(f" {_normalize_text(token)} " in normalized for token in tokens)


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").replace("/", " ").split())


def _short_visual_prompt(prompt: str) -> str:
    words = _normalize_text(prompt).split()
    return " ".join(words[:3])


def evidence_tag_for_prompt(prompt: str) -> VisualEvidenceTag | None:
    normalized = prompt.lower().replace("_", " ")
    if (
        "bridge" in normalized
        or "access" in normalized
        or "road" in normalized
        or "blocked vehicle" in normalized
    ):
        return "damaged_bridge_or_access_span"
    if (
        "port" in normalized
        or "apron" in normalized
        or "container" in normalized
        or "pier" in normalized
        or "crane" in normalized
    ):
        return "damaged_port_or_logistics_apron"
    if (
        "warehouse" in normalized
        or "logistics" in normalized
        or "silo" in normalized
        or "storage tank" in normalized
        or "loading dock" in normalized
        or "truck yard" in normalized
    ):
        return "damaged_warehouse_block"
    if (
        "water" in normalized
        or "power" in normalized
        or "reservoir" in normalized
        or "treatment basin" in normalized
        or "pump station" in normalized
    ):
        return "damaged_water_or_power_facility"
    if (
        "market" in normalized
        or "civilian building" in normalized
        or "building cluster" in normalized
        or "shelter" in normalized
        or "hospital" in normalized
        or "apartment" in normalized
        or "tent camp" in normalized
    ):
        return "damaged_market_or_civilian_cluster"
    if "rubble" in normalized:
        return "large_rubble_field"
    if "urban destruction" in normalized:
        return "broad_urban_destruction"
    if "missing building" in normalized:
        return "missing_building_footprint"
    if "collapsed building" in normalized:
        return "collapsed_building"
    if "burn" in normalized:
        return "burn_scar"
    if "blast" in normalized or "crater" in normalized:
        return "blast_or_crater_scarring"
    if "debris" in normalized:
        return "debris_field"
    return None


def score_temporal_change_masks(
    *,
    current_masks: list[Sam3EvidenceMask],
    baseline_masks: list[Sam3EvidenceMask],
) -> list[Sam3EvidenceMask]:
    """Keep only SAM3 masks that look like new damage or missing structures.

    SAM3 segments concepts, not disruption. This converts prompt hits into
    evidence only when the current frame differs from the baseline frame.
    """

    filtered: list[Sam3EvidenceMask] = []
    compact_current = [
        mask
        for mask in current_masks
        if mask.area_ratio <= MAX_EVIDENCE_MASK_AREA_RATIO and mask.score >= 0.45
    ]
    compact_baseline = [
        mask
        for mask in baseline_masks
        if mask.area_ratio <= MAX_EVIDENCE_MASK_AREA_RATIO and mask.score >= 0.45
    ]

    for mask in compact_current:
        if not _is_damage_prompt(mask.prompt):
            continue
        peers = _same_prompt_masks(mask, compact_baseline)
        best_iou = _best_iou(mask, peers)
        change_score = round(mask.score * (1.0 - best_iou), 3)
        if best_iou < SAME_OBJECT_IOU_THRESHOLD and change_score >= MIN_DAMAGE_CHANGE_SCORE:
            filtered.append(
                mask.model_copy(
                    update={
                        "matched_baseline_iou": round(best_iou, 3),
                        "temporal_change_score": change_score,
                    }
                )
            )

    for baseline in compact_baseline:
        if _is_damage_prompt(baseline.prompt):
            continue
        peers = _same_prompt_masks(baseline, compact_current)
        best_iou = _best_iou(baseline, peers)
        best_current_area = max((peer.area_ratio for peer in peers), default=0.0)
        missing_ratio = (
            1.0 if not peers else max(1.0 - best_current_area / baseline.area_ratio, 0.0)
        )
        change_score = round(baseline.score * max(1.0 - best_iou, missing_ratio), 3)
        if best_iou < SAME_OBJECT_IOU_THRESHOLD and change_score >= MIN_MISSING_STRUCTURE_SCORE:
            filtered.append(
                baseline.model_copy(
                    update={
                        "label": f"missing {baseline.prompt}",
                        "frame_role": "baseline",
                        "matched_baseline_iou": round(best_iou, 3),
                        "temporal_change_score": change_score,
                    }
                )
            )

    return filtered


def _evidence_label_for_alert(alert: Alert) -> tuple[str, str]:
    if alert.event_type == "probable_access_obstruction":
        return "damaged bridge or access span", "damaged_bridge_or_access_span"
    if alert.asset_type in {"grain_port", "container_port"}:
        return "damaged port or logistics apron", "damaged_port_or_logistics_apron"
    if alert.asset_type in {"water_infrastructure"}:
        return "damaged water or power facility", "damaged_water_or_power_facility"
    if alert.asset_type in {"grain_storage_complex", "logistics_hub", "aid_warehouse_cluster"}:
        return "damaged warehouse block", "damaged_warehouse_block"
    if alert.asset_type in {
        "medical_aid_node",
        "aid_shelter_campus",
        "civilian_building_cluster",
    }:
        return "damaged market or civilian cluster", "damaged_market_or_civilian_cluster"
    return "debris field", "debris_field"


def _action_from_masks(masks: list[Sam3EvidenceMask]) -> str:
    if not masks:
        return "discard"
    best_score = max(mask.score for mask in masks)
    best_area = max(mask.area_ratio for mask in masks)
    if best_score >= 0.65 and best_area >= 0.01:
        return "downlink_now"
    if best_score >= 0.45 and best_area >= 0.005:
        return "defer"
    return "discard"


def _is_damage_prompt(prompt: str) -> bool:
    normalized = prompt.lower().replace("_", " ")
    return any(
        token in normalized
        for token in ("rubble", "debris", "collapsed", "burn", "crater", "blast")
    )


def _same_prompt_masks(
    mask: Sam3EvidenceMask,
    candidates: list[Sam3EvidenceMask],
) -> list[Sam3EvidenceMask]:
    return [
        candidate
        for candidate in candidates
        if candidate.prompt == mask.prompt or candidate.label == mask.label
    ]


def _best_iou(mask: Sam3EvidenceMask, candidates: list[Sam3EvidenceMask]) -> float:
    return max(
        (_bbox_iou(mask.bbox_norm, candidate.bbox_norm) for candidate in candidates),
        default=0.0,
    )


def _bbox_iou(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    x1 = max(first[0], second[0])
    y1 = max(first[1], second[1])
    x2 = min(first[2], second[2])
    y2 = min(first[3], second[3])
    intersection = max(x2 - x1, 0.0) * max(y2 - y1, 0.0)
    first_area = max(first[2] - first[0], 0.0) * max(first[3] - first[1], 0.0)
    second_area = max(second[2] - second[0], 0.0) * max(second[3] - second[1], 0.0)
    union = first_area + second_area - intersection
    return intersection / union if union else 0.0


def _suppress_autonomous_sam3_report(
    *,
    report: Sam3EvidenceReport,
    alert: Alert | None,
) -> Sam3EvidenceReport:
    if alert is not None and alert.action != "discard":
        return report
    if not report.masks and report.triage_action == "discard":
        return report
    return report.model_copy(
        update={
            "decision": "no_evidence",
            "masks": [],
            "visual_evidence_tags": [],
            "triage_action": "discard",
            "summary": (
                "SAM3 output suppressed because the upstream alert was absent or "
                "discarded; SAM3 is evidence support, not an autonomous alert gate."
            ),
        }
    )


def _unavailable_report(
    *,
    asset: Asset,
    current: FrameEnvelope,
    baseline: FrameEnvelope,
    prompts: list[str],
    source_context: Sam3SourceContext | None,
    model_version: str,
    backend: str,
) -> Sam3EvidenceReport:
    return Sam3EvidenceReport(
        asset_id=asset.asset_id,
        current_frame_id=current.frame.frame_id,
        baseline_frame_id=baseline.frame.frame_id,
        current_image_ref=current.frame.image_ref,
        baseline_image_ref=baseline.frame.image_ref,
        overlay_ref=current.overlay_ref,
        model_version=model_version,
        backend=backend,
        decision="unavailable",
        source_context=source_context,
        prompts=prompts,
        triage_action="discard",
        summary="SAM3 evidence backend unavailable; no segmentation-driven alert emitted.",
    )
