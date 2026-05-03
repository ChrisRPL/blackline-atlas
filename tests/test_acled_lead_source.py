from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

from app.services.acled_lead_source import (
    fetch_acled_conflict_leads,
    request_acled_access_token,
)


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


def test_request_acled_access_token_uses_oauth_password_flow() -> None:
    seen: dict[str, str] = {}

    def opener(request: Request, timeout: float) -> _FakeHTTPResponse:
        assert timeout == 8.0
        seen["url"] = request.full_url
        seen["body"] = request.data.decode("utf-8")
        return _FakeHTTPResponse(body=b'{"access_token":"token-123"}')

    token = request_acled_access_token(
        username="user@example.test",
        password="secret",
        token_url="https://acled.example/oauth/token",
        opener=opener,
    )

    assert token == "token-123"
    assert seen["url"] == "https://acled.example/oauth/token"
    body = parse_qs(seen["body"])
    assert body["username"] == ["user@example.test"]
    assert body["password"] == ["secret"]
    assert body["grant_type"] == ["password"]
    assert body["client_id"] == ["acled"]
    assert body["scope"] == ["authenticated"]


def test_fetch_acled_conflict_leads_maps_rows_to_leads() -> None:
    row = {
        "event_id_cnty": "UKR12345",
        "event_date": "2026-04-28",
        "disorder_type": "Political violence",
        "event_type": "Explosions/Remote violence",
        "sub_event_type": "Shelling/artillery/missile attack",
        "country": "Ukraine",
        "admin1": "Kharkiv",
        "admin2": "Kharkivskyi",
        "location": "Kharkiv",
        "latitude": "49.9935",
        "longitude": "36.2304",
        "geo_precision": "1",
        "source": "Local source",
        "source_scale": "National",
        "notes": "Shelling reported near a hospital district.",
        "fatalities": "2",
        "civilian_targeting": "Civilian targeting",
        "tags": "civilian infrastructure",
        "timestamp": "1777334400",
    }
    seen: dict[str, str] = {}

    def opener(request: Request, timeout: float) -> _FakeHTTPResponse:
        assert timeout == 8.0
        seen["authorization"] = request.headers["Authorization"]
        seen["url"] = request.full_url
        return _FakeHTTPResponse(body=json.dumps({"status": 200, "data": [row]}).encode())

    result = fetch_acled_conflict_leads(
        access_token="token-123",
        api_url="https://acled.example/api/acled/read",
        countries=("Ukraine",),
        event_types=("Explosions/Remote violence",),
        days=7,
        limit=10,
        opener=opener,
    )

    assert seen["authorization"] == "Bearer token-123"
    query = parse_qs(urlparse(seen["url"]).query)
    assert query["_format"] == ["json"]
    assert query["country"] == ["Ukraine"]
    assert query["event_type"] == ["Explosions/Remote violence"]
    assert query["event_date_where"] == ["BETWEEN"]
    assert query["limit"] == ["10"]
    assert result.fetched_event_count == 1
    assert len(result.leads) == 1
    lead = result.leads[0]
    assert lead.lead_id.startswith("acled_UKR12345_")
    assert lead.title == "Kharkiv Shelling/artillery/missile attack"
    assert lead.region == "Kharkiv, Kharkivskyi, Kharkiv, Ukraine"
    assert lead.latitude == 49.9935
    assert lead.longitude == 36.2304
    assert lead.category_guess == "medical_aid_node"
    assert "Civilian targeting flagged" in (lead.summary or "")
