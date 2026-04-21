from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.schemas.lead import Lead

DEFAULT_LEAD_REGISTRY_PATH = Path(__file__).with_name("lead_registry.seed.json")


def load_lead_registry(manifest_path: str | None) -> list[Lead]:
    path = Path(manifest_path) if manifest_path else DEFAULT_LEAD_REGISTRY_PATH

    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
        return [Lead.model_validate(entry) for entry in entries]
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValidationError, TypeError):
        return []
