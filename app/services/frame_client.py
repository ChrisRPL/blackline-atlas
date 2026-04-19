from __future__ import annotations

from pathlib import Path
from shutil import copyfile
from typing import Mapping, Protocol

from pydantic import ValidationError

from app.schemas.frame import FrameEnvelope
from app.services.frame_cache import FrameCacheKey, FrameCacheLayout
from app.services.frame_types import FrameRequest
from app.services.scenario_fixtures import ScenarioFixture


class FrameClient(Protocol):
    def get_current_frame(self, request: FrameRequest) -> FrameEnvelope: ...

    def get_baseline_frame(self, request: FrameRequest) -> FrameEnvelope: ...


class FixtureFrameClient:
    def __init__(self, scenarios: Mapping[str, ScenarioFixture]) -> None:
        self._scenarios = dict(scenarios)

    def get_current_frame(self, request: FrameRequest) -> FrameEnvelope:
        return self._scenario(request.scenario_id).current_frame

    def get_baseline_frame(self, request: FrameRequest) -> FrameEnvelope:
        return self._scenario(request.scenario_id).baseline_frame

    def _scenario(self, scenario_id: str) -> ScenarioFixture:
        if scenario_id not in self._scenarios:
            raise KeyError(f"Unknown scenario fixture: {scenario_id}")
        return self._scenarios[scenario_id]


class CachedFrameClient:
    def __init__(self, delegate: FrameClient, cache_layout: FrameCacheLayout) -> None:
        self._delegate = delegate
        self._cache_layout = cache_layout

    def get_current_frame(self, request: FrameRequest) -> FrameEnvelope:
        return self._get_or_cache(
            request=request,
            variant="current",
            loader=self._delegate.get_current_frame,
        )

    def get_baseline_frame(self, request: FrameRequest) -> FrameEnvelope:
        return self._get_or_cache(
            request=request,
            variant="baseline",
            loader=self._delegate.get_baseline_frame,
        )

    def _get_or_cache(
        self,
        *,
        request: FrameRequest,
        variant: str,
        loader,
    ) -> FrameEnvelope:
        frame_id = self._peek_frame_id(request=request, loader=loader)
        cache_key = FrameCacheKey(
            asset_id=request.asset_id,
            scenario_id=request.scenario_id,
            frame_id=frame_id,
            variant=variant,
        )
        metadata_path = self._cache_layout.metadata_path(cache_key)

        if metadata_path.exists():
            try:
                cached = FrameEnvelope.model_validate_json(
                    metadata_path.read_text(encoding="utf-8")
                )
            except ValidationError:
                cached = None
            if cached is not None and self._cached_envelope_usable(cached):
                return cached

        envelope = loader(request)
        materialized = self._materialize_envelope(
            envelope=envelope, request=request, variant=variant
        )
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(materialized.model_dump_json(indent=2), encoding="utf-8")
        return materialized

    def _peek_frame_id(self, *, request: FrameRequest, loader) -> str:
        envelope = loader(request)
        return envelope.frame.frame_id

    def _materialize_envelope(
        self,
        *,
        envelope: FrameEnvelope,
        request: FrameRequest,
        variant: str,
    ) -> FrameEnvelope:
        image_ref = envelope.frame.image_ref
        overlay_ref = envelope.overlay_ref

        cache_key = FrameCacheKey(
            asset_id=request.asset_id,
            scenario_id=request.scenario_id,
            frame_id=envelope.frame.frame_id,
            variant=variant,
        )
        cached_image_ref = None
        if image_ref:
            cached_image_ref = self._materialize_ref(
                source_ref=image_ref,
                target_path=self._cache_layout.image_path(cache_key),
            )

        cached_overlay_ref = None
        if overlay_ref:
            overlay_key = FrameCacheKey(
                asset_id=request.asset_id,
                scenario_id=request.scenario_id,
                frame_id=envelope.frame.frame_id,
                variant="overlay",
            )
            cached_overlay_ref = self._materialize_ref(
                source_ref=overlay_ref,
                target_path=self._cache_layout.image_path(overlay_key),
            )

        return envelope.model_copy(
            update={
                "frame": envelope.frame.model_copy(update={"image_ref": cached_image_ref}),
                "overlay_ref": cached_overlay_ref,
            }
        )

    def _cached_envelope_usable(self, envelope: FrameEnvelope) -> bool:
        refs = [envelope.frame.image_ref, envelope.overlay_ref]
        for ref in refs:
            if not ref:
                continue
            path = Path(ref)
            if not path.exists():
                return False
            if path.is_file() and path.stat().st_size == 0:
                return False
        return True

    def _materialize_ref(self, *, source_ref: str, target_path: Path) -> str:
        source_path = Path(source_ref)
        if not source_path.is_file():
            return source_ref

        suffix = source_path.suffix or target_path.suffix or ".png"
        materialized_path = (
            target_path if target_path.suffix == suffix else target_path.with_suffix(suffix)
        )
        materialized_path.parent.mkdir(parents=True, exist_ok=True)
        copyfile(source_path, materialized_path)
        return str(materialized_path)
