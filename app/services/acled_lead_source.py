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

ACLED_API_URL = "https://acleddata.com/api/acled/read"
ACLED_TOKEN_URL = "https://acleddata.com/oauth/token"
DEFAULT_ACLED_COUNTRIES = (
    "Ukraine",
    "Palestine",
    "Lebanon",
    "Syria",
    "Yemen",
    "Sudan",
    "Myanmar",
    "Iraq",
    "Libya",
    "Iran",
    "Mexico",
    "Afghanistan",
    "Pakistan",
    "Somalia",
    "Ethiopia",
    "Democratic Republic of Congo",
    "Mali",
)
DEFAULT_ACLED_EVENT_TYPES = (
    "Battles",
    "Explosions/Remote violence",
    "Violence against civilians",
    "Strategic developments",
)
ACLED_FIELDS = (
    "event_id_cnty",
    "event_date",
    "disorder_type",
    "event_type",
    "sub_event_type",
    "country",
    "admin1",
    "admin2",
    "location",
    "latitude",
    "longitude",
    "geo_precision",
    "source",
    "source_scale",
    "notes",
    "fatalities",
    "civilian_targeting",
    "tags",
    "timestamp",
)
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 "
    "BlacklineAtlasACLEDLeadIngest/0.1"
)


@dataclass(frozen=True)
class AcledLeadFetchResult:
    leads: list[Lead]
    fetched_event_count: int


@dataclass(frozen=True)
class _AcledEvent:
    event_id: str
    event_date: date
    event_type: str
    sub_event_type: str
    country: str
    admin1: str | None
    admin2: str | None
    location: str
    latitude: float
    longitude: float
    geo_precision: int
    source: str | None
    notes: str | None
    fatalities: int
    civilian_targeting: str | None
    tags: str | None


def fetch_acled_conflict_leads(
    *,
    access_token: str | None,
    api_url: str = ACLED_API_URL,
    days: int = 14,
    limit: int = 160,
    countries: tuple[str, ...] = DEFAULT_ACLED_COUNTRIES,
    event_types: tuple[str, ...] = DEFAULT_ACLED_EVENT_TYPES,
    timeout_seconds: float = 8.0,
    opener=urlopen,
) -> AcledLeadFetchResult:
    if not access_token:
        return AcledLeadFetchResult(leads=[], fetched_event_count=0)

    today = datetime.now(tz=UTC).date()
    start_date = today - timedelta(days=max(days, 1))
    params = {
        "_format": "json",
        "event_date": f"{start_date.isoformat()}|{today.isoformat()}",
        "event_date_where": "BETWEEN",
        "event_type": _or_filter("event_type", event_types),
        "fields": "|".join(ACLED_FIELDS),
        "limit": str(limit),
    }
    if countries:
        params["country"] = _or_filter("country", countries)

    payload = _read_json(
        f"{api_url}?{urlencode(params)}",
        access_token=access_token,
        timeout_seconds=timeout_seconds,
        opener=opener,
    )
    if payload is None:
        return AcledLeadFetchResult(leads=[], fetched_event_count=0)

    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return AcledLeadFetchResult(leads=[], fetched_event_count=0)

    events = [_event_from_row(row) for row in rows if isinstance(row, dict)]
    filtered = [event for event in events if event is not None]
    leads = [_event_to_lead(event) for event in _dedupe_events(filtered)[:limit]]
    return AcledLeadFetchResult(leads=leads, fetched_event_count=len(rows))


def request_acled_access_token(
    *,
    username: str | None,
    password: str | None,
    token_url: str = ACLED_TOKEN_URL,
    timeout_seconds: float = 8.0,
    opener=urlopen,
) -> str | None:
    if not username or not password:
        return None

    body = urlencode(
        {
            "username": username,
            "password": password,
            "grant_type": "password",
            "client_id": "acled",
            "scope": "authenticated",
        }
    ).encode("utf-8")
    request = Request(
        token_url,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": _USER_AGENT,
        },
        method="POST",
    )
    try:
        with opener(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError):
        return None

    token = payload.get("access_token") if isinstance(payload, dict) else None
    return token if isinstance(token, str) and token.strip() else None


def parse_acled_csv_list(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None or value.strip().lower() in {"", "default"}:
        return default
    if value.strip().lower() == "all":
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _event_from_row(row: dict[str, Any]) -> _AcledEvent | None:
    event_id = _string(row.get("event_id_cnty"))
    event_date = _parse_date(_string(row.get("event_date")))
    latitude = _safe_float(row.get("latitude"))
    longitude = _safe_float(row.get("longitude"))
    location = _string(row.get("location"))
    event_type = _string(row.get("event_type"))
    if not event_id or event_date is None or latitude is None or longitude is None:
        return None
    if not location or not event_type:
        return None

    return _AcledEvent(
        event_id=event_id,
        event_date=event_date,
        event_type=event_type,
        sub_event_type=_string(row.get("sub_event_type")) or event_type,
        country=_string(row.get("country")) or "Unknown country",
        admin1=_string(row.get("admin1")) or None,
        admin2=_string(row.get("admin2")) or None,
        location=location,
        latitude=latitude,
        longitude=longitude,
        geo_precision=_safe_int(row.get("geo_precision")),
        source=_string(row.get("source")) or None,
        notes=_string(row.get("notes")) or None,
        fatalities=_safe_int(row.get("fatalities")),
        civilian_targeting=_string(row.get("civilian_targeting")) or None,
        tags=_string(row.get("tags")) or None,
    )


def _dedupe_events(events: list[_AcledEvent]) -> list[_AcledEvent]:
    best_by_key: dict[tuple[str, float, float, str], _AcledEvent] = {}
    for event in events:
        key = (
            event.event_type,
            round(event.latitude, 2),
            round(event.longitude, 2),
            event.location.lower(),
        )
        current = best_by_key.get(key)
        if current is None or _event_rank(event) > _event_rank(current):
            best_by_key[key] = event
    return sorted(best_by_key.values(), key=_event_rank, reverse=True)


def _event_rank(event: _AcledEvent) -> tuple[str, int, int, str]:
    return (
        event.event_date.isoformat(),
        event.fatalities,
        -event.geo_precision,
        event.event_id,
    )


def _event_to_lead(event: _AcledEvent) -> Lead:
    title = f"{event.location} {event.sub_event_type}".strip()
    region_parts = [event.location, event.admin2, event.admin1, event.country]
    region = ", ".join(part for part in region_parts if part)
    source_note = f" Source: {event.source}." if event.source else ""
    civilian_note = ""
    if event.civilian_targeting and event.civilian_targeting != "0":
        civilian_note = " Civilian targeting flagged."
    fatality_note = f" Fatalities reported: {event.fatalities}." if event.fatalities else ""
    return Lead(
        lead_id=f"acled_{event.event_id}_{_stable_suffix(title)}",
        title=title,
        region=region,
        latitude=event.latitude,
        longitude=event.longitude,
        category_guess=_category_guess(event),
        status="lead_only",
        summary=(
            f"ACLED {event.event_type} / {event.sub_event_type} lead from "
            f"{event.event_date.isoformat()}.{civilian_note}{fatality_note}{source_note}"
        ),
        source_date=event.event_date,
        last_refreshed_at=datetime.now(tz=UTC).replace(microsecond=0),
    )


def _category_guess(event: _AcledEvent) -> AssetType:
    haystack = " ".join(
        item
        for item in (
            event.location,
            event.admin1,
            event.admin2,
            event.notes,
            event.tags,
            event.source,
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


def _or_filter(field: str, values: tuple[str, ...]) -> str:
    if not values:
        return ""
    first, *rest = values
    return first + "".join(f":OR:{field}={value}" for value in rest)


def _read_json(
    url: str,
    *,
    access_token: str,
    timeout_seconds: float,
    opener,
) -> dict[str, Any] | None:
    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        },
    )
    try:
        with opener(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError):
        return None


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
