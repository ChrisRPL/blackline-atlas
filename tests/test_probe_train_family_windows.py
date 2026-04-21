from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts import probe_train_family_windows  # noqa: E402


class _FakeResponse:
    def __init__(self, *, metadata: dict[str, object], status: int = 200) -> None:
        self._status = status
        self.headers = {"sentinel_metadata": json.dumps(metadata)}

    @property
    def status(self) -> int:
        return self._status

    def getcode(self) -> int:
        return self._status

    def read(self, amount: int | None = None) -> bytes:
        _ = amount
        return b"png"

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_build_probe_payload_uses_known_family_candidates(monkeypatch) -> None:
    def fake_urlopen(url: str, timeout: float):
        _ = timeout
        if "timestamp=2024-04-15T09%3A06%3A00Z" in url:
            return _FakeResponse(
                metadata={
                    "datetime": "2024-04-13T09:06:26Z",
                    "cloud_cover": 0.1,
                    "image_available": True,
                    "source": "sentinel-2b",
                    "footprint": [30.47, 50.44, 30.49, 50.46],
                }
            )
        return _FakeResponse(
            metadata={
                "datetime": "2024-10-01T09:16:23Z",
                "cloud_cover": 1.2,
                "image_available": True,
                "source": "sentinel-2a",
                "footprint": [30.47, 50.44, 30.49, 50.46],
            }
        )

    monkeypatch.setattr(probe_train_family_windows, "urlopen", fake_urlopen)

    payload = probe_train_family_windows.build_probe_payload(
        historical_endpoint="https://simsat.test/data/image/sentinel",
        family_ids=("okhmatdyt",),
    )

    assert payload["historical_endpoint"] == "https://simsat.test/data/image/sentinel"
    family = payload["families"][0]
    assert family["family_id"] == "okhmatdyt"
    assert family["asset_id"] == "okhmatdyt_hospital_01"
    assert family["size_km"] == 0.5
    assert family["probes"][0]["datetime"] == "2024-04-13T09:06:26Z"
    assert family["probes"][0]["image_available"] is True
    assert family["probes"][-1]["datetime"] == "2024-10-01T09:16:23Z"


def test_probe_timestamp_returns_error_payload_on_connection_failure(monkeypatch) -> None:
    def fake_urlopen(url: str, timeout: float):
        _ = (url, timeout)
        raise probe_train_family_windows.URLError("boom")

    monkeypatch.setattr(probe_train_family_windows, "urlopen", fake_urlopen)

    payload = probe_train_family_windows.probe_timestamp(
        historical_endpoint="https://simsat.test/data/image/sentinel",
        latitude=19.5937,
        longitude=37.236699,
        size_km=5.0,
        requested_timestamp="2025-07-10T08:14:00Z",
        timeout_seconds=20.0,
        window_seconds=14 * 24 * 60 * 60,
    )

    assert payload["requested_timestamp"] == "2025-07-10T08:14:00Z"
    assert payload["ok"] is False
    assert "boom" in payload["error"]


def test_resolve_families_rejects_unknown_family() -> None:
    try:
        probe_train_family_windows.resolve_families(["nope"])
    except ValueError as exc:
        assert "unknown family id(s): nope" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown family")
