from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from app.core.config import load_local_env
from app.schemas.lead import Lead
from app.services.acled_lead_source import (
    ACLED_API_URL,
    ACLED_TOKEN_URL,
    DEFAULT_ACLED_COUNTRIES,
    fetch_acled_conflict_leads,
    parse_acled_csv_list,
    request_acled_access_token,
)
from app.services.gdelt_cloud_lead_source import (
    DEFAULT_GDELT_CLOUD_COUNTRIES,
    GDELT_CLOUD_EVENTS_URL,
    fetch_gdelt_cloud_conflict_leads,
    parse_gdelt_cloud_csv_list,
)
from app.services.gdelt_lead_source import (
    DEFAULT_CONFLICT_COUNTRY_CODES,
    GDELT_LASTUPDATE_URL,
    fetch_gdelt_conflict_leads,
)
from app.services.lead_registry_loader import DEFAULT_LEAD_REGISTRY_PATH, load_lead_registry

DEFAULT_LEAD_SOURCE_PATH = Path(__file__).with_name("lead_sources.seed.json")
_USER_AGENT = "BlacklineAtlasLeadRefresh/0.1"


def load_lead_sources(manifest_path: str | None) -> list[Lead]:
    path = Path(manifest_path) if manifest_path else DEFAULT_LEAD_SOURCE_PATH

    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
        return [Lead.model_validate(entry) for entry in entries]
    except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError, ValidationError):
        return []


def refresh_lead_registry(
    *,
    source_path: str | None,
    output_path: str | None,
    source_mode: str = "seed",
    timeout_seconds: float = 8.0,
    gdelt_lastupdate_url: str = GDELT_LASTUPDATE_URL,
    gdelt_hours: int = 24,
    gdelt_max_files: int = 96,
    gdelt_limit: int = 160,
    gdelt_min_articles: int = 1,
    gdelt_country_allowlist: frozenset[str] | set[str] | None = DEFAULT_CONFLICT_COUNTRY_CODES,
    acled_access_token: str | None = None,
    acled_username: str | None = None,
    acled_password: str | None = None,
    acled_api_url: str = ACLED_API_URL,
    acled_token_url: str = ACLED_TOKEN_URL,
    acled_days: int = 14,
    acled_limit: int = 160,
    acled_countries: tuple[str, ...] = DEFAULT_ACLED_COUNTRIES,
    gdelt_cloud_api_key: str | None = None,
    gdelt_cloud_api_url: str = GDELT_CLOUD_EVENTS_URL,
    gdelt_cloud_days: int = 7,
    gdelt_cloud_limit: int = 160,
    gdelt_cloud_countries: tuple[str, ...] = DEFAULT_GDELT_CLOUD_COUNTRIES,
    gdelt_cloud_confidence_profile: str = "balanced",
    opener=urlopen,
    dry_run: bool = False,
    preserve_on_empty: bool = False,
) -> tuple[list[Lead], int]:
    output = Path(output_path) if output_path else DEFAULT_LEAD_REGISTRY_PATH
    existing_by_id = {lead.lead_id: lead for lead in load_lead_registry(str(output))}
    refreshed_at = datetime.now(tz=UTC).replace(microsecond=0)
    if source_mode == "gdelt_cloud":
        result = fetch_gdelt_cloud_conflict_leads(
            api_key=gdelt_cloud_api_key,
            api_url=gdelt_cloud_api_url,
            days=gdelt_cloud_days,
            limit=gdelt_cloud_limit,
            countries=gdelt_cloud_countries,
            confidence_profile=gdelt_cloud_confidence_profile,
            timeout_seconds=timeout_seconds,
            opener=opener,
        )
        sources = result.leads
        reachable_count = 1 if result.fetched_event_count else 0
    elif source_mode == "acled":
        token = acled_access_token or request_acled_access_token(
            username=acled_username,
            password=acled_password,
            token_url=acled_token_url,
            timeout_seconds=timeout_seconds,
            opener=opener,
        )
        result = fetch_acled_conflict_leads(
            access_token=token,
            api_url=acled_api_url,
            days=acled_days,
            limit=acled_limit,
            countries=acled_countries,
            timeout_seconds=timeout_seconds,
            opener=opener,
        )
        sources = result.leads
        reachable_count = 1 if result.fetched_event_count else 0
    elif source_mode == "gdelt":
        result = fetch_gdelt_conflict_leads(
            lastupdate_url=gdelt_lastupdate_url,
            hours=gdelt_hours,
            max_files=gdelt_max_files,
            limit=gdelt_limit,
            min_articles=gdelt_min_articles,
            country_allowlist=gdelt_country_allowlist,
            timeout_seconds=timeout_seconds,
            opener=opener,
        )
        sources = result.leads
        reachable_count = result.fetched_file_count
    else:
        sources = load_lead_sources(source_path)
        reachable_count = 0

    refreshed: list[Lead] = []
    for source in sources:
        if source_mode == "seed" and _source_is_reachable(
            source.source_url,
            timeout_seconds=timeout_seconds,
            opener=opener,
        ):
            reachable_count += 1
        refreshed.append(_merged_lead(source, existing_by_id.get(source.lead_id), refreshed_at))

    if not dry_run and (refreshed or not preserve_on_empty):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                [lead.model_dump(mode="json", exclude_none=True) for lead in refreshed],
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return refreshed, reachable_count


def lead_refresh_summary(
    *,
    leads: list[Lead],
    reachable_count: int,
    output_path: str | None,
    dry_run: bool,
) -> dict[str, Any]:
    output = Path(output_path) if output_path else DEFAULT_LEAD_REGISTRY_PATH
    status_counts: dict[str, int] = {}
    linked_count = 0
    for lead in leads:
        status_counts[lead.status] = status_counts.get(lead.status, 0) + 1
        if lead.linked_asset_id:
            linked_count += 1
    return {
        "dry_run": dry_run,
        "output_path": str(output),
        "lead_count": len(leads),
        "linked_asset_count": linked_count,
        "reachable_source_count": reachable_count,
        "status_counts": status_counts,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh the deterministic Blackline Atlas lead registry from curated sources.",
    )
    parser.add_argument("--source-path", default=None)
    parser.add_argument("--output-path", default=None)
    parser.add_argument(
        "--source-mode",
        choices=("seed", "gdelt", "gdelt_cloud", "acled"),
        default="seed",
        help="Use curated seeds, GDELT Project exports, GDELT Cloud, or ACLED.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--gdelt-lastupdate-url", default=GDELT_LASTUPDATE_URL)
    parser.add_argument("--gdelt-hours", type=int, default=24)
    parser.add_argument("--gdelt-max-files", type=int, default=96)
    parser.add_argument("--gdelt-limit", type=int, default=160)
    parser.add_argument("--gdelt-min-articles", type=int, default=1)
    parser.add_argument(
        "--gdelt-country-allowlist",
        default="default",
        help=(
            "Comma-separated GDELT/FIPS action country codes. Use 'default' for the "
            "conflict-priority set or 'all' to disable country filtering."
        ),
    )
    parser.add_argument("--acled-access-token", default=None)
    parser.add_argument("--acled-username", default=None)
    parser.add_argument("--acled-password", default=None)
    parser.add_argument("--acled-api-url", default=ACLED_API_URL)
    parser.add_argument("--acled-token-url", default=ACLED_TOKEN_URL)
    parser.add_argument("--acled-days", type=int, default=14)
    parser.add_argument("--acled-limit", type=int, default=160)
    parser.add_argument(
        "--acled-countries",
        default="default",
        help="Comma-separated country names. Use 'default' for conflict-priority countries.",
    )
    parser.add_argument("--gdelt-cloud-api-key", default=None)
    parser.add_argument("--gdelt-cloud-api-url", default=GDELT_CLOUD_EVENTS_URL)
    parser.add_argument("--gdelt-cloud-days", type=int, default=7)
    parser.add_argument("--gdelt-cloud-limit", type=int, default=160)
    parser.add_argument("--gdelt-cloud-confidence-profile", default="balanced")
    parser.add_argument(
        "--gdelt-cloud-countries",
        default="default",
        help="Comma-separated country names. Use 'default' for conflict-priority countries.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Probe and summarize sources without rewriting the registry file.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    load_local_env()
    args = parse_args(argv)
    leads, reachable_count = refresh_lead_registry(
        source_path=args.source_path,
        output_path=args.output_path,
        source_mode=args.source_mode,
        timeout_seconds=args.timeout_seconds,
        gdelt_lastupdate_url=args.gdelt_lastupdate_url,
        gdelt_hours=args.gdelt_hours,
        gdelt_max_files=args.gdelt_max_files,
        gdelt_limit=args.gdelt_limit,
        gdelt_min_articles=args.gdelt_min_articles,
        gdelt_country_allowlist=parse_gdelt_country_allowlist(args.gdelt_country_allowlist),
        acled_access_token=args.acled_access_token or os.getenv("ACLED_ACCESS_TOKEN") or None,
        acled_username=args.acled_username or os.getenv("ACLED_USERNAME") or None,
        acled_password=args.acled_password or os.getenv("ACLED_PASSWORD") or None,
        acled_api_url=args.acled_api_url,
        acled_token_url=args.acled_token_url,
        acled_days=args.acled_days,
        acled_limit=args.acled_limit,
        acled_countries=parse_acled_csv_list(args.acled_countries, DEFAULT_ACLED_COUNTRIES),
        gdelt_cloud_api_key=(
            args.gdelt_cloud_api_key
            or os.getenv("GDELT_API_KEY")
            or os.getenv("GDELT_CLOUD_API_KEY")
            or None
        ),
        gdelt_cloud_api_url=args.gdelt_cloud_api_url,
        gdelt_cloud_days=args.gdelt_cloud_days,
        gdelt_cloud_limit=args.gdelt_cloud_limit,
        gdelt_cloud_countries=parse_gdelt_cloud_csv_list(
            args.gdelt_cloud_countries,
            DEFAULT_GDELT_CLOUD_COUNTRIES,
        ),
        gdelt_cloud_confidence_profile=args.gdelt_cloud_confidence_profile,
        dry_run=args.dry_run,
    )
    print(
        json.dumps(
            lead_refresh_summary(
                leads=leads,
                reachable_count=reachable_count,
                output_path=args.output_path,
                dry_run=args.dry_run,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


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


def parse_gdelt_country_allowlist(value: str) -> frozenset[str] | None:
    normalized = value.strip().lower()
    if normalized in {"", "default"}:
        return DEFAULT_CONFLICT_COUNTRY_CODES
    if normalized == "all":
        return None
    return frozenset(part.strip().upper() for part in value.split(",") if part.strip())


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


if __name__ == "__main__":
    raise SystemExit(main())
