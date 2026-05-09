from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

from app.services.gdelt_cloud_lead_source import fetch_gdelt_cloud_conflict_leads


class _FakeHTTPResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = body
        self.status = status

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = exc_type
        _ = exc
        _ = tb

    def read(self) -> bytes:
        return self._body


def test_fetch_gdelt_cloud_conflict_leads_maps_v2_events_to_leads() -> None:
    event = {
        "id": "conflict_9b440c54",
        "url": "https://gdeltcloud.com/story/example",
        "primary_story_url": "https://gdeltcloud.com/story/example-primary",
        "family": "conflict",
        "title": "Israeli strikes in southern Lebanon kill four despite ceasefire",
        "summary": "Generated event summary.",
        "event_date": "2026-04-25",
        "category": "Explosions/Remote violence",
        "subcategory": "Shelling/artillery/missile attack",
        "geo": {
            "country": "Lebanon",
            "region": "Middle East",
            "admin1": "Nabatieh",
            "location": "Kfar Tebnit",
            "latitude": 33.3567,
            "longitude": 35.5797,
        },
        "metrics": {
            "article_count": 12,
            "confidence": 0.91,
            "significance": 0.88,
        },
        "fatalities": 4,
        "top_articles": [{"url": "https://example.test/article"}],
    }
    seen: list[str] = []

    def opener(request: Request, timeout: float) -> _FakeHTTPResponse:
        assert timeout == 8.0
        assert request.headers["Authorization"] == "Bearer gdelt_sk_test"
        seen.append(request.full_url)
        return _FakeHTTPResponse(body=json.dumps({"success": True, "data": [event]}).encode())

    result = fetch_gdelt_cloud_conflict_leads(
        api_key="gdelt_sk_test",
        api_url="https://gdeltcloud.example/api/v2/events",
        countries=("Lebanon",),
        days=7,
        limit=10,
        opener=opener,
    )

    query = parse_qs(urlparse(seen[0]).query)
    assert query["event_family"] == ["conflict"]
    assert query["country"] == ["Lebanon"]
    assert query["sort"] == ["recent"]
    assert query["confidence_profile"] == ["loose"]
    assert result.fetched_event_count == 2
    assert len(result.leads) == 1
    lead = result.leads[0]
    assert lead.lead_id.startswith("gdeltcloud_conflict_9b440c54_")
    assert lead.title == "Israeli strikes in southern Lebanon kill four despite ceasefire"
    assert lead.region == "Kfar Tebnit, Nabatieh, Lebanon, Middle East"
    assert lead.latitude == 33.3567
    assert lead.longitude == 35.5797
    assert lead.source_url == "https://gdeltcloud.com/story/example"
    assert lead.source_date.isoformat() == "2026-04-25"
    assert lead.category_guess == "civilian_building_cluster"
    assert "GDELT Cloud conflict event" in (lead.summary or "")
    assert "Confidence 0.91" in (lead.summary or "")


def test_fetch_gdelt_cloud_conflict_leads_paginates_until_limit() -> None:
    def event(index: int) -> dict[str, object]:
        return {
            "id": f"conflict_{index}",
            "title": f"Conflict event {index}",
            "event_date": "2026-04-25",
            "category": "Battles",
            "geo": {
                "country": "Ukraine",
                "region": "Europe",
                "admin1": "Donetsk",
                "location": f"Point {index}",
                "latitude": 48.0 + index / 100,
                "longitude": 37.0 + index / 100,
            },
            "metrics": {"article_count": 1, "confidence": 0.7, "significance": 0.5},
        }

    seen_cursors: list[str | None] = []

    def opener(request: Request, timeout: float) -> _FakeHTTPResponse:
        query = parse_qs(urlparse(request.full_url).query)
        cursor = query.get("cursor", [None])[0]
        seen_cursors.append(cursor)
        rows = [event(0), event(1)] if cursor is None else [event(2)]
        next_cursor = "2" if cursor is None else None
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "success": True,
                    "data": rows,
                    "pagination": {"limit": 2, "cursor": cursor, "next_cursor": next_cursor},
                }
            ).encode()
        )

    result = fetch_gdelt_cloud_conflict_leads(
        api_key="gdelt_sk_test",
        api_url="https://gdeltcloud.example/api/v2/events",
        days=30,
        limit=3,
        opener=opener,
    )

    assert seen_cursors == [None, "2"]
    assert result.fetched_event_count == 3
    assert len(result.leads) == 3


def test_fetch_gdelt_cloud_conflict_leads_returns_newest_events_first() -> None:
    def event(index: int, event_date: str, significance: float) -> dict[str, object]:
        return {
            "id": f"conflict_recent_{index}",
            "title": f"Conflict event {index}",
            "event_date": event_date,
            "category": "Explosions/Remote violence",
            "geo": {
                "country": "Ukraine",
                "region": "Europe",
                "admin1": "Odesa",
                "location": f"Point {index}",
                "latitude": 46.0 + index / 100,
                "longitude": 30.0 + index / 100,
            },
            "metrics": {"article_count": 1, "confidence": 0.7, "significance": significance},
        }

    def opener(request: Request, timeout: float) -> _FakeHTTPResponse:
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "success": True,
                    "data": [
                        event(1, "2026-04-20", 0.95),
                        event(2, "2026-05-03", 0.55),
                        event(3, "2026-05-01", 0.75),
                    ],
                }
            ).encode()
        )

    result = fetch_gdelt_cloud_conflict_leads(
        api_key="gdelt_sk_test",
        api_url="https://gdeltcloud.example/api/v2/events",
        days=30,
        limit=3,
        opener=opener,
    )

    assert [lead.source_date.isoformat() for lead in result.leads] == [
        "2026-05-03",
        "2026-05-01",
        "2026-04-20",
    ]
