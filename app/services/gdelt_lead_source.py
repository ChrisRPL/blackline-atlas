from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.schemas.asset import AssetType
from app.schemas.lead import Lead

GDELT_LASTUPDATE_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"
GDELT_EXPORT_INTERVAL_MINUTES = 15
_USER_AGENT = "BlacklineAtlasLiveLeadIngest/0.1"
_CONFLICT_ROOT_CODES = {"14", "18", "19", "20"}
DEFAULT_CONFLICT_COUNTRY_CODES = frozenset(
    {
        "AF",
        "BM",
        "CF",
        "CG",
        "ET",
        "GZ",
        "HA",
        "IN",
        "IR",
        "IS",
        "IZ",
        "LE",
        "LY",
        "ML",
        "MX",
        "PK",
        "RS",
        "SO",
        "SU",
        "SY",
        "UP",
        "WE",
        "YM",
    }
)
_ROOT_LABELS = {
    "14": "civil unrest",
    "18": "assault",
    "19": "armed conflict",
    "20": "mass violence",
}


@dataclass(frozen=True)
class GdeltLeadFetchResult:
    leads: list[Lead]
    fetched_file_count: int


@dataclass(frozen=True)
class _GdeltEvent:
    global_event_id: str
    sql_date: date
    event_code: str
    event_root_code: str
    event_label: str
    action_geo_full_name: str
    action_geo_country_code: str
    latitude: float
    longitude: float
    num_articles: int
    source_url: str | None


def fetch_gdelt_conflict_leads(
    *,
    lastupdate_url: str = GDELT_LASTUPDATE_URL,
    hours: int = 24,
    max_files: int = 96,
    limit: int = 160,
    min_articles: int = 1,
    country_allowlist: frozenset[str] | set[str] | None = DEFAULT_CONFLICT_COUNTRY_CODES,
    timeout_seconds: float = 8.0,
    opener=urlopen,
) -> GdeltLeadFetchResult:
    latest_export_url = _latest_export_url(
        lastupdate_url=lastupdate_url,
        timeout_seconds=timeout_seconds,
        opener=opener,
    )
    export_urls = _recent_export_urls(
        latest_export_url=latest_export_url,
        hours=hours,
        max_files=max_files,
    )

    events: list[_GdeltEvent] = []
    fetched_file_count = 0
    for export_url in export_urls:
        payload = _read_url(export_url, timeout_seconds=timeout_seconds, opener=opener)
        if payload is None:
            continue
        fetched_file_count += 1
        events.extend(
            _events_from_export_zip(
                payload,
                min_articles=min_articles,
                country_allowlist=country_allowlist,
            )
        )

    leads = [_event_to_lead(event) for event in _dedupe_events(events)[:limit]]
    return GdeltLeadFetchResult(leads=leads, fetched_file_count=fetched_file_count)


def _latest_export_url(*, lastupdate_url: str, timeout_seconds: float, opener) -> str | None:
    payload = _read_url(lastupdate_url, timeout_seconds=timeout_seconds, opener=opener)
    if payload is None:
        return None

    for token in payload.decode("utf-8", errors="replace").split():
        if token.endswith(".export.CSV.zip"):
            return token
    return None


def _recent_export_urls(*, latest_export_url: str | None, hours: int, max_files: int) -> list[str]:
    if latest_export_url is None:
        return []

    match = re.search(r"(?P<ts>\d{14})\.export\.CSV\.zip$", latest_export_url)
    if match is None:
        return [latest_export_url]

    latest_ts = datetime.strptime(match.group("ts"), "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    base_url = latest_export_url.rsplit("/", 1)[0]
    file_count = max(1, min(max_files, (max(hours, 1) * 60) // GDELT_EXPORT_INTERVAL_MINUTES))
    urls = []
    for index in range(file_count):
        export_ts = latest_ts - timedelta(minutes=GDELT_EXPORT_INTERVAL_MINUTES * index)
        urls.append(f"{base_url}/{export_ts.strftime('%Y%m%d%H%M%S')}.export.CSV.zip")
    return urls


def _events_from_export_zip(
    payload: bytes,
    *,
    min_articles: int,
    country_allowlist: frozenset[str] | set[str] | None,
) -> list[_GdeltEvent]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile:
        return []

    events: list[_GdeltEvent] = []
    for name in archive.namelist():
        if not name.endswith((".CSV", ".csv")):
            continue
        with archive.open(name) as file:
            text_stream = io.TextIOWrapper(file, encoding="utf-8", errors="replace", newline="")
            reader = csv.reader(text_stream, delimiter="\t")
            for row in reader:
                event = _event_from_row(
                    row,
                    min_articles=min_articles,
                    country_allowlist=country_allowlist,
                )
                if event is not None:
                    events.append(event)
    return events


def _event_from_row(
    row: list[str],
    *,
    min_articles: int,
    country_allowlist: frozenset[str] | set[str] | None,
) -> _GdeltEvent | None:
    if len(row) < 61:
        return None
    if row[25] != "1":
        return None
    if row[28] not in _CONFLICT_ROOT_CODES:
        return None
    if country_allowlist is not None and row[53].upper() not in country_allowlist:
        return None
    if _safe_int(row[51]) <= 1:
        return None

    latitude = _safe_float(row[56])
    longitude = _safe_float(row[57])
    if latitude is None or longitude is None or (latitude == 0 and longitude == 0):
        return None

    num_articles = _safe_int(row[33])
    if num_articles < min_articles:
        return None

    sql_date = _parse_sqldate(row[1])
    if sql_date is None:
        return None

    root_code = row[28]
    return _GdeltEvent(
        global_event_id=row[0],
        sql_date=sql_date,
        event_code=row[26],
        event_root_code=root_code,
        event_label=_ROOT_LABELS.get(root_code, "conflict event"),
        action_geo_full_name=row[52] or "Unknown location",
        action_geo_country_code=row[53] or "unknown",
        latitude=latitude,
        longitude=longitude,
        num_articles=num_articles,
        source_url=row[60] or None,
    )


def _dedupe_events(events: list[_GdeltEvent]) -> list[_GdeltEvent]:
    best_by_key: dict[tuple[str, str, float, float], _GdeltEvent] = {}
    for event in events:
        key = (
            event.event_root_code,
            event.action_geo_country_code,
            round(event.latitude, 2),
            round(event.longitude, 2),
        )
        current = best_by_key.get(key)
        if current is None or _event_rank(event) > _event_rank(current):
            best_by_key[key] = event

    return sorted(best_by_key.values(), key=_event_rank, reverse=True)


def _event_rank(event: _GdeltEvent) -> tuple[int, int, str]:
    root_priority = {"20": 4, "19": 3, "18": 2, "14": 1}.get(event.event_root_code, 0)
    return (root_priority, event.num_articles, event.global_event_id)


def _event_to_lead(event: _GdeltEvent) -> Lead:
    title = _title_for_event(event)
    return Lead(
        lead_id=f"gdelt_{event.global_event_id}_{_stable_suffix(title)}",
        title=title,
        region=event.action_geo_full_name,
        latitude=event.latitude,
        longitude=event.longitude,
        category_guess=_category_guess(event),
        status="lead_only",
        summary=(
            f"Live GDELT {event.event_label} lead from {event.num_articles} "
            f"source article{'' if event.num_articles == 1 else 's'}."
        ),
        source_url=event.source_url,
        source_date=event.sql_date,
        last_refreshed_at=datetime.now(tz=UTC).replace(microsecond=0),
    )


def _title_for_event(event: _GdeltEvent) -> str:
    location = event.action_geo_full_name.split(",", 1)[0].strip() or "Unknown location"
    return f"{location} {event.event_label}"


def _category_guess(event: _GdeltEvent) -> AssetType:
    haystack = f"{event.action_geo_full_name} {event.source_url or ''}".lower()
    if any(term in haystack for term in ("hospital", "clinic", "medical")):
        return "medical_aid_node"
    if any(term in haystack for term in ("bridge", "crossing")):
        return "bridge"
    if any(term in haystack for term in ("port", "harbor", "harbour", "terminal")):
        return "container_port"
    if any(term in haystack for term in ("dam", "water", "reservoir", "station")):
        return "water_infrastructure"
    if any(term in haystack for term in ("warehouse", "logistics", "depot")):
        return "logistics_hub"
    if any(term in haystack for term in ("camp", "shelter", "refugee")):
        return "aid_shelter_campus"
    return "civilian_building_cluster"


def _stable_suffix(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]


def _parse_sqldate(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        return None


def _safe_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def _safe_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _read_url(url: str, *, timeout_seconds: float, opener) -> bytes | None:
    request = Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with opener(request, timeout=timeout_seconds) as response:
            return response.read()
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        return None
