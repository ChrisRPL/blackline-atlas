from __future__ import annotations

import math
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path

from app.schemas.asset import Asset
from app.schemas.frame import FrameEnvelope
from app.schemas.lead import Lead
from app.schemas.satellite_evidence import (
    SatelliteEvidenceAttempt,
    SatelliteEvidenceBundle,
    SatelliteEvidenceScope,
    SatelliteEvidenceUsability,
)
from app.services.frame_client import FrameClient
from app.services.frame_types import FrameRequest

_LIVE_SHORT_WINDOW_SECONDS = 120 * 24 * 60 * 60
_LIVE_MEDIUM_WINDOW_SECONDS = 365 * 24 * 60 * 60
_LIVE_CONTEXT_WINDOW_SECONDS = 730 * 24 * 60 * 60
_LIVE_SEARCH_DEADLINE_SECONDS = 35.0
_LIVE_MAX_CANDIDATE_ATTEMPTS = 12
_MAX_MODEL_AOI_SIZE_KM = 8.0
_CLOUD_WARNING_THRESHOLD = 0.35


@dataclass(frozen=True)
class _EvidenceCandidate:
    scope: SatelliteEvidenceScope
    latitude: float
    longitude: float
    size_km: float
    window_seconds: float
    current_shift_days: int = 0
    baseline_shift_days: int = 0


@dataclass(frozen=True)
class _ReadyEvidence:
    candidate: _EvidenceCandidate
    current: FrameEnvelope
    baseline: FrameEnvelope
    offset_km: float
    quality_warnings: list[str]


def resolve_live_lead_satellite_evidence(
    *,
    asset: Asset,
    lead: Lead,
    frame_client: FrameClient,
    requested_timestamp: str,
    baseline_timestamp: str,
) -> SatelliteEvidenceBundle:
    started_at = time.monotonic()
    attempts: list[SatelliteEvidenceAttempt] = []
    best_ready: _ReadyEvidence | None = None

    for candidate_index, candidate in enumerate(
        _evidence_candidates(lead.latitude, lead.longitude)
    ):
        if (
            candidate_index >= _LIVE_MAX_CANDIDATE_ATTEMPTS
            or time.monotonic() - started_at > _LIVE_SEARCH_DEADLINE_SECONDS
        ):
            break

        current_timestamp = _shift_timestamp(
            requested_timestamp,
            days=-candidate.current_shift_days,
        )
        candidate_baseline_timestamp = _shift_timestamp(
            baseline_timestamp,
            days=-candidate.baseline_shift_days,
        )
        request = FrameRequest(
            asset_id=asset.asset_id,
            scenario_id=f"live_{lead.lead_id}",
            latitude=candidate.latitude,
            longitude=candidate.longitude,
            requested_timestamp=current_timestamp,
            baseline_timestamp=candidate_baseline_timestamp,
            size_km=candidate.size_km,
            window_seconds=candidate.window_seconds,
        )
        current, current_status = _resolve_coordinate_current_frame(
            frame_client=frame_client,
            request=request,
        )
        if current is not None:
            low_info_status = _low_visual_information_status(current)
            if low_info_status is not None:
                current = None
                current_status = low_info_status
        if current is None:
            baseline, baseline_status = None, "skipped because current missing"
        else:
            baseline, baseline_status = _resolve_baseline_frame(
                frame_client=frame_client,
                request=request,
            )
            if baseline is not None:
                low_info_status = _low_visual_information_status(baseline)
                if low_info_status is not None:
                    baseline = None
                    baseline_status = low_info_status
        attempts.append(
            SatelliteEvidenceAttempt(
                scope=candidate.scope,
                latitude=candidate.latitude,
                longitude=candidate.longitude,
                size_km=candidate.size_km,
                window_seconds=candidate.window_seconds,
                current_status=current_status,
                baseline_status=baseline_status,
                current_cloud_cover=_cloud_cover(current),
                baseline_cloud_cover=_cloud_cover(baseline),
                reason=_attempt_reason(current=current, baseline=baseline),
            )
        )
        if current is None or baseline is None:
            continue

        offset = _distance_km(
            lead.latitude,
            lead.longitude,
            candidate.latitude,
            candidate.longitude,
        )
        ready = _ReadyEvidence(
            candidate=candidate,
            current=current,
            baseline=baseline,
            offset_km=offset,
            quality_warnings=_quality_warnings(
                current=current,
                baseline=baseline,
                scope=candidate.scope,
                offset_km=offset,
                size_km=candidate.size_km,
            ),
        )
        best_ready = _better_ready_evidence(best_ready, ready)
        if _ready_evidence_is_clear(ready):
            return _ready_bundle(
                asset=asset,
                lead=lead,
                ready=ready,
                frame_client=frame_client,
                attempts=attempts,
                requested_timestamp=requested_timestamp,
                baseline_timestamp=baseline_timestamp,
            )

    if best_ready is not None:
        return _ready_bundle(
            asset=asset,
            lead=lead,
            ready=best_ready,
            frame_client=frame_client,
            attempts=attempts,
            requested_timestamp=requested_timestamp,
            baseline_timestamp=baseline_timestamp,
        )

    return SatelliteEvidenceBundle(
        asset_id=asset.asset_id,
        lead_id=lead.lead_id,
        status="unavailable",
        scope="satellite_context_only",
        usable_for_evidence=False,
        usability="unavailable",
        quality_score=0.0,
        quality_summary="No dated SimSat/Sentinel pair resolved for this lead.",
        reason="No SimSat/Sentinel image was available after exact, nearby, and regional attempts.",
        target_latitude=lead.latitude,
        target_longitude=lead.longitude,
        resolved_latitude=lead.latitude,
        resolved_longitude=lead.longitude,
        offset_km=0.0,
        size_km=25.0,
        requested_timestamp=requested_timestamp,
        baseline_timestamp=baseline_timestamp,
        attempts=attempts,
        quality_warnings=["no_dated_pair_resolved"],
    )


def _ready_bundle(
    *,
    asset: Asset,
    lead: Lead,
    ready: _ReadyEvidence,
    frame_client: FrameClient,
    attempts: list[SatelliteEvidenceAttempt],
    requested_timestamp: str,
    baseline_timestamp: str,
) -> SatelliteEvidenceBundle:
    candidate = ready.candidate
    usability = _ready_usability(ready)
    usable_for_evidence = usability == "direct_clear"
    reason = _ready_reason(candidate.scope, ready.offset_km)
    if _has_cloud_warning(ready.quality_warnings):
        reason = f"{reason} Best available pair selected after cloud-aware search."

    contact_sheet_ref = _contact_sheet_for_exact_coordinate(
        asset=asset,
        lead=lead,
        frame_client=frame_client,
        requested_timestamp=requested_timestamp,
        baseline_timestamp=baseline_timestamp,
    )
    return SatelliteEvidenceBundle(
        asset_id=asset.asset_id,
        lead_id=lead.lead_id,
        status="ready",
        scope=candidate.scope,
        usable_for_evidence=usable_for_evidence,
        usability=usability,
        quality_score=_ready_quality_score(ready),
        quality_summary=_ready_quality_summary(usability),
        reason=reason,
        target_latitude=lead.latitude,
        target_longitude=lead.longitude,
        resolved_latitude=candidate.latitude,
        resolved_longitude=candidate.longitude,
        offset_km=round(ready.offset_km, 2),
        size_km=candidate.size_km,
        requested_timestamp=requested_timestamp,
        baseline_timestamp=baseline_timestamp,
        current_frame=ready.current,
        baseline_frame=ready.baseline,
        contact_sheet_image_ref=contact_sheet_ref,
        contact_sheet_summary=(
            "Exact-coordinate Sentinel orientation sheet: 3 km, 5 km, and 8 km rows; "
            "baseline/current columns. Context only, not primary evidence."
            if contact_sheet_ref
            else None
        ),
        attempts=attempts,
        quality_warnings=ready.quality_warnings,
    )


def _contact_sheet_for_exact_coordinate(
    *,
    asset: Asset,
    lead: Lead,
    frame_client: FrameClient,
    requested_timestamp: str,
    baseline_timestamp: str,
) -> str | None:
    pairs: list[tuple[float, FrameEnvelope, FrameEnvelope]] = []
    for size_km in (3.0, 5.0, 8.0):
        request = FrameRequest(
            asset_id=asset.asset_id,
            scenario_id=f"live_{lead.lead_id}_contact_{size_km:g}km",
            latitude=lead.latitude,
            longitude=lead.longitude,
            requested_timestamp=requested_timestamp,
            baseline_timestamp=baseline_timestamp,
            size_km=size_km,
            window_seconds=_LIVE_MEDIUM_WINDOW_SECONDS,
        )
        current, _ = _resolve_coordinate_current_frame(
            frame_client=frame_client,
            request=request,
        )
        if current is not None and _low_visual_information_status(current) is not None:
            current = None
        if current is None:
            continue
        baseline, _ = _resolve_baseline_frame(frame_client=frame_client, request=request)
        if baseline is not None and _low_visual_information_status(baseline) is not None:
            baseline = None
        if baseline is None:
            continue
        pairs.append((size_km, baseline, current))
    if not pairs:
        return None
    return _render_contact_sheet(asset_id=asset.asset_id, lead_id=lead.lead_id, pairs=pairs[:3])


def _render_contact_sheet(
    *,
    asset_id: str,
    lead_id: str,
    pairs: list[tuple[float, FrameEnvelope, FrameEnvelope]],
) -> str | None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    cell_width = 288
    cell_height = 288
    header_height = 30
    label_width = 58
    output_dir = Path("var/contact_sheets") / asset_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{lead_id}_exact_coordinate_contact.png"

    rows: list[tuple[float, Image.Image, Image.Image]] = []
    for size_km, baseline, current in pairs:
        baseline_image = _open_contact_sheet_image(
            baseline.frame.image_ref,
            cell_width,
            cell_height,
        )
        current_image = _open_contact_sheet_image(current.frame.image_ref, cell_width, cell_height)
        if baseline_image is None or current_image is None:
            continue
        rows.append((size_km, baseline_image, current_image))
    if not rows:
        return None

    sheet = Image.new(
        "RGB",
        (label_width + cell_width * 2, header_height + cell_height * len(rows)),
        (18, 22, 24),
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((label_width + 8, 9), "baseline", fill=(230, 236, 232), font=font)
    draw.text((label_width + cell_width + 8, 9), "current", fill=(230, 236, 232), font=font)
    for row_index, (size_km, baseline_image, current_image) in enumerate(rows):
        top = header_height + row_index * cell_height
        draw.text((8, top + 10), f"{size_km:g} km", fill=(230, 236, 232), font=font)
        sheet.paste(baseline_image, (label_width, top))
        sheet.paste(current_image, (label_width + cell_width, top))
    try:
        sheet.save(output_path)
    except OSError:
        return None
    return str(output_path)


def _open_contact_sheet_image(
    image_ref: str | None,
    width: int,
    height: int,
):
    if not image_ref or image_ref.startswith(("http://", "https://", "data:")):
        return None
    path = Path(image_ref)
    if not path.exists() or not path.is_file():
        return None
    try:
        from PIL import Image, ImageOps

        with Image.open(path) as image:
            return ImageOps.fit(image.convert("RGB"), (width, height))
    except (OSError, ValueError):
        return None


def _ready_usability(ready: _ReadyEvidence) -> SatelliteEvidenceUsability:
    if ready.candidate.scope not in {"exact_aoi", "nearby_aoi"}:
        return "context_only"
    if ready.candidate.size_km > _MAX_MODEL_AOI_SIZE_KM:
        return "context_only"
    if _has_cloud_warning(ready.quality_warnings):
        return "cloud_limited"
    return "direct_clear"


def _ready_quality_score(ready: _ReadyEvidence) -> float:
    current_cloud = _normalized_cloud_cover(ready.current.frame.cloud_cover)
    baseline_cloud = _normalized_cloud_cover(ready.baseline.frame.cloud_cover)
    max_cloud = max(_cloud_penalty(current_cloud), _cloud_penalty(baseline_cloud))
    scope_penalty = {
        "exact_aoi": 0.0,
        "nearby_aoi": 0.08,
        "regional_aoi": 0.35,
        "satellite_context_only": 0.65,
    }[ready.candidate.scope]
    return round(max(min(1.0 - max_cloud - scope_penalty, 1.0), 0.0), 3)


def _ready_quality_summary(usability: SatelliteEvidenceUsability) -> str:
    if usability == "direct_clear":
        return "Dated Sentinel before/after pair is clear enough for a source-led visual brief."
    if usability == "cloud_limited":
        return (
            "Clouds or low detail limit the read. Atlas can describe visible context, but will "
            "not claim visual confirmation from these frames."
        )
    if usability == "context_only":
        return "Satellite imagery is regional/contextual and not direct model evidence."
    return "No usable dated satellite evidence resolved."


def _better_ready_evidence(
    current_best: _ReadyEvidence | None,
    candidate: _ReadyEvidence,
) -> _ReadyEvidence:
    if current_best is None:
        return candidate
    if _ready_evidence_score(candidate) < _ready_evidence_score(current_best):
        return candidate
    return current_best


def _ready_evidence_score(ready: _ReadyEvidence) -> tuple[float, float, float, float]:
    current_cloud = _normalized_cloud_cover(ready.current.frame.cloud_cover)
    baseline_cloud = _normalized_cloud_cover(ready.baseline.frame.cloud_cover)
    cloud_penalty = _cloud_penalty(current_cloud) + _cloud_penalty(baseline_cloud)
    cloud_penalty += _high_cloud_penalty(current_cloud)
    cloud_penalty += _high_cloud_penalty(baseline_cloud)

    scope_penalty = {
        "exact_aoi": 0.0,
        "nearby_aoi": 0.25,
        "regional_aoi": 1.5,
        "satellite_context_only": 3.0,
    }[ready.candidate.scope]

    return (
        cloud_penalty + scope_penalty,
        ready.offset_km / 20.0,
        _size_context_penalty(ready.candidate.size_km),
        ready.candidate.window_seconds,
    )


def _size_context_penalty(size_km: float) -> float:
    if size_km < 5.0:
        return (5.0 - size_km) / 20.0
    return (size_km - 5.0) / 100.0


def _ready_evidence_is_clear(ready: _ReadyEvidence) -> bool:
    current_cloud = _normalized_cloud_cover(ready.current.frame.cloud_cover)
    baseline_cloud = _normalized_cloud_cover(ready.baseline.frame.cloud_cover)
    if current_cloud is None or baseline_cloud is None:
        return False
    return (
        current_cloud < _CLOUD_WARNING_THRESHOLD
        and baseline_cloud < _CLOUD_WARNING_THRESHOLD
        and ready.candidate.scope in {"exact_aoi", "nearby_aoi"}
    )


def _cloud_penalty(cloud_cover: float | None) -> float:
    if cloud_cover is None:
        return _CLOUD_WARNING_THRESHOLD
    return cloud_cover


def _high_cloud_penalty(cloud_cover: float | None) -> float:
    if cloud_cover is not None and cloud_cover >= _CLOUD_WARNING_THRESHOLD:
        return 1.0
    return 0.0


def _has_cloud_warning(warnings: list[str]) -> bool:
    return any(warning.startswith(("current_cloud_", "baseline_cloud_")) for warning in warnings)


def _resolve_coordinate_current_frame(
    *,
    frame_client: FrameClient,
    request: FrameRequest,
) -> tuple[FrameEnvelope | None, str]:
    if request.requested_timestamp is None:
        return None, "missing requested timestamp"

    # SimSat's /data/current/image/sentinel follows the simulator satellite
    # position. For a clicked live marker we need coordinate/time lookup.
    coordinate_request = replace(request, baseline_timestamp=request.requested_timestamp)
    try:
        frame = frame_client.get_baseline_frame(coordinate_request)
    except (KeyError, ValueError):
        return None, "missing image"
    return frame.model_copy(update={"filter_reason": "simsat_historical_current_frame"}), "ready"


def _resolve_baseline_frame(
    *,
    frame_client: FrameClient,
    request: FrameRequest,
) -> tuple[FrameEnvelope | None, str]:
    try:
        return frame_client.get_baseline_frame(request), "ready"
    except (KeyError, ValueError):
        return None, "missing image"


def _low_visual_information_status(frame: FrameEnvelope) -> str | None:
    image_ref = frame.frame.image_ref
    if not image_ref or image_ref.startswith(("http://", "https://", "data:")):
        return None
    image_path = Path(image_ref)
    if not image_path.exists():
        return None
    try:
        from PIL import Image

        with Image.open(image_path) as image:
            sample = image.convert("RGB").resize((64, 64))
            pixels = sample.tobytes()
    except (OSError, ValueError):
        return None
    if not pixels:
        return "blank/no-data satellite tile"
    no_data = 0
    total_pixels = len(pixels) // 3
    for index in range(0, len(pixels), 3):
        red, green, blue = pixels[index], pixels[index + 1], pixels[index + 2]
        near_black = red <= 3 and green <= 3 and blue <= 3
        near_white = red >= 252 and green >= 252 and blue >= 252
        if near_black or near_white:
            no_data += 1
    if no_data / total_pixels >= 0.92:
        return "blank/no-data satellite tile"
    return None


def _attempt_reason(*, current: FrameEnvelope | None, baseline: FrameEnvelope | None) -> str:
    if current is not None and baseline is not None:
        return "current and baseline resolved"
    if current is None and baseline is None:
        return "current and baseline missing"
    if current is None:
        return "current missing"
    return "baseline missing"


def _cloud_cover(frame: FrameEnvelope | None) -> float | None:
    if frame is None:
        return None
    return _normalized_cloud_cover(frame.frame.cloud_cover)


def _quality_warnings(
    *,
    current: FrameEnvelope,
    baseline: FrameEnvelope,
    scope: SatelliteEvidenceScope,
    offset_km: float,
    size_km: float,
) -> list[str]:
    warnings: list[str] = []
    current_cloud = _normalized_cloud_cover(current.frame.cloud_cover)
    baseline_cloud = _normalized_cloud_cover(baseline.frame.cloud_cover)
    if current_cloud is not None and current_cloud >= _CLOUD_WARNING_THRESHOLD:
        warnings.append(f"current_cloud_{round(current_cloud * 100)}pct")
    if baseline_cloud is not None and baseline_cloud >= _CLOUD_WARNING_THRESHOLD:
        warnings.append(f"baseline_cloud_{round(baseline_cloud * 100)}pct")
    if scope == "nearby_aoi":
        warnings.append(f"nearby_offset_{offset_km:.1f}km")
    if size_km > _MAX_MODEL_AOI_SIZE_KM:
        warnings.append("aoi_too_wide_for_model_read")
    if scope == "regional_aoi":
        warnings.append("regional_context_not_direct_evidence")
    if _source_family(current.frame.source) != _source_family(baseline.frame.source):
        warnings.append("source_or_modality_mismatch")
    return warnings


def _source_family(source: str) -> str:
    return source.split("?", 1)[0]


def _normalized_cloud_cover(value: float | None) -> float | None:
    if value is None:
        return None
    if value > 1.0:
        return max(min(value / 100.0, 1.0), 0.0)
    return max(min(value, 1.0), 0.0)


def _evidence_candidates(latitude: float, longitude: float) -> list[_EvidenceCandidate]:
    candidates = [
        _EvidenceCandidate(
            scope="exact_aoi",
            latitude=latitude,
            longitude=longitude,
            size_km=5.0,
            window_seconds=14 * 24 * 60 * 60,
            current_shift_days=0,
            baseline_shift_days=0,
        ),
        _EvidenceCandidate(
            scope="exact_aoi",
            latitude=latitude,
            longitude=longitude,
            size_km=5.0,
            window_seconds=14 * 24 * 60 * 60,
            current_shift_days=0,
            baseline_shift_days=14,
        ),
        _EvidenceCandidate(
            scope="exact_aoi",
            latitude=latitude,
            longitude=longitude,
            size_km=5.0,
            window_seconds=14 * 24 * 60 * 60,
            current_shift_days=0,
            baseline_shift_days=28,
        ),
        _EvidenceCandidate(
            scope="exact_aoi",
            latitude=latitude,
            longitude=longitude,
            size_km=5.0,
            window_seconds=14 * 24 * 60 * 60,
            current_shift_days=14,
            baseline_shift_days=0,
        ),
        _EvidenceCandidate(
            scope="exact_aoi",
            latitude=latitude,
            longitude=longitude,
            size_km=5.0,
            window_seconds=14 * 24 * 60 * 60,
            current_shift_days=28,
            baseline_shift_days=0,
        ),
        _EvidenceCandidate(
            scope="exact_aoi",
            latitude=latitude,
            longitude=longitude,
            size_km=5.0,
            window_seconds=14 * 24 * 60 * 60,
            current_shift_days=14,
            baseline_shift_days=14,
        ),
        _EvidenceCandidate(
            scope="exact_aoi",
            latitude=latitude,
            longitude=longitude,
            size_km=8.0,
            window_seconds=_LIVE_MEDIUM_WINDOW_SECONDS,
        ),
        _EvidenceCandidate(
            scope="exact_aoi",
            latitude=latitude,
            longitude=longitude,
            size_km=3.0,
            window_seconds=_LIVE_MEDIUM_WINDOW_SECONDS,
        ),
    ]

    # SimSat/Sentinel availability can be sparse at exact event coordinates.
    # Keep nearby searches close enough for evidence review before context fallback.
    for north_km, east_km in ((-5.0, 0.0), (5.0, 0.0), (0.0, -5.0), (0.0, 5.0)):
        candidates.append(
            _km_offset_candidate(
                latitude,
                longitude,
                north_km,
                east_km,
                size_km=5.0,
                window_seconds=_LIVE_MEDIUM_WINDOW_SECONDS,
            )
        )

    for north_km, east_km in ((-9.0, 0.0), (9.0, 0.0), (0.0, -9.0), (0.0, 9.0)):
        candidates.append(
            _km_offset_candidate(
                latitude,
                longitude,
                north_km,
                east_km,
                size_km=10.0,
                window_seconds=_LIVE_CONTEXT_WINDOW_SECONDS,
            )
        )

    candidates.append(
        _EvidenceCandidate(
            scope="regional_aoi",
            latitude=latitude,
            longitude=longitude,
            size_km=18.0,
            window_seconds=_LIVE_CONTEXT_WINDOW_SECONDS,
        )
    )
    return candidates


def _shift_timestamp(timestamp: str, *, days: int) -> str:
    if days == 0:
        return timestamp
    normalized = timestamp.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        shifted = datetime.fromisoformat(normalized) + timedelta(days=days)
    except ValueError:
        return timestamp
    return shifted.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _km_offset_candidate(
    latitude: float,
    longitude: float,
    north_km: float,
    east_km: float,
    *,
    size_km: float,
    window_seconds: float,
) -> _EvidenceCandidate:
    latitude_delta = north_km / 111.0
    longitude_scale = max(math.cos(math.radians(latitude)), 0.1)
    longitude_delta = east_km / (111.0 * longitude_scale)
    return _EvidenceCandidate(
        scope="nearby_aoi",
        latitude=max(min(latitude + latitude_delta, 89.9), -89.9),
        longitude=_normalize_longitude(longitude + longitude_delta),
        size_km=size_km,
        window_seconds=window_seconds,
    )


def _normalize_longitude(longitude: float) -> float:
    while longitude > 180:
        longitude -= 360
    while longitude < -180:
        longitude += 360
    return longitude


def _distance_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    radius_km = 6371.0
    phi_a = math.radians(lat_a)
    phi_b = math.radians(lat_b)
    delta_phi = math.radians(lat_b - lat_a)
    delta_lambda = math.radians(lon_b - lon_a)
    haversine = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi_a) * math.cos(phi_b) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(haversine))


def _ready_reason(scope: SatelliteEvidenceScope, offset_km: float) -> str:
    if scope == "exact_aoi":
        return "Exact SimSat/Sentinel imagery resolved for the selected lead coordinate."
    if scope == "nearby_aoi":
        return (
            "Nearby SimSat/Sentinel imagery resolved "
            f"{offset_km:.1f} km from the source coordinate."
        )
    if scope == "regional_aoi":
        return "Regional SimSat/Sentinel context resolved around the source coordinate."
    return "Satellite context resolved, but not enough for direct disruption evidence."
