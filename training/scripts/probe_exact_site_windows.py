from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts.probe_train_family_windows import (  # noqa: E402
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_WINDOW_SECONDS,
    probe_timestamp,
)

DEFAULT_QUEUE_PATH = ROOT / "training" / "replay_pack" / "exact_site_probe_queue.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Probe arbitrary exact civilian-site timestamp queues against the SimSat "
            "historical Sentinel endpoint."
        ),
    )
    parser.add_argument(
        "--historical-endpoint",
        required=True,
        help="SimSat historical Sentinel endpoint, typically /data/image/sentinel.",
    )
    parser.add_argument(
        "--queue-path",
        type=Path,
        default=DEFAULT_QUEUE_PATH,
        help=f"Exact-site probe queue JSON. Default: {DEFAULT_QUEUE_PATH}",
    )
    parser.add_argument(
        "--probe-id",
        action="append",
        dest="probe_ids",
        default=None,
        help="Probe id from the queue. Repeat for multiple.",
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
    payload = build_probe_payload(
        historical_endpoint=args.historical_endpoint,
        queue_path=args.queue_path,
        probe_ids=tuple(args.probe_ids) if args.probe_ids else None,
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


def build_probe_payload(
    *,
    historical_endpoint: str,
    queue_path: Path,
    probe_ids: tuple[str, ...] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
) -> dict[str, object]:
    queue = load_probe_queue(queue_path)
    selected = resolve_probe_items(queue, probe_ids)
    probes_payload: list[dict[str, object]] = []
    for item in selected:
        probes = [
            probe_timestamp(
                historical_endpoint=historical_endpoint,
                latitude=float(item["latitude"]),
                longitude=float(item["longitude"]),
                size_km=float(item["size_km"]),
                requested_timestamp=timestamp,
                timeout_seconds=timeout_seconds,
                window_seconds=window_seconds,
            )
            for timestamp in item["timestamps"]
        ]
        probes_payload.append(
            {
                "probe_id": item["probe_id"],
                "label": item["label"],
                "lead_id": item.get("lead_id"),
                "asset_id": item.get("asset_id"),
                "category": item.get("category"),
                "latitude": item["latitude"],
                "longitude": item["longitude"],
                "size_km": item["size_km"],
                "probes": probes,
            }
        )
    return {
        "historical_endpoint": historical_endpoint,
        "queue_path": str(queue_path),
        "window_seconds": window_seconds,
        "sites": probes_payload,
    }


def load_probe_queue(queue_path: Path) -> list[dict[str, object]]:
    return json.loads(queue_path.read_text(encoding="utf-8"))


def resolve_probe_items(
    queue: list[dict[str, object]],
    probe_ids: tuple[str, ...] | None,
) -> list[dict[str, object]]:
    if not probe_ids:
        return queue
    by_id = {str(item["probe_id"]): item for item in queue}
    missing = [probe_id for probe_id in probe_ids if probe_id not in by_id]
    if missing:
        raise ValueError(
            "unknown probe id(s): " + ", ".join(missing) + f" (known: {', '.join(sorted(by_id))})"
        )
    return [by_id[probe_id] for probe_id in probe_ids]


if __name__ == "__main__":
    raise SystemExit(main())
