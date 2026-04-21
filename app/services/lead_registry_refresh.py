from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.schemas.lead import Lead
from app.services.lead_registry_loader import DEFAULT_LEAD_REGISTRY_PATH, load_lead_registry

DEFAULT_LEAD_SOURCE_PATH = Path(__file__).with_name("lead_sources.seed.json")
_USER_AGENT = "BlacklineAtlasLeadRefresh/0.1"


def load_lead_sources(manifest_path: str | None) -> list[Lead]:
    path = Path(manifest_path) if manifest_path else DEFAULT_LEAD_SOURCE_PATH

    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
        return [Lead.model_validate(entry) for entry in entries]
    except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
        return []


def refresh_lead_registry(
    *,
    source_path: str | None,
    output_path: str | None,
    timeout_seconds: float = 8.0,
    opener=urlopen,
) -> tuple[list[Lead], int]:
    output = Path(output_path) if output_path else DEFAULT_LEAD_REGISTRY_PATH
    existing_by_id = {lead.lead_id: lead for lead in load_lead_registry(str(output))}
    refreshed_at = datetime.now(tz=UTC).replace(microsecond=0)
    sources = load_lead_sources(source_path)

    reachable_count = 0
    refreshed: list[Lead] = []
    for source in sources:
        if _source_is_reachable(source.source_url, timeout_seconds=timeout_seconds, opener=opener):
            reachable_count += 1
        refreshed.append(_merged_lead(source, existing_by_id.get(source.lead_id), refreshed_at))

    output.write_text(
        json.dumps(
            [lead.model_dump(mode="json", exclude_none=True) for lead in refreshed],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return refreshed, reachable_count


def _merged_lead(source: Lead, existing: Lead | None, refreshed_at: datetime) -> Lead:
    payload = source.model_dump(mode="python", exclude_none=True)
    if existing is not None:
        if existing.linked_asset_id and "linked_asset_id" not in payload:
            payload["linked_asset_id"] = existing.linked_asset_id
        if existing.summary and "summary" not in payload:
            payload["summary"] = existing.summary
        if existing.category_guess and "category_guess" not in payload:
            payload["category_guess"] = existing.category_guess
        if existing.status in {"reference_event", "reference_control", "vlm_reviewed"}:
            payload["status"] = existing.status
    payload["last_refreshed_at"] = refreshed_at.isoformat().replace("+00:00", "Z")
    return Lead.model_validate(payload)


def _source_is_reachable(
    source_url: str | None,
    *,
    timeout_seconds: float,
    opener=urlopen,
) -> bool:
    if not source_url:
        return False

    request = Request(source_url, headers={"User-Agent": _USER_AGENT})
    try:
        with opener(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", 200)
            return 200 <= status < 400
    except (HTTPError, URLError, TimeoutError, ValueError):
        return False
