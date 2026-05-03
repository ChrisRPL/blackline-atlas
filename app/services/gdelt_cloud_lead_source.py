from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.schemas.asset import AssetType
from app.schemas.lead import Lead

GDELT_CLOUD_EVENTS_URL = "https://gdeltcloud.com/api/v2/events"
DEFAULT_GDELT_CLOUD_COUNTRIES: tuple[str, ...] = ()
_USER_AGENT = "BlacklineAtlasGdeltCloudLeadIngest/0.1"


@dataclass(frozen=True)
class GdeltCloudLeadFetchResult:
    leads: list[Lead]
    fetched_event_count: int


@dataclass(frozen=True)
class _GdeltCloudEvent:
    event_id: str
    title: str
    summary: str | None
    event_date: date
    category: str | None
    subcategory: str | None
    country: str | None
    region: str | None
    admin1: str | None
    location: str | None
    latitude: float
    longitude: float
    source_url: str | None
    article_count: int
    confidence: float | None
    significance: float | None
    fatalities: int


def fetch_gdelt_cloud_conflict_leads(
    *,
    api_key: str | None,
    api_url: str = GDELT_CLOUD_EVENTS_URL,
    days: int = 30,
    limit: int = 500,
    countries: tuple[str, ...] = DEFAULT_GDELT_CLOUD_COUNTRIES,
    confidence_profile: str = "loose",
    timeout_seconds: float = 8.0,
    opener=urlopen,
) -> GdeltCloudLeadFetchResult:
    if not api_key:
        return GdeltCloudLeadFetchResult(leads=[], fetched_event_count=0)

    events: list[_GdeltCloudEvent] = []
    country_list = countries or ("",)
    sort_modes = ("significance", "recent")
    per_request_limit = max(10, min(limit, 100))
    for country in country_list:
        for sort in sort_modes:
            cursor: str | None = None
            pages_read = 0
            while len(_dedupe_events(events)) < limit and pages_read < 10:
                payload = _read_events(
                    api_key=api_key,
                    api_url=api_url,
                    days=days,
                    limit=per_request_limit,
                    country=country or None,
                    confidence_profile=confidence_profile,
                    sort=sort,
                    cursor=cursor,
                    timeout_seconds=timeout_seconds,
                    opener=opener,
                )
                if payload is None:
                    break
                rows = payload.get("data") if isinstance(payload, dict) else None
                if not isinstance(rows, list) or not rows:
                    break
                events.extend(
                    event
                    for row in rows
                    if isinstance(row, dict)
                    for event in [_event_from_row(row)]
                    if event is not None
                )
                pages_read += 1
                cursor = _next_cursor(payload)
                if not cursor:
                    break
            if len(_dedupe_events(events)) >= limit:
                break

    ranked = _dedupe_events(events)[:limit]
    return GdeltCloudLeadFetchResult(
        leads=[_event_to_lead(event) for event in ranked],
        fetched_event_count=len(events),
    )


def parse_gdelt_cloud_csv_list(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None or value.strip().lower() in {"", "default"}:
        return default
    if value.strip().lower() == "all":
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _read_events(
    *,
    api_key: str,
    api_url: str,
    days: int,
    limit: int,
    country: str | None,
    confidence_profile: str,
    sort: str,
    cursor: str | None,
    timeout_seconds: float,
    opener,
) -> dict[str, Any] | None:
    today = datetime.now(tz=UTC).date()
    # GDELT Cloud treats date_start/date_end as an inclusive window.
    start = today - timedelta(days=max(days - 1, 0))
    params = {
        "event_family": "conflict",
        "date_start": start.isoformat(),
        "date_end": today.isoformat(),
        "sort": sort,
        "confidence_profile": confidence_profile,
        "limit": str(limit),
    }
    if cursor:
        params["cursor"] = cursor
    if country:
        params["country"] = country
    request = Request(
        f"{api_url}?{urlencode(params)}",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        },
    )
    try:
        with opener(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError):
        return None


def _next_cursor(payload: dict[str, Any]) -> str | None:
    pagination = payload.get("pagination")
    if not isinstance(pagination, dict):
        return None
    cursor = pagination.get("next_cursor")
    return cursor if isinstance(cursor, str) and cursor else None


def _event_from_row(row: dict[str, Any]) -> _GdeltCloudEvent | None:
    geo = row.get("geo")
    metrics = row.get("metrics")
    if not isinstance(geo, dict):
        return None
    if not isinstance(metrics, dict):
        metrics = {}

    event_id = _string(row.get("id"))
    title = _string(row.get("title"))
    event_date = _parse_date(_string(row.get("event_date")))
    latitude = _safe_float(geo.get("latitude"))
    longitude = _safe_float(geo.get("longitude"))
    if not event_id or not title or event_date is None:
        return None
    if latitude is None or longitude is None or (latitude == 0 and longitude == 0):
        return None

    return _GdeltCloudEvent(
        event_id=event_id,
        title=title,
        summary=_string(row.get("summary")) or None,
        event_date=event_date,
        category=_string(row.get("category")) or None,
        subcategory=_string(row.get("subcategory")) or None,
        country=_string(geo.get("country")) or None,
        region=_string(geo.get("region")) or None,
        admin1=_string(geo.get("admin1")) or None,
        location=_string(geo.get("location")) or None,
        latitude=latitude,
        longitude=longitude,
        source_url=_string(row.get("url"))
        or _string(row.get("primary_story_url"))
        or _top_article_url(row),
        article_count=_safe_int(metrics.get("article_count")),
        confidence=_safe_float(metrics.get("confidence")),
        significance=_safe_float(metrics.get("significance")),
        fatalities=_safe_int(row.get("fatalities")),
    )


def _dedupe_events(events: list[_GdeltCloudEvent]) -> list[_GdeltCloudEvent]:
    best_by_key: dict[tuple[str, str, float, float], _GdeltCloudEvent] = {}
    for event in events:
        key = (
            event.category or "",
            event.country or "",
            round(event.latitude, 2),
            round(event.longitude, 2),
        )
        current = best_by_key.get(key)
        if current is None or _event_rank(event) > _event_rank(current):
            best_by_key[key] = event
    return sorted(best_by_key.values(), key=_event_rank, reverse=True)


def _event_rank(event: _GdeltCloudEvent) -> tuple[float, float, int, int, str]:
    return (
        event.significance or 0.0,
        event.confidence or 0.0,
        event.fatalities,
        event.article_count,
        event.event_id,
    )


def _event_to_lead(event: _GdeltCloudEvent) -> Lead:
    category = event.subcategory or event.category or "conflict event"
    summary_parts = [f"GDELT Cloud conflict event: {category}."]
    if event.summary:
        summary_parts.append(event.summary)
    if event.confidence is not None:
        summary_parts.append(f"Confidence {event.confidence:.2f}.")
    if event.significance is not None:
        summary_parts.append(f"Significance {event.significance:.2f}.")
    if event.article_count:
        summary_parts.append(f"{event.article_count} linked source articles.")
    if event.fatalities:
        summary_parts.append(f"Fatalities reported: {event.fatalities}.")
    return Lead(
        lead_id=f"gdeltcloud_{event.event_id}_{_stable_suffix(event.title)}",
        title=event.title,
        region=_region_label(event),
        latitude=event.latitude,
        longitude=event.longitude,
        category_guess=_category_guess(event),
        status="lead_only",
        summary=" ".join(summary_parts),
        source_url=event.source_url,
        source_date=event.event_date,
        last_refreshed_at=datetime.now(tz=UTC).replace(microsecond=0),
    )


def _category_guess(event: _GdeltCloudEvent) -> AssetType:
    haystack = " ".join(
        item
        for item in (
            event.title,
            event.summary,
            event.category,
            event.subcategory,
            event.location,
            event.admin1,
        )
        if item
    ).lower()
    if any(term in haystack for term in ("hospital", "clinic", "medical", "ambulance")):
        return "medical_aid_node"
    if any(term in haystack for term in ("bridge", "crossing")):
        return "bridge"
    if any(term in haystack for term in ("port", "harbor", "harbour", "terminal")):
        return "container_port"
    if any(term in haystack for term in ("dam", "water", "reservoir", "station")):
        return "water_infrastructure"
    if any(term in haystack for term in ("warehouse", "logistics", "depot")):
        return "logistics_hub"
    if any(term in haystack for term in ("camp", "shelter", "refugee", "displaced")):
        return "aid_shelter_campus"
    return "civilian_building_cluster"


def _region_label(event: _GdeltCloudEvent) -> str:
    parts = [event.location, event.admin1, event.country, event.region]
    return ", ".join(part for part in parts if part) or "Unknown location"


def _top_article_url(row: dict[str, Any]) -> str | None:
    articles = row.get("top_articles")
    if not isinstance(articles, list) or not articles:
        return None
    first = articles[0]
    if not isinstance(first, dict):
        return None
    return _string(first.get("url")) or _string(first.get("source_url")) or None


def _stable_suffix(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]


def _parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
