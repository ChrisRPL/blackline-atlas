from __future__ import annotations

import json

from app.services.lead_registry_loader import load_lead_registry
from app.services.lead_registry_refresh import refresh_lead_registry


class _FakeHTTPResponse:
    def __init__(self, status: int = 200) -> None:
        self.status = status

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = exc_type
        _ = exc
        _ = tb


def test_refresh_lead_registry_rewrites_seed_from_curated_sources(tmp_path) -> None:
    source_path = tmp_path / "lead_sources.seed.json"
    output_path = tmp_path / "lead_registry.seed.json"
    source_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "lead_qasmiyeh_bridge_202604",
                    "title": "Qasmiyeh Bridge",
                    "region": "South Lebanon",
                    "latitude": 33.33944,
                    "longitude": 35.25222,
                    "category_guess": "bridge",
                    "status": "lead_only",
                    "source_url": "https://example.test/qasmiyeh",
                    "source_date": "2026-04-16",
                }
            ]
        ),
        encoding="utf-8",
    )
    output_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "lead_qasmiyeh_bridge_202604",
                    "title": "Qasmiyeh Bridge",
                    "region": "South Lebanon",
                    "latitude": 33.33944,
                    "longitude": 35.25222,
                    "category_guess": "bridge",
                    "status": "reference_event",
                    "summary": "Manual upgraded status.",
                    "source_url": "https://example.test/qasmiyeh",
                    "source_date": "2026-04-16",
                    "linked_asset_id": "qasmiyeh_bridge_01",
                    "last_refreshed_at": "2026-04-20T00:00:00Z",
                }
            ]
        ),
        encoding="utf-8",
    )

    leads, reachable = refresh_lead_registry(
        source_path=str(source_path),
        output_path=str(output_path),
        opener=lambda request, timeout: _FakeHTTPResponse(),
    )

    assert reachable == 1
    assert len(leads) == 1
    assert leads[0].status == "reference_event"
    assert leads[0].linked_asset_id == "qasmiyeh_bridge_01"
    assert leads[0].last_refreshed_at is not None

    refreshed = load_lead_registry(str(output_path))
    assert refreshed[0].status == "reference_event"
    assert refreshed[0].linked_asset_id == "qasmiyeh_bridge_01"
