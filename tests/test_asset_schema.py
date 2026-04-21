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


def test_asset_allows_aid_shelter_campus_type() -> None:
    asset = Asset(
        asset_id="aid_shelter_01",
        asset_name="Demo Aid Shelter Campus",
        asset_type="aid_shelter_campus",
        region="Khan Younis",
        latitude=31.364167,
        longitude=34.295556,
    )

    assert asset.asset_type == "aid_shelter_campus"


def test_asset_allows_civilian_building_cluster_type() -> None:
    asset = Asset(
        asset_id="civilian_cluster_01",
        asset_name="Demo Civilian Building Cluster",
        asset_type="civilian_building_cluster",
        region="xBD AOI",
        latitude=18.0,
        longitude=-72.0,
    )

    assert asset.asset_type == "civilian_building_cluster"


def test_asset_allows_road_access_corridor_type() -> None:
    asset = Asset(
        asset_id="road_corridor_01",
        asset_name="Demo Road Corridor",
        asset_type="road_access_corridor",
        region="SpaceNet8 AOI",
        latitude=29.0,
        longitude=-90.0,
    )

    assert asset.asset_type == "road_access_corridor"


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
