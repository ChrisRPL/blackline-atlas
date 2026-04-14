from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FrameRequest:
    asset_id: str
    scenario_id: str
