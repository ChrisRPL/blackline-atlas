from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FrameRequest:
    asset_id: str
    scenario_id: str
    latitude: float | None = None
    longitude: float | None = None
    requested_timestamp: str | None = None
    baseline_timestamp: str | None = None
    size_km: float = 5.0
    window_seconds: float = 10 * 24 * 60 * 60
    spectral_bands: tuple[str, ...] = ("red", "green", "blue")
