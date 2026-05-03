from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path
from urllib.request import Request

from app.services.lead_registry_loader import load_lead_registry
from app.services.lead_registry_refresh import lead_refresh_summary, refresh_lead_registry


class _FakeHTTPResponse:
    def __init__(self, status: int = 200, body: bytes = b"") -> None:
        self.status = status
        self._body = body

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = exc_type
        _ = exc
        _ = tb

    def read(self) -> bytes:
        return self._body


def _request_url(request: Request | str) -> str:
    return request.full_url if isinstance(request, Request) else request


def _gdelt_zip(*rows: list[str]) -> bytes:
    payload = BytesIO()
    with zipfile.ZipFile(payload, mode="w") as archive:
        archive.writestr("20260428120000.export.CSV", "\n".join("\t".join(row) for row in rows))
    return payload.getvalue()


def _gdelt_row(
    *,
    global_event_id: str = "123456789",
    sql_date: str = "20260428",
    event_code: str = "190",
    event_root_code: str = "19",
    action_geo_type: str = "4",
    action_geo_name: str = "Kharkiv, Kharkiv, Ukraine",
    action_geo_country: str = "UP",
    latitude: str = "49.9935",
    longitude: str = "36.2304",
    num_articles: str = "6",
    source_url: str = "https://example.test/kharkiv",
) -> list[str]:
    row = [""] * 61
    row[0] = global_event_id
    row[1] = sql_date
    row[25] = "1"
    row[26] = event_code
    row[28] = event_root_code
    row[33] = num_articles
    row[51] = action_geo_type
    row[52] = action_geo_name
    row[53] = action_geo_country
    row[56] = latitude
    row[57] = longitude
    row[60] = source_url
    return row


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


def test_refresh_lead_registry_dry_run_does_not_rewrite_seed(tmp_path) -> None:
    source_path = tmp_path / "lead_sources.seed.json"
    output_path = tmp_path / "lead_registry.seed.json"
    source_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "lead_port_202604",
                    "title": "Port lead",
                    "region": "Demo",
                    "latitude": 1.0,
                    "longitude": 2.0,
                    "category_guess": "container_port",
                    "status": "lead_only",
                    "source_url": "https://example.test/port",
                    "source_date": "2026-04-20",
                }
            ]
        ),
        encoding="utf-8",
    )
    output_path.write_text("[]\n", encoding="utf-8")

    leads, reachable = refresh_lead_registry(
        source_path=str(source_path),
        output_path=str(output_path),
        dry_run=True,
        opener=lambda request, timeout: _FakeHTTPResponse(),
    )

    assert reachable == 1
    assert len(leads) == 1
    assert output_path.read_text(encoding="utf-8") == "[]\n"


def test_refresh_lead_registry_can_build_live_gdelt_leads(tmp_path) -> None:
    output_path = tmp_path / "live_leads.json"
    export_url = "https://data.gdeltproject.org/gdeltv2/20260428120000.export.CSV.zip"
    lastupdate = f"0 {export_url}\n".encode()
    export_zip = _gdelt_zip(
        _gdelt_row(),
        _gdelt_row(
            global_event_id="222222222",
            action_geo_name="Tennessee, United States",
            action_geo_country="US",
            latitude="35.7449",
            longitude="-86.7489",
            num_articles="50",
            source_url="https://example.test/local-crime",
        ),
        _gdelt_row(
            global_event_id="987654321",
            event_root_code="05",
            action_geo_name="Filtered, Example",
        ),
    )

    def opener(request, timeout):
        url = _request_url(request)
        if url.endswith("lastupdate.txt"):
            return _FakeHTTPResponse(body=lastupdate)
        if url == export_url:
            return _FakeHTTPResponse(body=export_zip)
        return _FakeHTTPResponse(status=404, body=b"")

    leads, fetched = refresh_lead_registry(
        source_path=None,
        output_path=str(output_path),
        source_mode="gdelt",
        gdelt_lastupdate_url="https://data.gdeltproject.org/gdeltv2/lastupdate.txt",
        gdelt_hours=1,
        gdelt_max_files=1,
        opener=opener,
    )

    assert fetched == 1
    assert len(leads) == 1
    assert leads[0].lead_id.startswith("gdelt_123456789_")
    assert leads[0].title == "Kharkiv armed conflict"
    assert leads[0].region == "Kharkiv, Kharkiv, Ukraine"
    assert leads[0].latitude == 49.9935
    assert leads[0].longitude == 36.2304
    assert leads[0].status == "lead_only"
    assert leads[0].category_guess == "civilian_building_cluster"

    refreshed = load_lead_registry(str(output_path))
    assert refreshed[0].source_url == "https://example.test/kharkiv"


def test_refresh_lead_registry_can_build_live_acled_leads(tmp_path) -> None:
    output_path = tmp_path / "live_leads.json"
    acled_row = {
        "event_id_cnty": "PSE555",
        "event_date": "2026-04-28",
        "event_type": "Explosions/Remote violence",
        "sub_event_type": "Air/drone strike",
        "country": "Palestine",
        "admin1": "Gaza Strip",
        "admin2": "Gaza",
        "location": "Gaza",
        "latitude": "31.5017",
        "longitude": "34.4668",
        "geo_precision": "1",
        "source": "ACLED source",
        "notes": "Airstrike reported near a civilian neighborhood.",
        "fatalities": "0",
        "civilian_targeting": "",
        "tags": "civilian infrastructure",
    }

    def opener(request, timeout):
        url = _request_url(request)
        assert timeout == 8.0
        if url == "https://acled.example/oauth/token":
            return _FakeHTTPResponse(body=b'{"access_token":"token-123"}')
        if url.startswith("https://acled.example/api/acled/read?"):
            assert request.headers["Authorization"] == "Bearer token-123"
            return _FakeHTTPResponse(body=json.dumps({"status": 200, "data": [acled_row]}).encode())
        return _FakeHTTPResponse(status=404, body=b"")

    leads, fetched = refresh_lead_registry(
        source_path=None,
        output_path=str(output_path),
        source_mode="acled",
        acled_username="user@example.test",
        acled_password="secret",
        acled_api_url="https://acled.example/api/acled/read",
        acled_token_url="https://acled.example/oauth/token",
        acled_days=14,
        acled_limit=10,
        acled_countries=("Palestine",),
        opener=opener,
    )

    assert fetched == 1
    assert len(leads) == 1
    assert leads[0].lead_id.startswith("acled_PSE555_")
    assert leads[0].title == "Gaza Air/drone strike"
    assert leads[0].region == "Gaza, Gaza, Gaza Strip, Palestine"
    assert leads[0].status == "lead_only"

    refreshed = load_lead_registry(str(output_path))
    assert refreshed[0].lead_id.startswith("acled_PSE555_")


def test_refresh_lead_registry_can_build_live_gdelt_cloud_leads(tmp_path) -> None:
    output_path = tmp_path / "live_leads.json"
    cloud_row = {
        "id": "conflict_abc123",
        "url": "https://gdeltcloud.example/story/abc123",
        "title": "Strike damages infrastructure in Kharkiv",
        "summary": "Generated summary.",
        "event_date": "2026-04-28",
        "category": "Explosions/Remote violence",
        "subcategory": "Shelling/artillery/missile attack",
        "geo": {
            "country": "Ukraine",
            "region": "Europe",
            "admin1": "Kharkiv",
            "location": "Kharkiv",
            "latitude": 49.9935,
            "longitude": 36.2304,
        },
        "metrics": {
            "article_count": 9,
            "confidence": 0.9,
            "significance": 0.8,
        },
        "fatalities": 0,
    }

    def opener(request, timeout):
        url = _request_url(request)
        assert timeout == 8.0
        if url.startswith("https://gdeltcloud.example/api/v2/events?"):
            assert request.headers["Authorization"] == "Bearer gdelt_sk_test"
            return _FakeHTTPResponse(
                body=json.dumps({"success": True, "data": [cloud_row]}).encode()
            )
        return _FakeHTTPResponse(status=404, body=b"")

    leads, fetched = refresh_lead_registry(
        source_path=None,
        output_path=str(output_path),
        source_mode="gdelt_cloud",
        gdelt_cloud_api_key="gdelt_sk_test",
        gdelt_cloud_api_url="https://gdeltcloud.example/api/v2/events",
        gdelt_cloud_days=7,
        gdelt_cloud_limit=10,
        gdelt_cloud_countries=("Ukraine",),
        opener=opener,
    )

    assert fetched == 1
    assert len(leads) == 1
    assert leads[0].lead_id.startswith("gdeltcloud_conflict_abc123_")
    assert leads[0].title == "Strike damages infrastructure in Kharkiv"
    assert leads[0].region == "Kharkiv, Kharkiv, Ukraine, Europe"

    refreshed = load_lead_registry(str(output_path))
    assert refreshed[0].lead_id.startswith("gdeltcloud_conflict_abc123_")


def test_lead_refresh_summary_is_machine_readable(tmp_path: Path) -> None:
    source_path = tmp_path / "lead_sources.seed.json"
    source_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "lead_bridge_202604",
                    "title": "Bridge lead",
                    "region": "Demo",
                    "latitude": 1.0,
                    "longitude": 2.0,
                    "category_guess": "bridge",
                    "status": "reference_event",
                    "source_date": "2026-04-20",
                    "linked_asset_id": "bridge_01",
                }
            ]
        ),
        encoding="utf-8",
    )
    leads, reachable = refresh_lead_registry(
        source_path=str(source_path),
        output_path=str(tmp_path / "out.json"),
        dry_run=True,
    )

    summary = lead_refresh_summary(
        leads=leads,
        reachable_count=reachable,
        output_path=str(tmp_path / "out.json"),
        dry_run=True,
    )

    assert summary["dry_run"] is True
    assert summary["lead_count"] == 1
    assert summary["linked_asset_count"] == 1
    assert summary["status_counts"] == {"reference_event": 1}
