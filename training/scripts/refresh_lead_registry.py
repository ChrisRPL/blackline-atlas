from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from app.schemas.lead import Lead


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize and refresh the local lead registry seed."
    )
    parser.add_argument(
        "--path",
        default="app/services/lead_registry.seed.json",
        help="Path to the lead registry seed JSON file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.path)
    entries = json.loads(path.read_text(encoding="utf-8"))
    refreshed_at = datetime.now(tz=UTC).replace(microsecond=0)
    leads = [
        Lead.model_validate(
            {
                **entry,
                "last_refreshed_at": refreshed_at.isoformat().replace("+00:00", "Z"),
            }
        )
        for entry in entries
    ]
    path.write_text(
        json.dumps(
            [lead.model_dump(mode="json", exclude_none=True) for lead in leads],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"refreshed {len(leads)} leads in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
