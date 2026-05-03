from __future__ import annotations

import hashlib
import json
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
    def __init__(
        self,
        delegate: FrameClient,
        cache_layout: FrameCacheLayout,
        *,
        cache_namespace: str = "default",
    ) -> None:
        self._delegate = delegate
        self._cache_layout = cache_layout
        self._cache_namespace = cache_namespace

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
        cached = self._cached_request_envelope(request=request, variant=variant)
        if cached is not None:
            return cached

        envelope = loader(request)
        frame_id = envelope.frame.frame_id
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
                self._write_request_alias(
                    request=request,
                    variant=variant,
                    metadata_path=metadata_path,
                )
                return cached

        materialized = self._materialize_envelope(
            envelope=envelope, request=request, variant=variant
        )
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(materialized.model_dump_json(indent=2), encoding="utf-8")
        self._write_request_alias(
            request=request,
            variant=variant,
            metadata_path=metadata_path,
        )
        return materialized

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

    def _cached_request_envelope(
        self,
        *,
        request: FrameRequest,
        variant: str,
    ) -> FrameEnvelope | None:
        alias_path = self._request_alias_path(request=request, variant=variant)
        if not alias_path.exists():
            return None
        try:
            payload = json.loads(alias_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        metadata_ref = payload.get("metadata_path")
        if not isinstance(metadata_ref, str):
            return None
        metadata_path = Path(metadata_ref)
        if not metadata_path.is_absolute():
            metadata_path = self._cache_layout.root / metadata_path
        if not metadata_path.exists():
            return None
        try:
            cached = FrameEnvelope.model_validate_json(metadata_path.read_text(encoding="utf-8"))
        except ValidationError:
            return None
        if self._cached_envelope_usable(cached):
            return cached
        return None

    def _write_request_alias(
        self,
        *,
        request: FrameRequest,
        variant: str,
        metadata_path: Path,
    ) -> None:
        alias_path = self._request_alias_path(request=request, variant=variant)
        alias_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            metadata_ref = metadata_path.relative_to(self._cache_layout.root)
        except ValueError:
            metadata_ref = metadata_path
        alias_path.write_text(
            json.dumps({"metadata_path": str(metadata_ref)}, sort_keys=True),
            encoding="utf-8",
        )

    def _request_alias_path(self, *, request: FrameRequest, variant: str) -> Path:
        digest = hashlib.sha256(
            json.dumps(
                {
                    "asset_id": request.asset_id,
                    "baseline_timestamp": request.baseline_timestamp,
                    "cache_namespace": self._cache_namespace,
                    "latitude": request.latitude,
                    "longitude": request.longitude,
                    "requested_timestamp": request.requested_timestamp,
                    "scenario_id": request.scenario_id,
                    "size_km": request.size_km,
                    "spectral_bands": list(request.spectral_bands),
                    "variant": variant,
                    "window_seconds": request.window_seconds,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()[:24]
        return (
            self._cache_layout.scenario_dir(
                asset_id=request.asset_id,
                scenario_id=request.scenario_id,
            )
            / "_requests"
            / variant
            / f"{digest}.json"
        )

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
