from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_WINDOW_SECONDS = 14 * 24 * 60 * 60
DEFAULT_SPECTRAL_BANDS = ("red", "green", "blue")

TRAIN_FAMILY_CANDIDATES: dict[str, dict[str, object]] = {
    "okhmatdyt": {
        "label": "Okhmatdyt Children's Hospital",
        "asset_id": "okhmatdyt_hospital_01",
        "latitude": 50.451172,
        "longitude": 30.479935,
        "size_km": 0.5,
        "timestamps": (
            "2024-04-15T09:06:00Z",
            "2024-05-15T09:06:00Z",
            "2024-05-30T09:06:00Z",
            "2024-08-15T09:16:00Z",
            "2024-10-01T09:16:00Z",
            "2024-11-01T09:16:00Z",
        ),
    },
    "baltimore": {
        "label": "Francis Scott Key Bridge",
        "asset_id": "baltimore_bridge_01",
        "latitude": 39.218,
        "longitude": -76.531,
        "size_km": 2.0,
        "timestamps": (
            "2023-10-15T16:02:00Z",
            "2023-12-15T16:02:00Z",
            "2024-01-15T16:02:00Z",
            "2024-05-20T16:02:00Z",
            "2024-07-20T16:02:00Z",
            "2024-08-20T16:02:00Z",
        ),
    },
    "port_sudan": {
        "label": "Port Sudan Aid Hub",
        "asset_id": "port_sudan_01",
        "latitude": 19.5937,
        "longitude": 37.236699,
        "size_km": 5.0,
        "timestamps": (
            "2025-02-15T08:14:00Z",
            "2025-03-01T08:14:00Z",
            "2025-06-25T08:14:00Z",
            "2025-07-10T08:14:00Z",
            "2025-08-01T08:14:00Z",
        ),
    },
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Probe candidate timestamp windows for known Train 01 positive families "
            "against the SimSat historical endpoint."
        ),
    )
    parser.add_argument(
        "--historical-endpoint",
        required=True,
        help="SimSat historical Sentinel endpoint, typically /data/image/sentinel.",
    )
    parser.add_argument(
        "--family",
        action="append",
        dest="families",
        default=None,
        help=(
            "Probe family id. Repeat for multiple. "
            f"Known: {', '.join(sorted(TRAIN_FAMILY_CANDIDATES))}"
        ),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"HTTP timeout in seconds. Default: {DEFAULT_TIMEOUT_SECONDS}",
    )
    parser.add_argument(
        "--window-seconds",
        type=float,
        default=DEFAULT_WINDOW_SECONDS,
        help=f"Historical search window in seconds. Default: {DEFAULT_WINDOW_SECONDS}",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Optional JSON output path.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    families = resolve_families(args.families)
    payload = build_probe_payload(
        historical_endpoint=args.historical_endpoint,
        family_ids=families,
        timeout_seconds=args.timeout_seconds,
        window_seconds=args.window_seconds,
    )
    output = json.dumps(payload, indent=2, sort_keys=True)
    if args.output_path is not None:
        args.output_path.parent.mkdir(parents=True, exist_ok=True)
        args.output_path.write_text(output + "\n", encoding="utf-8")
        print(f"wrote {args.output_path}")
    print(output)
    return 0


def resolve_families(families: list[str] | None) -> tuple[str, ...]:
    requested = tuple(families or sorted(TRAIN_FAMILY_CANDIDATES))
    unknown = [family for family in requested if family not in TRAIN_FAMILY_CANDIDATES]
    if unknown:
        raise ValueError(
            "unknown family id(s): "
            + ", ".join(unknown)
            + f" (known: {', '.join(sorted(TRAIN_FAMILY_CANDIDATES))})"
        )
    return requested


def build_probe_payload(
    *,
    historical_endpoint: str,
    family_ids: tuple[str, ...],
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
) -> dict[str, object]:
    families_payload: list[dict[str, object]] = []
    for family_id in family_ids:
        family = TRAIN_FAMILY_CANDIDATES[family_id]
        probes = [
            probe_timestamp(
                historical_endpoint=historical_endpoint,
                latitude=float(family["latitude"]),
                longitude=float(family["longitude"]),
                size_km=float(family["size_km"]),
                requested_timestamp=timestamp,
                timeout_seconds=timeout_seconds,
                window_seconds=window_seconds,
            )
            for timestamp in family["timestamps"]
        ]
        families_payload.append(
            {
                "family_id": family_id,
                "label": family["label"],
                "asset_id": family["asset_id"],
                "latitude": family["latitude"],
                "longitude": family["longitude"],
                "size_km": family["size_km"],
                "probes": probes,
            }
        )
    return {
        "historical_endpoint": historical_endpoint,
        "window_seconds": window_seconds,
        "families": families_payload,
    }


def probe_timestamp(
    *,
    historical_endpoint: str,
    latitude: float,
    longitude: float,
    size_km: float,
    requested_timestamp: str,
    timeout_seconds: float,
    window_seconds: float,
) -> dict[str, object]:
    request_url = build_request_url(
        endpoint=historical_endpoint,
        latitude=latitude,
        longitude=longitude,
        requested_timestamp=requested_timestamp,
        size_km=size_km,
        window_seconds=window_seconds,
    )
    try:
        with urlopen(request_url, timeout=timeout_seconds) as response:
            status = getattr(response, "status", response.getcode())
            metadata = json.loads(response.headers["sentinel_metadata"])
            response.read(1)
    except URLError as exc:
        return {
            "requested_timestamp": requested_timestamp,
            "request_url": request_url,
            "ok": False,
            "error": str(exc),
        }

    return {
        "requested_timestamp": requested_timestamp,
        "request_url": request_url,
        "ok": status == 200,
        "datetime": metadata.get("datetime"),
        "cloud_cover": metadata.get("cloud_cover"),
        "image_available": metadata.get("image_available"),
        "source": metadata.get("source"),
        "footprint": metadata.get("footprint"),
    }


def build_request_url(
    *,
    endpoint: str,
    latitude: float,
    longitude: float,
    requested_timestamp: str,
    size_km: float,
    window_seconds: float,
) -> str:
    params = urlencode(
        {
            "lon": f"{longitude:.6f}",
            "lat": f"{latitude:.6f}",
            "timestamp": requested_timestamp,
            "spectral_bands": list(DEFAULT_SPECTRAL_BANDS),
            "size_km": size_km,
            "window_seconds": window_seconds,
            "return_type": "png",
        },
        doseq=True,
    )
    return f"{endpoint}?{params}"


if __name__ == "__main__":
    raise SystemExit(main())
