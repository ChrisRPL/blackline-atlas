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
    simsat_current_http_enabled: bool = False
    simsat_baseline_http_enabled: bool = False
    mapbox_context_enabled: bool = True
    model_endpoint: str | None = None
    model_http_enabled: bool = False
    model_api_key: str | None = None
    model_provider: str = "atlas_json_http"
    agent_model_version: str = "lfm2.5-1.2b-instruct"
    agent_endpoint: str | None = None
    agent_http_enabled: bool = False
    agent_api_key: str | None = None
    agent_provider: str = "atlas_json_http"


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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
        simsat_current_http_enabled=env_flag("SIMSAT_CURRENT_HTTP_ENABLED"),
        simsat_baseline_http_enabled=env_flag("SIMSAT_BASELINE_HTTP_ENABLED"),
        mapbox_context_enabled=env_flag("MAPBOX_CONTEXT_ENABLED", default=True),
        model_endpoint=os.getenv("MODEL_ENDPOINT") or None,
        model_http_enabled=env_flag("MODEL_HTTP_ENABLED"),
        model_api_key=os.getenv("MODEL_API_KEY") or None,
        model_provider=os.getenv("MODEL_PROVIDER", "atlas_json_http"),
        agent_model_version=os.getenv("AGENT_MODEL_VERSION", "lfm2.5-1.2b-instruct"),
        agent_endpoint=os.getenv("AGENT_ENDPOINT") or None,
        agent_http_enabled=env_flag("AGENT_HTTP_ENABLED"),
        agent_api_key=os.getenv("AGENT_API_KEY") or None,
        agent_provider=os.getenv("AGENT_PROVIDER", "atlas_json_http"),
    )
