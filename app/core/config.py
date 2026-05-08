from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def load_local_env(env_path: str = ".env") -> None:
    if env_flag("BLACKLINE_SKIP_DOTENV"):
        return

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
    mapbox_token: str | None = None
    simsat_required: bool = False
    lead_registry_path: str | None = None
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
    agent_timeout_seconds: float = 3.0
    sam3_model_version: str = "facebook/sam3"
    sam3_endpoint: str | None = None
    sam3_http_enabled: bool = True
    sam3_required: bool = True
    sam3_api_key: str | None = None
    analyst_model_version: str = "LiquidAI/LFM2.5-VL-450M"
    analyst_endpoint: str | None = None
    analyst_http_enabled: bool = False
    analyst_api_key: str | None = None
    analyst_provider: str = "atlas_json_http"
    analyst_timeout_seconds: float = 60.0
    analyst_adapter_ref: str | None = (
        "ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter"
    )
    acled_access_token: str | None = None
    acled_username: str | None = None
    acled_password: str | None = None
    acled_lead_enabled: bool = False
    gdelt_cloud_api_key: str | None = None


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
        simsat_required=env_flag("SIMSAT_REQUIRED"),
        mapbox_token=os.getenv("MAPBOX_TOKEN") or None,
        mapbox_token_present=bool(os.getenv("MAPBOX_TOKEN")),
        watchlist_path=os.getenv("WATCHLIST_PATH") or None,
        lead_registry_path=os.getenv("LEAD_REGISTRY_PATH") or None,
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
        agent_timeout_seconds=float(os.getenv("AGENT_TIMEOUT_SECONDS", "3.0")),
        sam3_model_version=os.getenv("SAM3_MODEL_VERSION", "facebook/sam3"),
        sam3_endpoint=os.getenv("SAM3_ENDPOINT") or None,
        sam3_http_enabled=env_flag("SAM3_HTTP_ENABLED", default=True),
        sam3_required=env_flag("SAM3_REQUIRED", default=True),
        sam3_api_key=os.getenv("SAM3_API_KEY") or None,
        analyst_model_version=os.getenv("ANALYST_MODEL_VERSION", "LiquidAI/LFM2.5-VL-450M"),
        analyst_endpoint=os.getenv("ANALYST_ENDPOINT") or None,
        analyst_http_enabled=env_flag("ANALYST_HTTP_ENABLED"),
        analyst_api_key=os.getenv("ANALYST_API_KEY") or None,
        analyst_provider=os.getenv("ANALYST_PROVIDER", "atlas_json_http"),
        analyst_timeout_seconds=float(os.getenv("ANALYST_TIMEOUT_SECONDS", "60.0")),
        analyst_adapter_ref=os.getenv("ANALYST_ADAPTER_REF")
        or "ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter",
        acled_access_token=os.getenv("ACLED_ACCESS_TOKEN") or None,
        acled_username=os.getenv("ACLED_USERNAME") or None,
        acled_password=os.getenv("ACLED_PASSWORD") or None,
        acled_lead_enabled=env_flag("ACLED_LEAD_ENABLED"),
        gdelt_cloud_api_key=os.getenv("GDELT_API_KEY") or os.getenv("GDELT_CLOUD_API_KEY") or None,
    )
