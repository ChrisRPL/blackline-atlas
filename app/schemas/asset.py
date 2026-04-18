from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

AssetType = Literal[
    "grain_port",
    "container_port",
    "bridge",
    "water_infrastructure",
    "logistics_hub",
    "rail_yard",
    "aid_corridor_node",
    "aid_warehouse_cluster",
    "medical_aid_node",
]
AssetEvidenceState = Literal[
    "watch_only",
    "live_demo",
    "reference_event",
    "reference_control",
]


class Asset(BaseModel):
    asset_id: str
    asset_name: str
    asset_type: AssetType
    region: str
    latitude: float
    longitude: float
    hero: bool = False
    evidence_available: bool = False
    evidence_state: AssetEvidenceState | None = None
