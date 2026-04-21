from __future__ import annotations

import argparse

from app.services.lead_registry_refresh import refresh_lead_registry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the curated local lead registry seed.")
    parser.add_argument(
        "--source-path",
        default="app/services/lead_sources.seed.json",
        help="Path to the curated lead source JSON file.",
    )
    parser.add_argument(
        "--output-path",
        default="app/services/lead_registry.seed.json",
        help="Path to the refreshed lead registry JSON file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    leads, reachable_count = refresh_lead_registry(
        source_path=args.source_path,
        output_path=args.output_path,
    )
    print(
        f"refreshed {len(leads)} leads from {args.source_path} into {args.output_path} "
        f"({reachable_count} sources reachable)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
