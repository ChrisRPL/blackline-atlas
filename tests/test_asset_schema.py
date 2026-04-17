from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.asset import Asset  # noqa: E402


def test_asset_allows_water_infrastructure_type() -> None:
    asset = Asset(
        asset_id="desal_01",
        asset_name="Demo Desalination Plant",
        asset_type="water_infrastructure",
        region="Gulf Coast",
        latitude=26.0,
        longitude=50.0,
    )

    assert asset.asset_type == "water_infrastructure"


def test_asset_allows_aid_warehouse_cluster_type() -> None:
    asset = Asset(
        asset_id="aid_wh_01",
        asset_name="Demo Aid Warehouse",
        asset_type="aid_warehouse_cluster",
        region="Baghdad",
        latitude=33.34,
        longitude=44.36,
    )

    assert asset.asset_type == "aid_warehouse_cluster"
