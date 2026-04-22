from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts import capture_simsat_manifest  # noqa: E402


class _FakeResponse:
    def __init__(self, *, body: bytes, metadata: dict[str, object], status: int = 200) -> None:
        self._body = body
        self._status = status
        self.headers = {"sentinel_metadata": json.dumps(metadata)}

    @property
    def status(self) -> int:
        return self._status

    def getcode(self) -> int:
        return self._status

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_write_simsat_capture_manifest_materializes_case_pair(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []

    def fake_urlopen(url: str, timeout: float):
        calls.append(url)
        if "timestamp=2026-04-14T18%3A40%3A00Z" in url:
            return _FakeResponse(
                body=b"current-png",
                metadata={
                    "image_available": True,
                    "source": "sentinel-2a",
                    "spectral_bands": ["red", "green", "blue"],
                    "footprint": [30.70, 46.48, 30.79, 46.52],
                    "size_km": 5.0,
                    "cloud_cover": 7.0,
                    "datetime": "2026-04-13T08:10:00Z",
                },
            )
        return _FakeResponse(
            body=b"",
            metadata={
                "image_available": False,
                "source": None,
                "spectral_bands": ["red", "green", "blue"],
                "footprint": [30.70, 46.48, 30.79, 46.52],
                "size_km": 5.0,
                "cloud_cover": None,
                "datetime": None,
            },
        )

    monkeypatch.setattr(capture_simsat_manifest, "urlopen", fake_urlopen)

    manifest_path, dataset_path = capture_simsat_manifest.write_simsat_capture_manifest(
        "https://simsat.test/data/image/sentinel",
        tmp_path,
        scenario_ids=("hero_port_disruption",),
    )

    assert manifest_path.exists()
    assert dataset_path.exists()
    assert len(calls) == 2

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["pack_version"] == "simsat-capture-v1"
    assert manifest["case_count"] == 1
    record = manifest["cases"][0]
    assert record["asset"]["asset_id"] == "demo_port_01"
    assert record["current"]["response_metadata"]["image_available"] is True
    assert Path(record["current"]["image_path"]).exists()
    assert Path(record["current"]["metadata_path"]).exists()
    assert record["baseline"]["response_metadata"]["image_available"] is False
    assert record["baseline"]["image_path"] is None
    assert Path(record["baseline"]["metadata_path"]).exists()
    assert "spectral_bands=red" in record["current"]["request_url"]
    assert "return_type=png" in record["current"]["request_url"]


def test_write_simsat_capture_manifest_survives_timeout(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []

    def fake_urlopen(url: str, timeout: float):
        calls.append(url)
        if len(calls) == 1:
            raise TimeoutError("timed out")
        return _FakeResponse(
            body=b"baseline-png",
            metadata={
                "image_available": True,
                "source": "sentinel-2a",
                "spectral_bands": ["red", "green", "blue"],
                "footprint": [30.70, 46.48, 30.79, 46.52],
                "size_km": 5.0,
                "cloud_cover": 3.0,
                "datetime": "2026-04-12T08:10:00Z",
            },
        )

    monkeypatch.setattr(capture_simsat_manifest, "urlopen", fake_urlopen)

    manifest_path, _ = capture_simsat_manifest.write_simsat_capture_manifest(
        "https://simsat.test/data/image/sentinel",
        tmp_path,
        scenario_ids=("hero_port_disruption",),
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = manifest["cases"][0]
    assert record["current"]["response_metadata"]["image_available"] is False
    assert record["current"]["image_path"] is None
    assert record["current"]["response_metadata"]["timestamp"] == "2026-04-14T18:40:00Z"
    assert record["baseline"]["response_metadata"]["image_available"] is True


def test_capture_main_requires_historical_endpoint(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SIMSAT_BASELINE_ENDPOINT", raising=False)
    capture_simsat_manifest.get_settings.cache_clear()

    try:
        capture_simsat_manifest.main([])
    except SystemExit as exc:
        assert "Missing SimSat Sentinel historical endpoint" in str(exc)
    else:
        raise AssertionError("Expected SystemExit when no historical endpoint is provided")


def test_write_simsat_capture_manifest_supports_external_cases_dataset(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_urlopen(url: str, timeout: float):
        _ = timeout
        return _FakeResponse(
            body=b"png",
            metadata={
                "image_available": True,
                "source": "sentinel-2c",
                "spectral_bands": ["red", "green", "blue"],
                "footprint": [35.50, 33.88, 35.54, 33.92],
                "size_km": 5.0,
                "cloud_cover": 0.12,
                "datetime": "2020-08-03T08:30:51Z",
            },
        )

    monkeypatch.setattr(capture_simsat_manifest, "urlopen", fake_urlopen)
    dataset_path = tmp_path / "non_demo_eval.jsonl"
    dataset_path.write_text(
        json.dumps(
            {
                "case_id": "beirut_port_blast",
                "asset": {
                    "asset_id": "beirut_port_01",
                    "asset_name": "Port of Beirut Grain Terminal",
                    "asset_type": "grain_port",
                    "region": "Beirut",
                    "latitude": 33.901,
                    "longitude": 35.52,
                    "hero": False,
                },
                "hero": False,
                "current_frame": {
                    "frame": {
                        "frame_id": "cur_beirut_port_01_20200805",
                        "asset_id": "beirut_port_01",
                        "captured_at": "2020-08-05T10:00:00Z",
                        "image_ref": "pending://beirut/current.png",
                        "cloud_cover": 0.12,
                        "source": "seed",
                    },
                    "baseline_frame_id": "base_beirut_port_01_20200725",
                },
                "baseline_frame": {
                    "frame": {
                        "frame_id": "base_beirut_port_01_20200725",
                        "asset_id": "beirut_port_01",
                        "captured_at": "2020-07-25T10:00:00Z",
                        "image_ref": "pending://beirut/baseline.png",
                        "cloud_cover": 0.44,
                        "source": "seed",
                    }
                },
                "model_output_text": (
                    '{"event_type":"probable_large_scale_disruption","severity":"high",'
                    '"confidence":0.93,"bbox":[0.52,0.17,0.88,0.69],'
                    '"civilian_impact":"shipping_or_aid_disruption",'
                    '"why":"Large blast damage footprint.","action":"downlink_now"}'
                ),
                "expected_candidate": {
                    "event_type": "probable_large_scale_disruption",
                    "severity": "high",
                    "confidence": 0.93,
                    "bbox": [0.52, 0.17, 0.88, 0.69],
                    "civilian_impact": "shipping_or_aid_disruption",
                    "why": "Large blast damage footprint.",
                    "action": "downlink_now",
                },
                "expected_alert": {
                    "alert_id": "blk_nd_00001",
                    "timestamp": "2020-08-05T10:00:00Z",
                    "asset_id": "beirut_port_01",
                    "asset_name": "Port of Beirut Grain Terminal",
                    "asset_type": "grain_port",
                    "event_type": "probable_large_scale_disruption",
                    "severity": "high",
                    "confidence": 0.93,
                    "bbox": [0.52, 0.17, 0.88, 0.69],
                    "civilian_impact": "shipping_or_aid_disruption",
                    "why": "Large blast damage footprint.",
                    "action": "downlink_now",
                    "source": {
                        "current_frame_id": "cur_beirut_port_01_20200805",
                        "baseline_frame_id": "base_beirut_port_01_20200725",
                        "model_version": "lfm2.5-vl-450m-prompted",
                    },
                    "mapbox_context_ref": None,
                },
                "expected_action": "downlink_now",
                "expected_metrics": {
                    "frames_scanned": 72,
                    "alerts_emitted": 1,
                    "raw_frames_suppressed": 67,
                    "downlink_rate": 0.031,
                },
                "split": "train",
                "annotation_source": "manual_public_satellite_event",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    manifest_path, _ = capture_simsat_manifest.write_simsat_capture_manifest(
        "https://simsat.test/data/image/sentinel",
        tmp_path / "captures",
        cases_dataset_path=dataset_path,
        scenario_ids=(),
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["case_count"] == 1
    assert manifest["cases"][0]["case_id"] == "beirut_port_blast"


def test_write_simsat_capture_manifest_uses_all_external_cases_by_default(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_urlopen(url: str, timeout: float):
        _ = url, timeout
        return _FakeResponse(
            body=b"png",
            metadata={
                "image_available": True,
                "source": "sentinel-2c",
                "spectral_bands": ["red", "green", "blue"],
                "footprint": [35.50, 33.88, 35.54, 33.92],
                "size_km": 5.0,
                "cloud_cover": 0.12,
                "datetime": "2020-08-03T08:30:51Z",
            },
        )

    monkeypatch.setattr(capture_simsat_manifest, "urlopen", fake_urlopen)
    dataset_path = tmp_path / "train_01.jsonl"
    rows = [
        {
            "case_id": "train_case_a",
            "asset": {
                "asset_id": "asset_a",
                "asset_name": "Asset A",
                "asset_type": "bridge",
                "region": "Test",
                "latitude": 1.0,
                "longitude": 2.0,
                "hero": False,
            },
            "hero": False,
            "current_frame": {
                "frame": {
                    "frame_id": "cur_a",
                    "asset_id": "asset_a",
                    "captured_at": "2020-08-05T10:00:00Z",
                    "image_ref": "pending://a/current.png",
                    "cloud_cover": 0.12,
                    "source": "seed",
                },
                "baseline_frame_id": "base_a",
            },
            "baseline_frame": {
                "frame": {
                    "frame_id": "base_a",
                    "asset_id": "asset_a",
                    "captured_at": "2020-07-25T10:00:00Z",
                    "image_ref": "pending://a/baseline.png",
                    "cloud_cover": 0.44,
                    "source": "seed",
                }
            },
            "model_output_text": (
                '{"event_type":"probable_access_obstruction","severity":"high",'
                '"confidence":0.9,"bbox":[0.1,0.1,0.9,0.9],'
                '"civilian_impact":"public_mobility_disruption",'
                '"why":"Broken span.","action":"downlink_now"}'
            ),
            "expected_candidate": {
                "event_type": "probable_access_obstruction",
                "severity": "high",
                "confidence": 0.9,
                "bbox": [0.1, 0.1, 0.9, 0.9],
                "civilian_impact": "public_mobility_disruption",
                "why": "Broken span.",
                "action": "downlink_now",
            },
            "expected_alert": {
                "alert_id": "blk_a",
                "timestamp": "2020-08-05T10:00:00Z",
                "asset_id": "asset_a",
                "asset_name": "Asset A",
                "asset_type": "bridge",
                "event_type": "probable_access_obstruction",
                "severity": "high",
                "confidence": 0.9,
                "bbox": [0.1, 0.1, 0.9, 0.9],
                "civilian_impact": "public_mobility_disruption",
                "why": "Broken span.",
                "action": "downlink_now",
                "source": {
                    "current_frame_id": "cur_a",
                    "baseline_frame_id": "base_a",
                    "model_version": "lfm2.5-vl-450m-prompted",
                },
                "mapbox_context_ref": None,
            },
            "expected_action": "downlink_now",
            "expected_metrics": {
                "frames_scanned": 12,
                "alerts_emitted": 1,
                "raw_frames_suppressed": 11,
                "downlink_rate": 0.08,
            },
            "split": "train",
            "annotation_source": "manual",
        },
        {
            "case_id": "train_case_b",
            "asset": {
                "asset_id": "asset_b",
                "asset_name": "Asset B",
                "asset_type": "container_port",
                "region": "Test",
                "latitude": 3.0,
                "longitude": 4.0,
                "hero": False,
            },
            "hero": False,
            "current_frame": {
                "frame": {
                    "frame_id": "cur_b",
                    "asset_id": "asset_b",
                    "captured_at": "2020-08-06T10:00:00Z",
                    "image_ref": "pending://b/current.png",
                    "cloud_cover": 0.22,
                    "source": "seed",
                },
                "baseline_frame_id": "base_b",
            },
            "baseline_frame": {
                "frame": {
                    "frame_id": "base_b",
                    "asset_id": "asset_b",
                    "captured_at": "2020-07-26T10:00:00Z",
                    "image_ref": "pending://b/baseline.png",
                    "cloud_cover": 0.54,
                    "source": "seed",
                }
            },
            "model_output_text": (
                '{"event_type":"probable_large_scale_disruption","severity":"high",'
                '"confidence":0.92,"bbox":[0.2,0.2,0.8,0.8],'
                '"civilian_impact":"shipping_or_aid_disruption",'
                '"why":"Blast scar.","action":"downlink_now"}'
            ),
            "expected_candidate": {
                "event_type": "probable_large_scale_disruption",
                "severity": "high",
                "confidence": 0.92,
                "bbox": [0.2, 0.2, 0.8, 0.8],
                "civilian_impact": "shipping_or_aid_disruption",
                "why": "Blast scar.",
                "action": "downlink_now",
            },
            "expected_alert": {
                "alert_id": "blk_b",
                "timestamp": "2020-08-06T10:00:00Z",
                "asset_id": "asset_b",
                "asset_name": "Asset B",
                "asset_type": "container_port",
                "event_type": "probable_large_scale_disruption",
                "severity": "high",
                "confidence": 0.92,
                "bbox": [0.2, 0.2, 0.8, 0.8],
                "civilian_impact": "shipping_or_aid_disruption",
                "why": "Blast scar.",
                "action": "downlink_now",
                "source": {
                    "current_frame_id": "cur_b",
                    "baseline_frame_id": "base_b",
                    "model_version": "lfm2.5-vl-450m-prompted",
                },
                "mapbox_context_ref": None,
            },
            "expected_action": "downlink_now",
            "expected_metrics": {
                "frames_scanned": 14,
                "alerts_emitted": 1,
                "raw_frames_suppressed": 13,
                "downlink_rate": 0.07,
            },
            "split": "train",
            "annotation_source": "manual",
        },
    ]
    dataset_path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    manifest_path, _ = capture_simsat_manifest.write_simsat_capture_manifest(
        "https://simsat.test/data/image/sentinel",
        tmp_path / "captures",
        cases_dataset_path=dataset_path,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["case_count"] == 2
    assert {case["case_id"] for case in manifest["cases"]} == {"train_case_a", "train_case_b"}


def test_write_simsat_capture_manifest_applies_case_capture_override(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[str] = []

    def fake_urlopen(url: str, timeout: float):
        calls.append(url)
        _ = timeout
        return _FakeResponse(
            body=b"png",
            metadata={
                "image_available": True,
                "source": "sentinel-2c",
                "spectral_bands": ["red", "green", "blue"],
                "footprint": [30.84, 50.52, 30.86, 50.54],
                "size_km": 0.5,
                "cloud_cover": 0.05,
                "datetime": "2022-03-23T09:06:23Z",
            },
        )

    monkeypatch.setattr(capture_simsat_manifest, "urlopen", fake_urlopen)
    dataset_path = tmp_path / "non_demo_eval.jsonl"
    dataset_path.write_text(
        json.dumps(
            {
                "case_id": "silpo_kvitneve_distribution_center_strike",
                "asset": {
                    "asset_id": "silpo_kvitneve_01",
                    "asset_name": "Silpo Kvitneve Distribution Center",
                    "asset_type": "logistics_hub",
                    "region": "Kvitneve, Kyiv Oblast",
                    "latitude": 50.529365,
                    "longitude": 30.852823,
                    "hero": False,
                },
                "hero": False,
                "current_frame": {
                    "frame": {
                        "frame_id": "cur_silpo_kvitneve_01_20220323",
                        "asset_id": "silpo_kvitneve_01",
                        "captured_at": "2022-03-23T09:06:23Z",
                        "image_ref": "pending://silpo_kvitneve_01/current.png",
                        "cloud_cover": 0.054423,
                        "source": "seed",
                    },
                    "baseline_frame_id": "base_silpo_kvitneve_01_20220226",
                },
                "baseline_frame": {
                    "frame": {
                        "frame_id": "base_silpo_kvitneve_01_20220226",
                        "asset_id": "silpo_kvitneve_01",
                        "captured_at": "2022-02-26T09:06:28Z",
                        "image_ref": "pending://silpo_kvitneve_01/baseline.png",
                        "cloud_cover": 17.070061,
                        "source": "seed",
                    }
                },
                "model_output_text": (
                    '{"event_type":"probable_large_scale_disruption","severity":"high",'
                    '"confidence":0.84,"bbox":[0.1,0.16,0.83,0.84],'
                    '"civilian_impact":"trade_disruption",'
                    '"why":"Warehouse-scale darkening and damage.",'
                    '"action":"downlink_now"}'
                ),
                "expected_candidate": {
                    "event_type": "probable_large_scale_disruption",
                    "severity": "high",
                    "confidence": 0.84,
                    "bbox": [0.1, 0.16, 0.83, 0.84],
                    "civilian_impact": "trade_disruption",
                    "why": "Warehouse-scale darkening and damage.",
                    "action": "downlink_now",
                },
                "expected_alert": {
                    "alert_id": "blk_nd_00010",
                    "timestamp": "2022-03-23T09:06:23Z",
                    "asset_id": "silpo_kvitneve_01",
                    "asset_name": "Silpo Kvitneve Distribution Center",
                    "asset_type": "logistics_hub",
                    "event_type": "probable_large_scale_disruption",
                    "severity": "high",
                    "confidence": 0.84,
                    "bbox": [0.1, 0.16, 0.83, 0.84],
                    "civilian_impact": "trade_disruption",
                    "why": "Warehouse-scale darkening and damage.",
                    "action": "downlink_now",
                    "source": {
                        "current_frame_id": "cur_silpo_kvitneve_01_20220323",
                        "baseline_frame_id": "base_silpo_kvitneve_01_20220226",
                        "model_version": "lfm2.5-vl-450m-prompted",
                    },
                    "mapbox_context_ref": None,
                },
                "expected_action": "downlink_now",
                "expected_metrics": {
                    "frames_scanned": 70,
                    "alerts_emitted": 1,
                    "raw_frames_suppressed": 66,
                    "downlink_rate": 0.029,
                },
                "split": "holdout_geo",
                "annotation_source": "manual_public_satellite_event",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    overrides_path = tmp_path / "capture_overrides.json"
    overrides_path.write_text(
        json.dumps(
            {
                "silpo_kvitneve_distribution_center_strike": {
                    "latitude": 50.528965,
                    "longitude": 30.849714,
                    "size_km": 0.5,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

    manifest_path, _ = capture_simsat_manifest.write_simsat_capture_manifest(
        "https://simsat.test/data/image/sentinel",
        tmp_path / "captures",
        cases_dataset_path=dataset_path,
        capture_overrides_path=overrides_path,
        scenario_ids=(),
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = manifest["cases"][0]
    assert "lat=50.528965" in calls[0]
    assert "lon=30.849714" in calls[0]
    assert "size_km=0.5" in calls[0]
    assert record["current"]["response_metadata"]["size_km"] == 0.5
