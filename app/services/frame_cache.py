from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

FrameVariant = Literal["current", "baseline", "overlay"]

_NON_SLUG = re.compile(r"[^a-zA-Z0-9._-]+")


def slug_token(value: str) -> str:
    normalized = _NON_SLUG.sub("-", value.strip()).strip("-")
    return normalized or "unknown"


@dataclass(frozen=True)
class FrameCacheKey:
    asset_id: str
    scenario_id: str
    frame_id: str
    variant: FrameVariant


@dataclass(frozen=True)
class FrameCacheLayout:
    root: Path

    def __init__(self, root: str | Path = ".cache/frames") -> None:
        object.__setattr__(self, "root", Path(root))

    def scenario_dir(self, *, asset_id: str, scenario_id: str) -> Path:
        return self.root / slug_token(asset_id) / slug_token(scenario_id)

    def frame_dir(self, key: FrameCacheKey) -> Path:
        return (
            self.scenario_dir(asset_id=key.asset_id, scenario_id=key.scenario_id)
            / key.variant
            / slug_token(key.frame_id)
        )

    def image_path(self, key: FrameCacheKey, suffix: str = ".png") -> Path:
        return self.frame_dir(key) / f"image{suffix}"

    def metadata_path(self, key: FrameCacheKey) -> Path:
        return self.frame_dir(key) / "metadata.json"

    def prepare_frame_dir(self, key: FrameCacheKey) -> Path:
        frame_dir = self.frame_dir(key)
        frame_dir.mkdir(parents=True, exist_ok=True)
        return frame_dir
