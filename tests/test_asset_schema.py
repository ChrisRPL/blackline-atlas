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


def test_asset_allows_grain_storage_complex_type() -> None:
    asset = Asset(
        asset_id="grain_storage_01",
        asset_name="Demo Grain Silos",
        asset_type="grain_storage_complex",
        region="Gedaref",
        latitude=14.026667,
        longitude=35.365,
    )

    assert asset.asset_type == "grain_storage_complex"


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


def test_asset_allows_medical_aid_node_type() -> None:
    asset = Asset(
        asset_id="medical_aid_01",
        asset_name="Demo Medical Aid Node",
        asset_type="medical_aid_node",
        region="Idlib",
        latitude=35.9,
        longitude=36.6,
    )

    assert asset.asset_type == "medical_aid_node"
