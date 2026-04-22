from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts import probe_exact_site_windows  # noqa: E402


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


def test_build_probe_payload_reads_exact_site_queue(monkeypatch, tmp_path) -> None:
    queue_path = tmp_path / "exact_site_probe_queue.json"
    queue_path.write_text(
        json.dumps(
            [
                {
                    "probe_id": "bahri_water_station_2025_damage_claim",
                    "label": "Khartoum Bahri Water Station",
                    "lead_id": "lead_bahri_water_station_202502",
                    "asset_id": "bahri_water_01",
                    "category": "water_infrastructure",
                    "latitude": 15.6169,
                    "longitude": 32.5347,
                    "size_km": 5.0,
                    "timestamps": [
                        "2025-01-30T08:26:00Z",
                        "2025-02-04T08:26:00Z",
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    def fake_probe_timestamp(**kwargs):
        return {
            "requested_timestamp": kwargs["requested_timestamp"],
            "request_url": "https://simsat.test/example",
            "ok": True,
            "datetime": "2025-02-03T08:26:11Z",
            "cloud_cover": 0.3,
            "image_available": True,
            "source": "sentinel-2a",
            "footprint": [32.5, 15.6, 32.6, 15.7],
        }

    monkeypatch.setattr(probe_exact_site_windows, "probe_timestamp", fake_probe_timestamp)

    payload = probe_exact_site_windows.build_probe_payload(
        historical_endpoint="https://simsat.test/data/image/sentinel",
        queue_path=queue_path,
        probe_ids=("bahri_water_station_2025_damage_claim",),
    )

    assert payload["historical_endpoint"] == "https://simsat.test/data/image/sentinel"
    site = payload["sites"][0]
    assert site["probe_id"] == "bahri_water_station_2025_damage_claim"
    assert site["lead_id"] == "lead_bahri_water_station_202502"
    assert site["asset_id"] == "bahri_water_01"
    assert site["probes"][0]["datetime"] == "2025-02-03T08:26:11Z"


def test_resolve_probe_items_rejects_unknown_probe_id() -> None:
    queue = [
        {
            "probe_id": "known",
            "label": "Known",
            "latitude": 0.0,
            "longitude": 0.0,
            "size_km": 1.0,
            "timestamps": [],
        }
    ]

    try:
        probe_exact_site_windows.resolve_probe_items(queue, ("missing",))
    except ValueError as exc:
        assert "unknown probe id(s): missing" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown probe id")
