from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.schemas.asset import Asset

DEFAULT_WATCHLIST_PATH = Path(__file__).with_name("watchlist.seed.json")


def load_watchlist_assets(manifest_path: str | None) -> list[Asset]:
    path = Path(manifest_path) if manifest_path else DEFAULT_WATCHLIST_PATH

    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
        assets = [Asset.model_validate(entry) for entry in entries]
        if assets and any(asset.hero for asset in assets):
            return assets
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValidationError, TypeError):
        pass

    return _fallback_assets()


def _fallback_assets() -> list[Asset]:
    return [
        Asset(
            asset_id="demo_port_01",
            asset_name="Demo Grain Port",
            asset_type="grain_port",
            region="Black Sea",
            latitude=46.501,
            longitude=30.747,
            hero=True,
        ),
        Asset(
            asset_id="demo_bridge_01",
            asset_name="Demo Logistics Bridge",
            asset_type="bridge",
            region="Lower Danube",
            latitude=45.169,
            longitude=28.801,
        ),
    ]
