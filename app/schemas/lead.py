from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.asset import AssetType

LeadStatus = Literal[
    "lead_only",
    "vlm_reviewed",
    "reference_event",
    "reference_control",
]


class Lead(BaseModel):
    lead_id: str
    title: str
    region: str
    latitude: float
    longitude: float
    category_guess: AssetType | None = None
    status: LeadStatus
    summary: str | None = None
    source_url: str | None = None
    source_date: date | None = None
    linked_asset_id: str | None = None
    last_refreshed_at: datetime | None = None


LeadRefreshSourceMode = Literal["auto", "seed", "gdelt", "gdelt_cloud", "acled"]


class LeadRefreshRequest(BaseModel):
    source_mode: LeadRefreshSourceMode = "auto"
    hours: int = Field(default=72, ge=1, le=72)
    max_files: int = Field(default=288, ge=1, le=288)
    limit: int = Field(default=500, ge=1, le=500)
    min_articles: int = Field(default=1, ge=1, le=50)
    country_allowlist: str = "default"
    acled_days: int = Field(default=14, ge=1, le=90)
    acled_countries: str = "default"
    gdelt_cloud_days: int = Field(default=30, ge=1, le=30)
    gdelt_cloud_countries: str = "default"
    gdelt_cloud_confidence_profile: str = "loose"
    dry_run: bool = False


class LeadRefreshResponse(BaseModel):
    dry_run: bool
    output_path: str
    source_mode: LeadRefreshSourceMode
    lead_count: int
    linked_asset_count: int
    reachable_source_count: int
    status_counts: dict[str, int]
    leads: list[Lead]
