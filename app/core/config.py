from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def load_local_env(env_path: str = ".env") -> None:
    path = Path(env_path)
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True)
class Settings:
    app_env: str
    app_port: int
    model_version: str
    simsat_current_endpoint: str | None
    simsat_baseline_endpoint: str | None
    mapbox_token_present: bool
    watchlist_path: str | None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_local_env()
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        app_port=int(os.getenv("APP_PORT", "8000")),
        model_version=os.getenv("MODEL_VERSION", "lfm2.5-vl-450m-prompted"),
        simsat_current_endpoint=os.getenv("SIMSAT_CURRENT_ENDPOINT") or None,
        simsat_baseline_endpoint=os.getenv("SIMSAT_BASELINE_ENDPOINT") or None,
        mapbox_token_present=bool(os.getenv("MAPBOX_TOKEN")),
        watchlist_path=os.getenv("WATCHLIST_PATH") or None,
    )
