from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

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
