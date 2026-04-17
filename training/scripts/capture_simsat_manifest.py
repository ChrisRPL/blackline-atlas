from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.schemas.annotated_case import AnnotatedCaseRecord  # noqa: E402
from app.schemas.simsat_capture import (  # noqa: E402
    SimSatCaptureFrame,
    SimSatCaptureRecord,
    SimSatSentinelMetadata,
)
from app.services.scenario_fixtures import build_stub_scenarios  # noqa: E402
from app.services.watchlist_loader import load_watchlist_assets  # noqa: E402
from training.scripts.build_dataset import SCENARIO_ORDER  # noqa: E402

PACK_VERSION = "simsat-capture-v1"
DEFAULT_OUTPUT_DIR = ROOT / "training" / "replay_pack" / "simsat_capture"
DEFAULT_MANIFEST_NAME = "simsat_capture_manifest.json"
DEFAULT_DATASET_NAME = "simsat_capture_manifest.jsonl"
DEFAULT_SPECTRAL_BANDS = ("red", "green", "blue")
DEFAULT_SIZE_KM = 5.0
DEFAULT_WINDOW_SECONDS = 10 * 24 * 60 * 60
DEFAULT_TIMEOUT_SECONDS = 20.0


def build_simsat_capture_manifest(
    *,
    historical_endpoint: str,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    cases_dataset_path: Path | None = None,
    spectral_bands: tuple[str, ...] = DEFAULT_SPECTRAL_BANDS,
    size_km: float = DEFAULT_SIZE_KM,
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    scenario_ids: tuple[str, ...] = SCENARIO_ORDER,
) -> list[dict[str, object]]:
    cases = _load_capture_cases(
        cases_dataset_path=cases_dataset_path,
        scenario_ids=scenario_ids,
    )

    records: list[dict[str, object]] = []
    for case in cases:
        case_dir = output_dir / case.case_id

        current = _capture_frame(
            endpoint=historical_endpoint,
            output_dir=case_dir,
            variant="current",
            frame_id=case.current_frame.frame.frame_id,
            lon=case.asset.longitude,
            lat=case.asset.latitude,
            requested_timestamp=case.current_frame.frame.captured_at,
            spectral_bands=spectral_bands,
            size_km=size_km,
            window_seconds=window_seconds,
            timeout_seconds=timeout_seconds,
        )
        baseline = _capture_frame(
            endpoint=historical_endpoint,
            output_dir=case_dir,
            variant="baseline",
            frame_id=case.baseline_frame.frame.frame_id,
            lon=case.asset.longitude,
            lat=case.asset.latitude,
            requested_timestamp=case.baseline_frame.frame.captured_at,
            spectral_bands=spectral_bands,
            size_km=size_km,
            window_seconds=window_seconds,
            timeout_seconds=timeout_seconds,
        )

        record = SimSatCaptureRecord(
            case_id=case.case_id,
            pack_version=PACK_VERSION,
            asset=case.asset,
            current=current,
            baseline=baseline,
        )
        records.append(record.model_dump(mode="json"))

    return records


def write_simsat_capture_manifest(
    historical_endpoint: str,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    manifest_name: str = DEFAULT_MANIFEST_NAME,
    dataset_name: str = DEFAULT_DATASET_NAME,
    cases_dataset_path: Path | None = None,
    spectral_bands: tuple[str, ...] = DEFAULT_SPECTRAL_BANDS,
    size_km: float = DEFAULT_SIZE_KM,
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    scenario_ids: tuple[str, ...] = SCENARIO_ORDER,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    records = build_simsat_capture_manifest(
        historical_endpoint=historical_endpoint,
        output_dir=output_dir,
        cases_dataset_path=cases_dataset_path,
        spectral_bands=spectral_bands,
        size_km=size_km,
        window_seconds=window_seconds,
        timeout_seconds=timeout_seconds,
        scenario_ids=scenario_ids,
    )
    manifest = {
        "pack_version": PACK_VERSION,
        "case_count": len(records),
        "cases": records,
    }

    manifest_path = output_dir / manifest_name
    dataset_path = output_dir / dataset_name
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    dataset_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    return manifest_path, dataset_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description="Freeze one current/baseline SimSat Sentinel pair per replay case.",
    )
    parser.add_argument(
        "--historical-endpoint",
        default=settings.simsat_baseline_endpoint,
        help=(
            "SimSat Sentinel historical endpoint, typically /data/image/sentinel. "
            "Defaults to SIMSAT_BASELINE_ENDPOINT if set."
        ),
    )
    parser.add_argument(
        "--cases-dataset",
        type=Path,
        default=None,
        help=(
            "Annotated case JSON/JSONL to capture instead of the built-in replay pack. "
            "Useful for non-demo AOIs."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for captured pairs. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--manifest-name",
        default=DEFAULT_MANIFEST_NAME,
        help=f"Manifest filename. Default: {DEFAULT_MANIFEST_NAME}",
    )
    parser.add_argument(
        "--dataset-name",
        default=DEFAULT_DATASET_NAME,
        help=f"JSONL filename. Default: {DEFAULT_DATASET_NAME}",
    )
    parser.add_argument(
        "--spectral-band",
        action="append",
        dest="spectral_bands",
        default=list(DEFAULT_SPECTRAL_BANDS),
        help="Sentinel spectral band to request. Repeat for multiple bands.",
    )
    parser.add_argument(
        "--size-km",
        type=float,
        default=DEFAULT_SIZE_KM,
        help=f"Requested image size in km. Default: {DEFAULT_SIZE_KM}",
    )
    parser.add_argument(
        "--window-seconds",
        type=float,
        default=DEFAULT_WINDOW_SECONDS,
        help=f"Historical search window in seconds. Default: {DEFAULT_WINDOW_SECONDS}",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"HTTP timeout in seconds. Default: {DEFAULT_TIMEOUT_SECONDS}",
    )
    parser.add_argument(
        "--scenario-id",
        action="append",
        dest="scenario_ids",
        default=None,
        help="Replay scenario id to capture. Repeat to limit export.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.historical_endpoint:
        raise SystemExit(
            "Missing SimSat Sentinel historical endpoint. "
            "Pass --historical-endpoint or set SIMSAT_BASELINE_ENDPOINT."
        )
    scenario_ids = (
        tuple(args.scenario_ids)
        if args.scenario_ids
        else (() if args.cases_dataset is not None else SCENARIO_ORDER)
    )
    manifest_path, dataset_path = write_simsat_capture_manifest(
        args.historical_endpoint,
        args.output_dir,
        manifest_name=args.manifest_name,
        dataset_name=args.dataset_name,
        cases_dataset_path=args.cases_dataset,
        spectral_bands=tuple(args.spectral_bands),
        size_km=args.size_km,
        window_seconds=args.window_seconds,
        timeout_seconds=args.timeout_seconds,
        scenario_ids=scenario_ids,
    )
    print(f"wrote {manifest_path}")
    print(f"wrote {dataset_path}")
    return 0


def _capture_frame(
    *,
    endpoint: str,
    output_dir: Path,
    variant: str,
    frame_id: str,
    lon: float,
    lat: float,
    requested_timestamp: str,
    spectral_bands: tuple[str, ...],
    size_km: float,
    window_seconds: float,
    timeout_seconds: float,
) -> SimSatCaptureFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    request_url = _build_request_url(
        endpoint=endpoint,
        lon=lon,
        lat=lat,
        requested_timestamp=requested_timestamp,
        spectral_bands=spectral_bands,
        size_km=size_km,
        window_seconds=window_seconds,
    )
    with urlopen(request_url, timeout=timeout_seconds) as response:
        status = getattr(response, "status", response.getcode())
        if status != 200:
            raise ValueError(f"SimSat request failed with status {status}: {request_url}")
        metadata_header = response.headers.get("sentinel_metadata")
        if not metadata_header:
            raise ValueError(f"SimSat response missing sentinel_metadata header: {request_url}")
        metadata = SimSatSentinelMetadata.model_validate(json.loads(metadata_header))
        body = response.read()

    metadata_path = output_dir / f"{variant}-metadata.json"
    metadata_path.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")

    image_path = None
    if metadata.image_available and body:
        image_file = output_dir / f"{variant}.png"
        image_file.write_bytes(body)
        image_path = str(image_file)

    return SimSatCaptureFrame(
        frame_id=frame_id,
        requested_timestamp=requested_timestamp,
        request_url=request_url,
        image_path=image_path,
        metadata_path=str(metadata_path),
        response_metadata=metadata,
    )


def _build_request_url(
    *,
    endpoint: str,
    lon: float,
    lat: float,
    requested_timestamp: str,
    spectral_bands: tuple[str, ...],
    size_km: float,
    window_seconds: float,
) -> str:
    params = urlencode(
        {
            "lon": f"{lon:.6f}",
            "lat": f"{lat:.6f}",
            "timestamp": requested_timestamp,
            "spectral_bands": list(spectral_bands),
            "size_km": size_km,
            "window_seconds": window_seconds,
            "return_type": "png",
        },
        doseq=True,
    )
    return f"{endpoint}?{params}"


def _load_capture_cases(
    *,
    cases_dataset_path: Path | None,
    scenario_ids: tuple[str, ...],
) -> list[AnnotatedCaseRecord]:
    if cases_dataset_path is None:
        settings = get_settings()
        assets = {asset.asset_id: asset for asset in load_watchlist_assets(settings.watchlist_path)}
        scenarios = build_stub_scenarios(
            settings=settings,
            hero_asset=assets["demo_port_01"],
            bridge_asset=assets["demo_bridge_01"],
        )
        return [
            AnnotatedCaseRecord(
                case_id=scenario_id,
                asset=assets[scenarios[scenario_id].asset_id],
                hero=assets[scenarios[scenario_id].asset_id].hero,
                current_frame=scenarios[scenario_id].current_frame,
                baseline_frame=scenarios[scenario_id].baseline_frame,
                model_output_text=scenarios[scenario_id].model_output_text,
                expected_candidate=json.loads(scenarios[scenario_id].model_output_text),
                expected_alert=scenarios[scenario_id].alerts[0],
                expected_action=scenarios[scenario_id].alerts[0].action,
                expected_metrics=scenarios[scenario_id].metrics,
                split="holdout_geo",
                holdout_reason="hero_demo",
                annotation_source="stub_replay_pack",
            )
            for scenario_id in scenario_ids
        ]

    entries = _load_json_records(cases_dataset_path)
    cases = [AnnotatedCaseRecord.model_validate(entry) for entry in entries]
    if not scenario_ids:
        return cases
    selected = {case.case_id for case in cases if case.case_id in set(scenario_ids)}
    missing = [case_id for case_id in scenario_ids if case_id not in selected]
    if missing:
        raise ValueError(f"missing case_id(s) in {cases_dataset_path}: {', '.join(missing)}")
    return [case for case in cases if case.case_id in selected]


def _load_json_records(path: Path) -> list[dict[str, object]]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in raw.splitlines() if line.strip()]
    payload = json.loads(raw)
    if isinstance(payload, dict) and isinstance(payload.get("cases"), list):
        return list(payload["cases"])
    if isinstance(payload, list):
        return payload
    raise ValueError(f"unsupported record layout in {path}")


if __name__ == "__main__":
    raise SystemExit(main())
