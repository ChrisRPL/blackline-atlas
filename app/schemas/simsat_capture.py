from __future__ import annotations

from pydantic import BaseModel

from app.schemas.asset import Asset


class SimSatSentinelMetadata(BaseModel):
    image_available: bool
    source: str | None = None
    spectral_bands: list[str]
    footprint: list[float]
    size_km: float
    cloud_cover: float | None = None
    datetime: str | None = None
    satellite_position: list[float] | None = None
    timestamp: str | None = None


class SimSatCaptureFrame(BaseModel):
    frame_id: str
    requested_timestamp: str
    request_url: str
    image_path: str | None = None
    metadata_path: str
    response_metadata: SimSatSentinelMetadata


class SimSatCaptureRecord(BaseModel):
    case_id: str
    pack_version: str
    asset: Asset
    current: SimSatCaptureFrame
    baseline: SimSatCaptureFrame
