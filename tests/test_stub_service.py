from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from urllib.error import URLError

from app.core.config import Settings
from app.schemas.agent import AtlasAgentQueryRequest
from app.schemas.lead import Lead, LeadRefreshRequest
from app.schemas.liquid_analyst import LiquidAnalystReport
from app.schemas.replay import ReplayStartRequest
from app.services.frame_filters import FrameFilterPolicy
from app.services.model_wrapper import PromptedCandidateModel
from app.services.prompt_builder import CandidatePromptBuilder
from app.services.sentinel_client import FixtureSentinelPayloadTransport
from app.services.stub import StubAtlasService


def _png_bytes(kind: str) -> bytes:
    from PIL import Image

    image = Image.new("RGB", (16, 16), "white")
    if kind == "blank":
        for y in range(8):
            for x in range(16):
                image.putpixel((x, y), (0, 0, 0))
    else:
        for y in range(16):
            for x in range(16):
                image.putpixel(
                    (x, y),
                    ((x * 17) % 255, (y * 19) % 255, ((x + y) * 11) % 255),
                )
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_stub_service_reloads_generated_live_lead_cache(tmp_path: Path) -> None:
    lead_registry_path = tmp_path / "live_leads.json"
    lead_registry_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "gdelt_1",
                    "title": "Kharkiv armed conflict",
                    "region": "Kharkiv, Ukraine",
                    "latitude": 49.9935,
                    "longitude": 36.2304,
                    "category_guess": "civilian_building_cluster",
                    "status": "lead_only",
                    "source_date": "2026-04-28",
                }
            ]
        ),
        encoding="utf-8",
    )
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=str(lead_registry_path),
        )
    )

    assert [lead.lead_id for lead in service.list_leads()] == ["gdelt_1"]

    lead_registry_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "gdelt_2",
                    "title": "Gaza disruption lead",
                    "region": "Gaza",
                    "latitude": 31.5017,
                    "longitude": 34.4668,
                    "category_guess": "civilian_building_cluster",
                    "status": "lead_only",
                    "source_date": "2026-04-28",
                }
            ]
        ),
        encoding="utf-8",
    )

    assert [lead.lead_id for lead in service.list_leads()] == ["gdelt_2"]


def test_stub_service_does_not_link_live_lead_to_seeded_evidence_when_simsat_missing(
    tmp_path: Path,
) -> None:
    lead_registry_path = tmp_path / "live_leads.json"
    lead_registry_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "gdelt_kramatorsk",
                    "title": "Russian shelling reported in Kramatorsk",
                    "region": "Kramatorsk, Donetsk, Ukraine",
                    "latitude": 48.7387,
                    "longitude": 37.5848,
                    "category_guess": "water_infrastructure",
                    "status": "lead_only",
                    "source_date": "2026-04-28",
                }
            ]
        ),
        encoding="utf-8",
    )
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=str(lead_registry_path),
        )
    )

    lead = service.list_leads()[0]
    assert lead.linked_asset_id is None

    response = service.run_agent_query(
        AtlasAgentQueryRequest(
            tool="site_compare",
            selected_lead_id=lead.lead_id,
        )
    )

    assert response.tool == "site_compare"
    assert response.status == "no_result"
    assert response.focus_asset_id is None
    assert response.focus_lead_id == lead.lead_id
    assert response.compare is None
    assert response.leads[0].lead_id == lead.lead_id
    assert "not satellite-observable" in response.summary


def test_stub_service_links_only_satellite_observable_live_leads(
    tmp_path: Path,
) -> None:
    lead_registry_path = tmp_path / "live_leads.json"
    lead_registry_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "gdelt_visible_damage",
                    "title": "Drone strike damages port warehouse",
                    "region": "Odesa, Ukraine",
                    "latitude": 46.4825,
                    "longitude": 30.7233,
                    "category_guess": "aid_warehouse_cluster",
                    "status": "lead_only",
                    "summary": (
                        "Visible building damage and fire reported at a civilian logistics site."
                    ),
                    "source_date": "2026-04-30",
                },
                {
                    "lead_id": "gdelt_source_only",
                    "title": "Two people killed during armed clash",
                    "region": "Kramatorsk, Ukraine",
                    "latitude": 48.7387,
                    "longitude": 37.5848,
                    "category_guess": "civilian_building_cluster",
                    "status": "lead_only",
                    "summary": (
                        "Local source reports casualties after a brief clash; "
                        "no infrastructure site is described."
                    ),
                    "source_date": "2026-04-30",
                    "linked_asset_id": "live_gdelt_source_only",
                },
            ]
        ),
        encoding="utf-8",
    )
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="http://simsat/current",
            simsat_baseline_endpoint="http://simsat/baseline",
            simsat_current_http_enabled=True,
            simsat_baseline_http_enabled=True,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=str(lead_registry_path),
        )
    )

    leads = {lead.lead_id: lead for lead in service.list_leads()}

    assert leads["gdelt_visible_damage"].linked_asset_id == "live_gdelt_visible_damage"
    assert leads["gdelt_source_only"].linked_asset_id is None
    assert "live_gdelt_source_only" not in {asset.asset_id for asset in service.list_assets()}

    response = service.run_agent_query(
        AtlasAgentQueryRequest(
            tool="site_compare",
            selected_lead_id="gdelt_source_only",
        )
    )

    assert response.status == "no_result"
    assert response.focus_asset_id is None
    assert response.focus_lead_id == "gdelt_source_only"
    assert "not satellite-observable" in response.summary
    assert response.leads[0].linked_asset_id is None


def test_stub_service_does_not_use_mapbox_as_evidence_when_simsat_pair_is_unresolved(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    lead_registry_path = tmp_path / "live_leads.json"
    lead_registry_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "gdelt_dnipro",
                    "title": "Dnipro strike damages apartment buildings",
                    "region": "Dnipro, Ukraine",
                    "latitude": 48.4647,
                    "longitude": 35.0462,
                    "category_guess": "civilian_building_cluster",
                    "status": "lead_only",
                    "source_date": "2026-04-14",
                }
            ]
        ),
        encoding="utf-8",
    )

    def fake_sentinel_urlopen(url: str, timeout: float):
        _ = url
        _ = timeout
        raise URLError("simsat unavailable")

    requested_mapbox_urls: list[str] = []

    def fake_mapbox_urlopen(url: str, timeout: float):
        requested_mapbox_urls.append(url)
        raise AssertionError("Mapbox must not be fetched as compare evidence")

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_sentinel_urlopen)
    monkeypatch.setattr("app.services.stub.urlopen", fake_mapbox_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="http://localhost:9005/data/current/image/sentinel",
            simsat_baseline_endpoint="http://localhost:9005/data/image/sentinel",
            simsat_current_http_enabled=True,
            simsat_baseline_http_enabled=True,
            mapbox_token_present=True,
            mapbox_token="test-mapbox-token",
            mapbox_context_enabled=True,
            watchlist_path=None,
            lead_registry_path=str(lead_registry_path),
        )
    )

    lead = service.list_leads()[0]
    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", selected_lead_id=lead.lead_id)
    )

    assert response.status == "no_result"
    assert response.compare is None
    assert "No dated Sentinel pair resolved" in response.summary
    assert "visual analysis was not run" in response.summary
    assert response.analyst_report is None
    assert service.get_asset_analyst_report(lead.linked_asset_id or f"live_{lead.lead_id}") is None
    assert service.get_asset_evidence(lead.linked_asset_id or f"live_{lead.lead_id}") is None
    assert requested_mapbox_urls == []


def test_stub_service_search_live_leads_skips_watchlist_evaluation(monkeypatch) -> None:
    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "output_text": json.dumps(
                        {
                            "tool": "search_live_leads",
                            "area": "Red Sea",
                            "category": None,
                            "site_id": None,
                            "alert_id": None,
                        }
                    )
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="https://example.test/sentinel/current/",
            simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
            simsat_current_http_enabled=True,
            simsat_baseline_http_enabled=True,
            mapbox_token_present=False,
            watchlist_path=None,
            agent_endpoint="https://example.test/agent",
            agent_http_enabled=True,
            agent_provider="atlas_json_http",
        )
    )

    def fail_watchlist_evaluation():
        raise AssertionError("search_live_leads must not evaluate replay watchlist frames")

    monkeypatch.setattr(service, "_watchlist_evaluations", fail_watchlist_evaluation)

    response = service.run_agent_query(
        AtlasAgentQueryRequest(
            query="Which active conflict regions near the Red Sea should I inspect first?"
        )
    )

    assert response.tool == "search_live_leads"
    assert response.resolved.area == "Red Sea"
    assert response.compare is None


def test_stub_service_refreshes_live_leads_into_runtime_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_refresh_lead_registry(**kwargs):
        assert kwargs["source_mode"] == "gdelt"
        assert kwargs["output_path"] == "var/live_leads.json"
        assert kwargs["gdelt_hours"] == 72
        assert kwargs["gdelt_limit"] == 500
        assert kwargs["preserve_on_empty"] is True
        return (
            [
                Lead(
                    lead_id="gdelt_live_1",
                    title="Kharkiv armed conflict",
                    region="Kharkiv, Ukraine",
                    latitude=49.9935,
                    longitude=36.2304,
                    category_guess="civilian_building_cluster",
                    status="lead_only",
                    source_date="2026-04-28",
                )
            ],
            2,
        )

    monkeypatch.setattr("app.services.stub.refresh_lead_registry", fake_refresh_lead_registry)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=None,
        )
    )

    response = service.refresh_leads(LeadRefreshRequest(source_mode="gdelt"))

    assert response.output_path == "var/live_leads.json"
    assert response.source_mode == "gdelt"
    assert response.lead_count == 1
    assert response.reachable_source_count == 2
    assert [lead.lead_id for lead in service.list_leads()] == ["gdelt_live_1"]


def test_stub_service_preserves_existing_leads_when_live_refresh_returns_empty(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_refresh_lead_registry(**kwargs):
        assert kwargs["preserve_on_empty"] is True
        return [], 0

    monkeypatch.setattr("app.services.stub.refresh_lead_registry", fake_refresh_lead_registry)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=None,
        )
    )
    before = [lead.lead_id for lead in service.list_leads()]

    response = service.refresh_leads(LeadRefreshRequest(source_mode="gdelt"))

    assert response.lead_count == 0
    assert [lead.lead_id for lead in service.list_leads()] == before


def test_stub_service_auto_refresh_prefers_acled_when_configured(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_refresh_lead_registry(**kwargs):
        assert kwargs["source_mode"] == "acled"
        assert kwargs["acled_access_token"] == "token-123"
        return (
            [
                Lead(
                    lead_id="acled_live_1",
                    title="Gaza Air/drone strike",
                    region="Gaza, Palestine",
                    latitude=31.5017,
                    longitude=34.4668,
                    category_guess="civilian_building_cluster",
                    status="lead_only",
                    source_date="2026-04-28",
                )
            ],
            1,
        )

    monkeypatch.setattr("app.services.stub.refresh_lead_registry", fake_refresh_lead_registry)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=None,
            acled_access_token="token-123",
            acled_lead_enabled=True,
        )
    )

    response = service.refresh_leads(LeadRefreshRequest())

    assert response.source_mode == "acled"
    assert response.lead_count == 1
    assert [lead.lead_id for lead in service.list_leads()] == ["acled_live_1"]


def test_stub_service_auto_refresh_prefers_gdelt_cloud_when_key_configured(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_refresh_lead_registry(**kwargs):
        assert kwargs["source_mode"] == "gdelt_cloud"
        assert kwargs["gdelt_cloud_api_key"] == "gdelt_sk_test"
        return (
            [
                Lead(
                    lead_id="gdeltcloud_live_1",
                    title="Strike damages infrastructure in Kharkiv",
                    region="Kharkiv, Ukraine",
                    latitude=49.9935,
                    longitude=36.2304,
                    category_guess="civilian_building_cluster",
                    status="lead_only",
                    source_date="2026-04-28",
                )
            ],
            1,
        )

    monkeypatch.setattr("app.services.stub.refresh_lead_registry", fake_refresh_lead_registry)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=None,
            gdelt_cloud_api_key="gdelt_sk_test",
        )
    )

    response = service.refresh_leads(LeadRefreshRequest())

    assert response.source_mode == "gdelt_cloud"
    assert response.lead_count == 1
    assert [lead.lead_id for lead in service.list_leads()] == ["gdeltcloud_live_1"]


def test_stub_service_auto_refresh_falls_back_to_gdelt_when_gdelt_cloud_empty(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    seen_modes: list[str] = []

    def fake_refresh_lead_registry(**kwargs):
        seen_modes.append(kwargs["source_mode"])
        if kwargs["source_mode"] == "gdelt_cloud":
            return [], 0
        return (
            [
                Lead(
                    lead_id="gdelt_live_1",
                    title="Kharkiv armed conflict",
                    region="Kharkiv, Ukraine",
                    latitude=49.9935,
                    longitude=36.2304,
                    category_guess="civilian_building_cluster",
                    status="lead_only",
                    source_date="2026-04-28",
                )
            ],
            4,
        )

    monkeypatch.setattr("app.services.stub.refresh_lead_registry", fake_refresh_lead_registry)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=None,
            gdelt_cloud_api_key="gdelt_sk_test",
        )
    )

    response = service.refresh_leads(LeadRefreshRequest())

    assert seen_modes == ["gdelt_cloud", "gdelt"]
    assert response.source_mode == "gdelt"
    assert response.lead_count == 1


def test_stub_service_auto_refresh_falls_back_to_gdelt_when_acled_empty(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    seen_modes: list[str] = []

    def fake_refresh_lead_registry(**kwargs):
        seen_modes.append(kwargs["source_mode"])
        if kwargs["source_mode"] == "acled":
            return [], 0
        return (
            [
                Lead(
                    lead_id="gdelt_live_1",
                    title="Kharkiv armed conflict",
                    region="Kharkiv, Ukraine",
                    latitude=49.9935,
                    longitude=36.2304,
                    category_guess="civilian_building_cluster",
                    status="lead_only",
                    source_date="2026-04-28",
                )
            ],
            4,
        )

    monkeypatch.setattr("app.services.stub.refresh_lead_registry", fake_refresh_lead_registry)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=None,
            acled_access_token="token-123",
            acled_lead_enabled=True,
        )
    )

    response = service.refresh_leads(LeadRefreshRequest())

    assert seen_modes == ["acled", "gdelt"]
    assert response.source_mode == "gdelt"
    assert response.lead_count == 1
    assert [lead.lead_id for lead in service.list_leads()] == ["gdelt_live_1"]


def test_stub_service_auto_refresh_uses_gdelt_when_acled_disabled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    seen_modes: list[str] = []

    def fake_refresh_lead_registry(**kwargs):
        seen_modes.append(kwargs["source_mode"])
        return (
            [
                Lead(
                    lead_id="gdelt_live_1",
                    title="Kharkiv armed conflict",
                    region="Kharkiv, Ukraine",
                    latitude=49.9935,
                    longitude=36.2304,
                    category_guess="civilian_building_cluster",
                    status="lead_only",
                    source_date="2026-04-28",
                )
            ],
            4,
        )

    monkeypatch.setattr("app.services.stub.refresh_lead_registry", fake_refresh_lead_registry)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=None,
            acled_access_token="token-123",
            acled_lead_enabled=False,
        )
    )

    response = service.refresh_leads(LeadRefreshRequest())

    assert seen_modes == ["gdelt"]
    assert response.source_mode == "gdelt"
    assert response.lead_count == 1


def test_stub_service_compares_unlinked_live_lead_through_simsat(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    lead_registry_path = tmp_path / "live_leads.json"
    lead_registry_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "gdelt_1",
                    "title": "Kharkiv strike damages civilian buildings",
                    "region": "Kharkiv, Ukraine",
                    "latitude": 49.9935,
                    "longitude": 36.2304,
                    "category_guess": "civilian_building_cluster",
                    "status": "lead_only",
                    "source_date": "2026-04-28",
                }
            ]
        ),
        encoding="utf-8",
    )
    metadata = {
        "image_available": True,
        "source": "sentinel",
        "spectral_bands": ["red", "green", "blue"],
        "footprint": [],
        "size_km": 5.0,
        "cloud_cover": 0.1,
        "datetime": "2026-04-28T12:00:00Z",
        "timestamp": "2026-04-28T12:00:00Z",
    }
    requested_urls: list[str] = []

    class FakeResponse:
        status = 200
        headers = {"sentinel_metadata": json.dumps(metadata)}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            _ = exc_type
            _ = exc
            _ = tb

        def read(self) -> bytes:
            return b"png"

        def getcode(self) -> int:
            return self.status

    def fake_urlopen(url: str, timeout: float):
        requested_urls.append(url)
        assert timeout == 5.0
        return FakeResponse()

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="http://simsat.test/data/current/image/sentinel",
            simsat_baseline_endpoint="http://simsat.test/data/image/sentinel",
            simsat_current_http_enabled=True,
            simsat_baseline_http_enabled=True,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=str(lead_registry_path),
        )
    )
    lead = service.list_leads()[0]

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", selected_lead_id=lead.lead_id)
    )

    assert response.status == "ok"
    assert response.compare is not None
    assert response.compare.satellite_evidence is not None
    assert response.compare.satellite_evidence.scope == "exact_aoi"
    assert response.compare.satellite_evidence.offset_km == 0
    assert response.compare.satellite_evidence.usability == "direct_clear"
    assert response.compare.satellite_evidence.quality_score == 0.9
    assert response.focus_asset_id == lead.linked_asset_id
    assert any("lon=36.230400" in url for url in requested_urls)
    assert any("lat=49.993500" in url for url in requested_urls)
    assert any("size_km=5.0" in url for url in requested_urls)
    assert not any("size_km=1.5" in url for url in requested_urls)
    assert not any("size_km=0.75" in url for url in requested_urls)
    assert "/data/image/sentinel" in response.compare.current_frame.frame.source
    current_timestamp = datetime.now(tz=UTC).date().isoformat()
    assert any(f"timestamp={current_timestamp}T12%3A00%3A00Z" in url for url in requested_urls)
    assert any("timestamp=2023-04-29T12%3A00%3A00Z" in url for url in requested_urls)
    assert len(response.compare.satellite_evidence.attempts) == 1
    assert response.compare.satellite_evidence.quality_warnings == []
    assert response.compare.satellite_evidence.attempts[0].current_cloud_cover == 0.1
    assert response.compare.satellite_evidence.attempts[0].baseline_cloud_cover == 0.1
    assert response.analyst_report is None
    assert service.get_asset_evidence(lead.linked_asset_id or f"live_{lead.lead_id}") is None
    assert service.get_asset_analyst_report(lead.linked_asset_id or f"live_{lead.lead_id}") is None
    assert Path(response.compare.current_frame.frame.image_ref or "").exists()


def test_stub_service_chains_single_linked_search_match_into_site_compare(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    lead_registry_path = tmp_path / "live_leads.json"
    lead_registry_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "gdelt_port_au_prince",
                    "title": "Port-Au-Prince armed conflict damages port warehouses",
                    "summary": "Source reports visible damage around civilian port warehouses.",
                    "region": "Port-au-Prince, Haiti",
                    "latitude": 18.5392,
                    "longitude": -72.335,
                    "category_guess": "container_port",
                    "status": "lead_only",
                    "source_date": "2026-05-02",
                }
            ]
        ),
        encoding="utf-8",
    )

    class FakeResponse:
        status = 200
        headers = {
            "sentinel_metadata": json.dumps(
                {
                    "image_available": True,
                    "source": "sentinel",
                    "spectral_bands": ["red", "green", "blue"],
                    "footprint": [],
                    "size_km": 3.0,
                    "cloud_cover": 0.12,
                    "datetime": "2026-05-02T12:00:00Z",
                    "timestamp": "2026-05-02T12:00:00Z",
                }
            )
        }

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            _ = exc_type
            _ = exc
            _ = tb

        def read(self) -> bytes:
            return b"png"

        def getcode(self) -> int:
            return self.status

    def fake_planner_urlopen(request, timeout: float):
        request_url = request.full_url if hasattr(request, "full_url") else str(request)
        if request_url == "https://example.test/planner":
            return _FakeHTTPResponse(
                body=json.dumps(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(
                                        {
                                            "tool": "search_live_leads",
                                            "area": "Port-au-Prince",
                                            "category": None,
                                            "site_id": None,
                                            "alert_id": None,
                                            "camera": None,
                                        }
                                    )
                                }
                            }
                        ]
                    }
                ).encode("utf-8")
            )
        return FakeResponse()

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_planner_urlopen)
    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_planner_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="http://simsat.test/data/current/image/sentinel",
            simsat_baseline_endpoint="http://simsat.test/data/image/sentinel",
            simsat_current_http_enabled=True,
            simsat_baseline_http_enabled=True,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=str(lead_registry_path),
            agent_endpoint="https://example.test/planner",
            agent_http_enabled=True,
            agent_provider="openai_chat_completions_http",
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(query="What is the current situation in Port-au-Prince?")
    )

    assert response.status == "ok"
    assert response.tool == "site_compare"
    assert response.compare is not None
    assert response.compare.satellite_evidence is not None
    assert response.compare.satellite_evidence.size_km == 5.0
    assert response.focus_asset_id == "live_gdelt_port_au_prince"
    assert response.planner.mode == "live"


def test_stub_service_prefers_clear_nearby_simsat_over_cloudy_exact_pair(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    lead_registry_path = tmp_path / "live_leads.json"
    lead_registry_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "gdelt_cloudy_exact",
                    "title": "Kharkiv strike damages civilian buildings",
                    "region": "Kharkiv, Ukraine",
                    "latitude": 49.9935,
                    "longitude": 36.2304,
                    "category_guess": "civilian_building_cluster",
                    "status": "lead_only",
                    "source_date": "2026-04-28",
                }
            ]
        ),
        encoding="utf-8",
    )
    requested_urls: list[str] = []

    class FakeResponse:
        status = 200

        def __init__(self, cloud_cover: float) -> None:
            metadata = {
                "image_available": True,
                "source": "sentinel",
                "spectral_bands": ["red", "green", "blue"],
                "footprint": [],
                "size_km": 5.0,
                "cloud_cover": cloud_cover,
                "datetime": "2026-04-28T12:00:00Z",
                "timestamp": "2026-04-28T12:00:00Z",
            }
            self.headers = {"sentinel_metadata": json.dumps(metadata)}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            _ = exc_type
            _ = exc
            _ = tb

        def read(self) -> bytes:
            return b"png"

        def getcode(self) -> int:
            return self.status

    def fake_urlopen(url: str, timeout: float):
        requested_urls.append(url)
        assert timeout == 5.0
        if "lat=49.993500" in url and "lon=36.230400" in url:
            return FakeResponse(0.9)
        return FakeResponse(0.08)

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="http://simsat.test/data/current/image/sentinel",
            simsat_baseline_endpoint="http://simsat.test/data/image/sentinel",
            simsat_current_http_enabled=True,
            simsat_baseline_http_enabled=True,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=str(lead_registry_path),
        )
    )
    lead = service.list_leads()[0]

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", selected_lead_id=lead.lead_id)
    )

    assert response.status == "ok"
    assert response.compare is not None
    assert response.compare.satellite_evidence is not None
    evidence = response.compare.satellite_evidence
    assert evidence.scope == "nearby_aoi"
    assert evidence.usable_for_evidence is True
    assert evidence.usability == "direct_clear"
    assert evidence.quality_score > 0.8
    assert evidence.offset_km > 0
    assert len(evidence.attempts) >= 4
    assert evidence.attempts[0].current_cloud_cover == 0.9
    assert evidence.attempts[0].baseline_cloud_cover == 0.9
    assert evidence.attempts[-1].current_cloud_cover == 0.08
    assert evidence.attempts[-1].baseline_cloud_cover == 0.08
    assert evidence.quality_warnings == [f"nearby_offset_{evidence.offset_km:.1f}km"]
    assert any("lat=49.948455" in url for url in requested_urls)
    assert Path(response.compare.current_frame.frame.image_ref or "").exists()


def test_stub_service_marks_all_cloudy_simsat_pair_as_cloud_limited(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    lead_registry_path = tmp_path / "live_leads.json"
    lead_registry_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "gdelt_clouded_all_day",
                    "title": "Dnipro strike damages apartment buildings",
                    "region": "Dnipro, Ukraine",
                    "latitude": 48.4647,
                    "longitude": 35.0462,
                    "category_guess": "civilian_building_cluster",
                    "status": "lead_only",
                    "source_date": "2026-04-29",
                }
            ]
        ),
        encoding="utf-8",
    )

    class FakeResponse:
        status = 200

        def __init__(self) -> None:
            metadata = {
                "image_available": True,
                "source": "sentinel",
                "spectral_bands": ["red", "green", "blue"],
                "footprint": [],
                "size_km": 5.0,
                "cloud_cover": 0.92,
                "datetime": "2026-04-29T12:00:00Z",
                "timestamp": "2026-04-29T12:00:00Z",
            }
            self.headers = {"sentinel_metadata": json.dumps(metadata)}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            _ = exc_type
            _ = exc
            _ = tb

        def read(self) -> bytes:
            return b"png"

        def getcode(self) -> int:
            return self.status

    def fake_urlopen(url: str, timeout: float):
        _ = url
        assert timeout == 5.0
        return FakeResponse()

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="http://simsat.test/data/current/image/sentinel",
            simsat_baseline_endpoint="http://simsat.test/data/image/sentinel",
            simsat_current_http_enabled=True,
            simsat_baseline_http_enabled=True,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=str(lead_registry_path),
        )
    )
    lead = service.list_leads()[0]

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", selected_lead_id=lead.lead_id)
    )

    assert response.status == "ok"
    assert response.compare is not None
    assert response.compare.satellite_evidence is not None
    evidence = response.compare.satellite_evidence
    assert evidence.scope == "exact_aoi"
    assert evidence.size_km == 5.0
    assert evidence.usability == "cloud_limited"
    assert evidence.usable_for_evidence is False
    assert evidence.quality_score < 0.2
    assert "visible context" in evidence.quality_summary
    assert evidence.quality_warnings == ["current_cloud_92pct", "baseline_cloud_92pct"]
    assert len(evidence.attempts) == 12
    assert response.analyst_report is None
    assert "not a confirmed visual alert" in response.summary


def test_stub_service_prefers_clear_temporal_simsat_pair_over_cloudy_event_window(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    lead_registry_path = tmp_path / "live_leads.json"
    lead_registry_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "gdelt_temporal_cloud",
                    "title": "Kharkiv strike damages civilian buildings",
                    "summary": "Source reports damaged buildings after a strike.",
                    "region": "Kharkiv, Ukraine",
                    "latitude": 49.9935,
                    "longitude": 36.2304,
                    "category_guess": "civilian_building_cluster",
                    "status": "lead_only",
                    "source_date": "2026-04-29",
                }
            ]
        ),
        encoding="utf-8",
    )
    requested_urls: list[str] = []
    current_date = datetime.now(tz=UTC).date()
    shifted_baseline_date = datetime(2023, 4, 30, tzinfo=UTC).date() - timedelta(days=14)

    class FakeResponse:
        status = 200

        def __init__(self, *, cloud_cover: float, captured_at: str) -> None:
            metadata = {
                "image_available": True,
                "source": "sentinel",
                "spectral_bands": ["red", "green", "blue"],
                "footprint": [],
                "size_km": 5.0,
                "cloud_cover": cloud_cover,
                "datetime": captured_at,
                "timestamp": captured_at,
            }
            self.headers = {"sentinel_metadata": json.dumps(metadata)}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            _ = exc_type
            _ = exc
            _ = tb

        def read(self) -> bytes:
            return b"png"

        def getcode(self) -> int:
            return self.status

    def fake_urlopen(url: str, timeout: float):
        requested_urls.append(url)
        assert timeout == 5.0
        if f"timestamp={current_date.isoformat()}T12%3A00%3A00Z" in url:
            return FakeResponse(
                cloud_cover=0.04,
                captured_at=f"{current_date.isoformat()}T09:00:00Z",
            )
        if f"timestamp={shifted_baseline_date.isoformat()}T12%3A00%3A00Z" in url:
            return FakeResponse(
                cloud_cover=0.05,
                captured_at=f"{shifted_baseline_date.isoformat()}T09:00:00Z",
            )
        return FakeResponse(cloud_cover=0.88, captured_at="2026-04-29T09:00:00Z")

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="http://simsat.test/data/current/image/sentinel",
            simsat_baseline_endpoint="http://simsat.test/data/image/sentinel",
            simsat_current_http_enabled=True,
            simsat_baseline_http_enabled=True,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=str(lead_registry_path),
        )
    )
    lead = service.list_leads()[0]

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", selected_lead_id=lead.lead_id)
    )

    assert response.compare is not None
    evidence = response.compare.satellite_evidence
    assert evidence is not None
    assert evidence.scope == "exact_aoi"
    assert evidence.usability == "direct_clear"
    assert evidence.size_km == 5.0
    assert evidence.current_frame is not None
    assert (
        evidence.current_frame.frame.captured_at
        == f"{current_date.isoformat()}T09:00:00Z"
    )
    assert len(evidence.attempts) == 2
    assert evidence.attempts[0].current_cloud_cover == 0.04
    assert evidence.attempts[0].baseline_cloud_cover == 0.88
    assert evidence.attempts[1].current_cloud_cover == 0.04
    assert evidence.attempts[1].baseline_cloud_cover == 0.05
    assert any(
        f"timestamp={shifted_baseline_date.isoformat()}T12%3A00%3A00Z" in url
        for url in requested_urls
    )


def test_cloud_limited_live_pair_still_runs_source_led_sam3_and_liquid_analyst(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    lead_registry_path = tmp_path / "live_leads.json"
    lead_registry_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "gdelt_clouded_analyst",
                    "title": "Missile strike damages Dnipro apartment buildings",
                    "summary": "Local source reports damaged apartments and rubble.",
                    "region": "Dnipro, Ukraine",
                    "latitude": 48.4647,
                    "longitude": 35.0462,
                    "category_guess": "civilian_building_cluster",
                    "status": "lead_only",
                    "source_date": "2026-04-29",
                }
            ]
        ),
        encoding="utf-8",
    )
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeSentinelResponse:
        status = 200

        def __init__(self) -> None:
            metadata = {
                "image_available": True,
                "source": "sentinel",
                "spectral_bands": ["red", "green", "blue"],
                "footprint": [],
                "size_km": 3.0,
                "cloud_cover": 0.7,
                "datetime": "2026-04-29T12:00:00Z",
                "timestamp": "2026-04-29T12:00:00Z",
            }
            self.headers = {"sentinel_metadata": json.dumps(metadata)}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            _ = exc_type
            _ = exc
            _ = tb

        def read(self) -> bytes:
            return b"png"

        def getcode(self) -> int:
            return self.status

    def fake_sentinel_urlopen(url: str, timeout: float):
        _ = url
        assert timeout == 5.0
        return FakeSentinelResponse()

    def fake_sam3_urlopen(request, timeout: float):
        assert request.full_url == "https://example.test/sam3"
        assert timeout == 20.0
        body = json.loads(request.data.decode("utf-8"))
        calls.append(("sam3", body))
        assert body["source_context"]["title"].startswith("Missile strike")
        assert "apartment block" in body["prompts"]
        assert "rubble pile" in body["prompts"]
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "asset_id": "live_gdelt_clouded_analyst",
                    "current_frame_id": body["current_frame"]["frame"]["frame_id"],
                    "baseline_frame_id": body["baseline_frame"]["frame"]["frame_id"],
                    "current_image_ref": body["current_frame"]["frame"]["image_ref"],
                    "baseline_image_ref": body["baseline_frame"]["frame"]["image_ref"],
                    "model_version": "facebook/sam3",
                    "backend": "sam3_http",
                    "decision": "no_evidence",
                    "source_context": body["source_context"],
                    "prompts": body["prompts"],
                    "masks": [],
                    "visual_evidence_tags": [],
                    "triage_action": "discard",
                    "summary": "Cloud-limited frame; no defensible masks.",
                }
            ).encode("utf-8")
        )

    def fake_gateway_urlopen(request, timeout: float):
        assert request.full_url == "https://example.test/liquid"
        assert timeout == 60.0
        body = json.loads(request.data.decode("utf-8"))
        calls.append(("liquid", body))
        assert body["adapter_ref"].endswith("hf-corpus-full-v1b-adapter")
        assert body["model_version"] == "LiquidAI/LFM2.5-VL-450M"
        user_text = next(
            item["text"]
            for item in body["inputs"]
            if item["type"] == "input_text" and item["role"] == "user"
        )
        assert "Source event: Missile strike" in user_text
        assert "Visual focus prompts:" in user_text
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "output_text": json.dumps(
                        {
                            "visible_change_summary": (
                                "The image shows significant urban destruction, including "
                                "two civilians killed and one injured."
                            ),
                            "civilian_disruption_evidence": [],
                            "negative_evidence": [],
                            "uncertainty_factors": ["cloud_or_visibility_limit"],
                            "severity_hint": "low",
                            "recommended_action": "discard",
                            "confidence": 0.9,
                            "short_rationale": (
                                "The image shows debris despite cloud."
                            ),
                        }
                    )
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_sentinel_urlopen)
    monkeypatch.setattr("app.services.sam3_evidence.urlopen", fake_sam3_urlopen)
    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_gateway_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="http://simsat.test/data/current/image/sentinel",
            simsat_baseline_endpoint="http://simsat.test/data/image/sentinel",
            simsat_current_http_enabled=True,
            simsat_baseline_http_enabled=True,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=str(lead_registry_path),
            sam3_endpoint="https://example.test/sam3",
            sam3_http_enabled=True,
            analyst_endpoint="https://example.test/liquid",
            analyst_http_enabled=True,
        )
    )
    lead = service.list_leads()[0]

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", selected_lead_id=lead.lead_id)
    )

    assert response.status == "ok"
    assert response.compare is not None
    assert response.compare.satellite_evidence is not None
    assert response.compare.satellite_evidence.usability == "cloud_limited"
    assert response.analyst_report is None
    assert calls == []
    assert response.focus_asset_id is not None
    evidence = service.get_asset_evidence(response.focus_asset_id)
    analyst = service.get_asset_analyst_report(response.focus_asset_id)
    assert evidence is not None
    assert analyst is not None
    assert analyst.backend == "liquid_vlm_http"
    assert analyst.negative_evidence == ["low_visibility"]
    assert analyst.confidence == 0.25
    assert analyst.severity_hint == "none"
    assert "Liquid VLM visual read:" in analyst.visible_change_summary
    assert "significant urban destruction" in analyst.visible_change_summary
    assert "killed" not in analyst.visible_change_summary
    assert "injured" not in analyst.visible_change_summary
    assert "cloud-limited" in analyst.visible_change_summary
    assert [kind for kind, _ in calls] == ["sam3", "liquid"]


def test_source_safe_analyst_report_strips_singular_casualty_language() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )
    report = LiquidAnalystReport(
        asset_id="live_kramatorsk",
        current_frame_id="current",
        baseline_frame_id="baseline",
        model_version="LiquidAI/LFM2.5-VL-450M",
        backend="liquid_vlm_http",
        status="ready",
        visible_change_summary=(
            "The image depicts large-scale destruction of residential areas, with a "
            "focus on a civilian casualty."
        ),
        civilian_disruption_evidence=[],
        negative_evidence=[],
        uncertainty_factors=[],
        severity_hint="low",
        recommended_action="discard",
        confidence=0.86,
        short_rationale="Mentions casualty from source text.",
    )

    cleaned = service._source_safe_analyst_report(report)

    assert "casualty" not in cleaned.visible_change_summary.lower()
    assert "large-scale destruction" in cleaned.visible_change_summary
    assert cleaned.confidence == 0.45


def test_stub_service_uses_timestamped_simsat_when_current_overpass_has_no_image(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    lead_registry_path = tmp_path / "live_leads.json"
    lead_registry_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "gdelt_2",
                    "title": "Dnipro strike damages apartment buildings",
                    "region": "Dnipro, Ukraine",
                    "latitude": 48.4647,
                    "longitude": 35.0462,
                    "category_guess": "civilian_building_cluster",
                    "status": "lead_only",
                    "source_date": "2026-04-29",
                }
            ]
        ),
        encoding="utf-8",
    )
    no_current_metadata = {
        "image_available": False,
        "source": None,
        "spectral_bands": ["red", "green", "blue"],
        "footprint": [],
        "size_km": 5.0,
        "cloud_cover": None,
        "datetime": None,
        "timestamp": None,
    }
    historical_metadata = {
        "image_available": True,
        "source": "sentinel",
        "spectral_bands": ["red", "green", "blue"],
        "footprint": [],
        "size_km": 5.0,
        "cloud_cover": 0.08,
        "datetime": "2026-04-29T12:00:00Z",
        "timestamp": "2026-04-29T12:00:00Z",
    }
    requested_urls: list[str] = []

    class FakeResponse:
        status = 200

        def __init__(self, metadata: dict[str, object], body: bytes) -> None:
            self.headers = {"sentinel_metadata": json.dumps(metadata)}
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            _ = exc_type
            _ = exc
            _ = tb

        def read(self) -> bytes:
            return self._body

        def getcode(self) -> int:
            return self.status

    def fake_urlopen(url: str, timeout: float):
        requested_urls.append(url)
        assert timeout == 5.0
        if "/data/current/image/sentinel" in url:
            return FakeResponse(no_current_metadata, b"")
        return FakeResponse(historical_metadata, b"png")

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="http://simsat.test/data/current/image/sentinel",
            simsat_baseline_endpoint="http://simsat.test/data/image/sentinel",
            simsat_current_http_enabled=True,
            simsat_baseline_http_enabled=True,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=str(lead_registry_path),
        )
    )
    lead = service.list_leads()[0]

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", selected_lead_id=lead.lead_id)
    )

    assert response.compare is not None
    assert response.compare.current_frame.filter_reason == "simsat_historical_current_frame"
    assert response.compare.satellite_evidence is not None
    assert response.compare.satellite_evidence.scope == "exact_aoi"
    assert "/data/image/sentinel" in response.compare.current_frame.frame.source
    assert sum("/data/image/sentinel" in url for url in requested_urls) >= 2
    assert Path(response.compare.current_frame.frame.image_ref or "").exists()


def test_stub_service_falls_back_to_nearby_simsat_imagery_for_live_lead(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    lead_registry_path = tmp_path / "live_leads.json"
    lead_registry_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "gdelt_3",
                    "title": "Kharkiv strike damages civilian buildings",
                    "region": "Kharkiv, Ukraine",
                    "latitude": 49.9935,
                    "longitude": 36.2304,
                    "category_guess": "civilian_building_cluster",
                    "status": "lead_only",
                    "source_date": "2026-04-28",
                }
            ]
        ),
        encoding="utf-8",
    )
    no_image_metadata = {
        "image_available": False,
        "source": None,
        "spectral_bands": ["red", "green", "blue"],
        "footprint": [],
        "size_km": 5.0,
        "cloud_cover": None,
        "datetime": None,
        "timestamp": None,
    }
    available_metadata = {
        "image_available": True,
        "source": "sentinel",
        "spectral_bands": ["red", "green", "blue"],
        "footprint": [],
        "size_km": 10.0,
        "cloud_cover": 0.2,
        "datetime": "2026-04-28T12:00:00Z",
        "timestamp": "2026-04-28T12:00:00Z",
    }
    requested_urls: list[str] = []

    class FakeResponse:
        status = 200

        def __init__(self, metadata: dict[str, object], body: bytes) -> None:
            self.headers = {"sentinel_metadata": json.dumps(metadata)}
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            _ = exc_type
            _ = exc
            _ = tb

        def read(self) -> bytes:
            return self._body

        def getcode(self) -> int:
            return self.status

    def fake_urlopen(url: str, timeout: float):
        requested_urls.append(url)
        assert timeout == 5.0
        if "lat=49.993500" in url and "lon=36.230400" in url:
            return FakeResponse(no_image_metadata, b"")
        return FakeResponse(available_metadata, b"png")

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="http://simsat.test/data/current/image/sentinel",
            simsat_baseline_endpoint="http://simsat.test/data/image/sentinel",
            simsat_current_http_enabled=True,
            simsat_baseline_http_enabled=True,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=str(lead_registry_path),
        )
    )
    lead = service.list_leads()[0]

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", selected_lead_id=lead.lead_id)
    )

    assert response.compare is not None
    assert response.compare.satellite_evidence is not None
    assert response.compare.satellite_evidence.scope == "nearby_aoi"
    assert response.compare.satellite_evidence.usable_for_evidence is True
    assert response.compare.satellite_evidence.offset_km > 0
    assert any("lat=49.948455" in url for url in requested_urls)
    assert Path(response.compare.current_frame.frame.image_ref or "").exists()


def test_stub_service_rejects_blank_simsat_tiles_before_model_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    lead_registry_path = tmp_path / "live_leads.json"
    lead_registry_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "gdelt_blank_tile",
                    "title": "Kharkiv strike damages civilian buildings",
                    "region": "Kharkiv, Ukraine",
                    "latitude": 49.9935,
                    "longitude": 36.2304,
                    "category_guess": "civilian_building_cluster",
                    "status": "lead_only",
                    "source_date": "2026-04-28",
                }
            ]
        ),
        encoding="utf-8",
    )
    requested_urls: list[str] = []

    class FakeResponse:
        status = 200

        def __init__(self, *, blank: bool) -> None:
            metadata = {
                "image_available": True,
                "source": "sentinel",
                "spectral_bands": ["red", "green", "blue"],
                "footprint": [],
                "size_km": 5.0,
                "cloud_cover": 0.05,
                "datetime": "2026-04-28T12:00:00Z",
                "timestamp": "2026-04-28T12:00:00Z",
            }
            self.headers = {"sentinel_metadata": json.dumps(metadata)}
            self._body = _png_bytes("blank" if blank else "texture")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            _ = exc_type
            _ = exc
            _ = tb

        def read(self) -> bytes:
            return self._body

        def getcode(self) -> int:
            return self.status

    def fake_urlopen(url: str, timeout: float):
        requested_urls.append(url)
        assert timeout == 5.0
        return FakeResponse(blank="lat=49.993500" in url and "lon=36.230400" in url)

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="http://simsat.test/data/current/image/sentinel",
            simsat_baseline_endpoint="http://simsat.test/data/image/sentinel",
            simsat_current_http_enabled=True,
            simsat_baseline_http_enabled=True,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=str(lead_registry_path),
        )
    )
    lead = service.list_leads()[0]

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", selected_lead_id=lead.lead_id)
    )

    assert response.compare is not None
    evidence = response.compare.satellite_evidence
    assert evidence is not None
    assert evidence.scope == "nearby_aoi"
    assert evidence.usability == "direct_clear"
    assert evidence.attempts[0].current_status == "blank/no-data satellite tile"
    assert evidence.attempts[0].baseline_status == "skipped because current missing"
    assert any("lat=49.948455" in url for url in requested_urls)


def test_stub_service_marks_cloudy_frame_as_suppressed() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )
    service.frame_filter_policy = FrameFilterPolicy(cloud_cover_threshold=0.01)

    frame = service.get_current_frame()
    metrics = service.get_metrics()
    alerts = service.list_alerts()

    assert frame.accepted_for_alerting is False
    assert frame.filter_reason == "cloud_cover_too_high"
    assert frame.overlay_ref is None
    assert metrics.alerts_emitted == 4
    assert metrics.raw_frames_suppressed == 139
    assert metrics.downlink_rate == 0.028
    assert alerts == []


class StaticResponder:
    def __init__(self, raw_output_text: str) -> None:
        self.raw_output_text = raw_output_text

    def generate(self, *, payload, scenario) -> str:
        _ = payload
        _ = scenario
        return self.raw_output_text


def test_stub_service_uses_shared_eval_path_for_invalid_model_output() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )
    hero = service.scenarios["hero_port_disruption"]
    service.scenarios["hero_port_disruption"] = replace(
        hero,
        model_output_text='{"event_type":"probable_large_scale_disruption"}',
    )

    frame = service.get_current_frame()
    metrics = service.get_metrics()
    alerts = service.list_alerts()

    assert frame.accepted_for_alerting is False
    assert frame.filter_reason == "invalid_model_output"
    assert frame.overlay_ref is None
    assert alerts == []
    assert metrics.alerts_emitted == 4
    assert metrics.raw_frames_suppressed == 139
    assert metrics.downlink_rate == 0.028


def test_stub_service_routes_through_model_wrapper() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )
    service.model_wrapper = PromptedCandidateModel(
        model_version="lfm2.5-vl-450m-prompted",
        backend=StaticResponder(
            raw_output_text=(
                '{"event_type":"no_event","severity":"low","confidence":0.11,'
                '"bbox":[0.10,0.10,0.40,0.40],"civilian_impact":"no_material_impact",'
                '"why":"No durable disruption visible.","action":"discard"}'
            )
        ),
        prompt_builder=CandidatePromptBuilder(),
    )

    frame = service.get_current_frame()
    metrics = service.get_metrics()
    alerts = service.list_alerts()

    assert frame.accepted_for_alerting is False
    assert frame.filter_reason == "model_discarded"
    assert frame.overlay_ref is None
    assert alerts == []
    assert metrics.alerts_emitted == 4
    assert metrics.raw_frames_suppressed == 139


def test_stub_service_can_opt_in_model_http_backend(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        assert request.full_url == "https://example.test/model"
        assert timeout == 10.0
        body = json.loads(request.data.decode("utf-8"))
        assert body["scenario_id"] == "hero_port_disruption"
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "output_text": (
                        '{"event_type":"probable_large_scale_disruption","severity":"high",'
                        '"confidence":0.93,"bbox":[0.19,0.26,0.73,0.84],'
                        '"civilian_impact":"shipping_or_aid_disruption",'
                        '"why":"Live backend confirmed macro disruption.","action":"downlink_now"}'
                    )
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            model_endpoint="https://example.test/model",
            model_http_enabled=True,
            model_provider="atlas_json_http",
        )
    )

    frame = service.get_current_frame()
    alerts = service.list_alerts()

    assert frame.accepted_for_alerting is True
    assert frame.filter_reason == "accepted"
    assert alerts[0].confidence == 0.93
    assert alerts[0].why == "Live backend confirmed macro disruption."


def test_stub_service_can_opt_in_openai_responses_model_backend(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        assert request.full_url == "https://api.openai.com/v1/responses"
        assert timeout == 10.0
        body = json.loads(request.data.decode("utf-8"))
        assert body["model"] == "gpt-4.1-mini"
        assert body["input"][0]["role"] == "system"
        assert body["input"][1]["role"] == "user"
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "output_text": (
                        '{"event_type":"probable_large_scale_disruption","severity":"high",'
                        '"confidence":0.91,"bbox":[0.19,0.26,0.73,0.84],'
                        '"civilian_impact":"trade_disruption",'
                        '"why":"OpenAI provider confirmed macro disruption.",'
                        '"action":"downlink_now"}'
                    )
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="gpt-4.1-mini",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            model_endpoint="https://api.openai.com/v1/responses",
            model_http_enabled=True,
            model_provider="openai_responses_http",
            model_api_key="test-key",
        )
    )

    frame = service.get_current_frame()
    alerts = service.list_alerts()

    assert frame.accepted_for_alerting is True
    assert frame.filter_reason == "accepted"
    assert alerts[0].confidence == 0.91
    assert alerts[0].civilian_impact == "trade_disruption"
    assert alerts[0].why == "OpenAI provider confirmed macro disruption."


def test_stub_service_can_opt_in_openai_chat_model_backend(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        assert request.full_url == "https://liquid.example/v1/chat/completions"
        assert timeout == 10.0
        body = json.loads(request.data.decode("utf-8"))
        assert body["model"] == "LiquidAI/LFM2.5-VL-450M"
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][1]["role"] == "user"
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"event_type":"probable_large_scale_disruption","severity":"high",'
                                    '"confidence":0.92,"bbox":[0.19,0.26,0.73,0.84],'
                                    '"civilian_impact":"shipping_or_aid_disruption",'
                                    '"why":"Chat-completions backend confirmed macro disruption.",'
                                    '"action":"downlink_now"}'
                                )
                            }
                        }
                    ]
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="LiquidAI/LFM2.5-VL-450M",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            model_endpoint="https://liquid.example/v1/chat/completions",
            model_http_enabled=True,
            model_provider="openai_chat_completions_http",
            model_api_key="liquid-key",
        )
    )

    frame = service.get_current_frame()
    alerts = service.list_alerts()
    health = service.get_health()

    assert frame.accepted_for_alerting is True
    assert alerts[0].confidence == 0.92
    assert alerts[0].why == "Chat-completions backend confirmed macro disruption."
    assert health.debug is not None
    assert health.debug.model_recent is not None
    assert health.debug.model_recent.provider_id == "openai_chat_completions_http"
    assert health.debug.model_recent.parse_ok is True


def test_stub_service_keeps_fixture_only_frames_without_sentinel_endpoints(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    current = service.get_current_frame()
    baseline = service.get_baseline_frame()

    assert current.frame.source == "sentinel_current_stub"
    assert baseline.frame.source == "sentinel_baseline_stub"


def test_stub_service_replay_snapshot_uses_one_active_scenario(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )
    service.start_replay(
        ReplayStartRequest(
            asset_id="demo_bridge_01",
            scenario_id="bridge_access_obstruction",
        )
    )

    snapshot = service.get_replay_snapshot()

    assert snapshot.replay.asset_id == "demo_bridge_01"
    assert snapshot.current_frame.frame.asset_id == "demo_bridge_01"
    assert snapshot.baseline_frame.frame.asset_id == "demo_bridge_01"
    assert snapshot.current_frame.baseline_frame_id == snapshot.baseline_frame.frame.frame_id
    assert snapshot.alerts[0].alert_id == "blk_00018"
    assert snapshot.metrics.frames_scanned == 88


def test_stub_service_sam3_fixture_evidence_uses_active_alert_bbox(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    report = service.get_current_evidence()

    assert report.model_version == "facebook/sam3"
    assert report.backend == "fixture"
    assert report.decision == "segmentation_ready"
    assert report.triage_action == "downlink_now"
    assert report.masks[0].bbox_norm == (0.19, 0.26, 0.73, 0.84)
    assert report.prompts[:3] == ["warehouse", "container yard", "port crane"]


def test_stub_service_can_opt_in_sam3_http_backend(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        assert request.full_url == "https://example.test/sam3"
        assert timeout == 20.0
        body = json.loads(request.data.decode("utf-8"))
        assert body["asset"]["asset_id"] == "demo_port_01"
        assert "container yard" in body["prompts"]
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "asset_id": "demo_port_01",
                    "current_frame_id": "cur_demo_port_01_20260414",
                    "baseline_frame_id": "base_demo_port_01_20250901",
                    "model_version": "facebook/sam3.1",
                    "backend": "sam3_http",
                    "decision": "segmentation_ready",
                    "prompts": body["prompts"],
                    "masks": [
                        {
                            "label": "damaged port logistics apron",
                            "prompt": "damaged port logistics apron",
                            "score": 0.88,
                            "bbox_norm": [0.19, 0.26, 0.73, 0.84],
                            "area_ratio": 0.31,
                        }
                    ],
                    "visual_evidence_tags": ["damaged_port_or_logistics_apron"],
                    "triage_action": "downlink_now",
                    "summary": "Remote SAM3 bridge returned one candidate mask.",
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.sam3_evidence.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            sam3_endpoint="https://example.test/sam3",
            sam3_http_enabled=True,
        )
    )

    report = service.get_current_evidence()

    assert report.backend == "sam3_http"
    assert report.decision == "segmentation_ready"
    assert report.masks[0].score == 0.88


def test_stub_service_composes_sentinel_adapters_when_endpoints_are_configured(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="https://example.test/sentinel/current/",
            simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    current = service.get_current_frame()
    baseline = service.get_baseline_frame()

    assert current.frame.source.startswith(
        "https://example.test/sentinel/current"
        "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=current"
    )
    assert baseline.frame.source.startswith(
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=baseline"
    )
    assert current.frame.image_ref is not None
    assert baseline.frame.image_ref is not None
    assert tmp_path.joinpath(
        ".cache",
        "frames",
        "demo_port_01",
        "hero_port_disruption",
        "current",
        "cur_demo_port_01_20260414",
        "metadata.json",
    ).exists()
    assert tmp_path.joinpath(
        ".cache",
        "frames",
        "demo_port_01",
        "hero_port_disruption",
        "baseline",
        "base_demo_port_01_20250901",
        "metadata.json",
    ).exists()


def test_stub_service_uses_current_adapter_and_fixture_baseline_with_current_only_endpoint(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="https://example.test/sentinel/current/",
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    current = service.get_current_frame()
    baseline = service.get_baseline_frame()

    assert current.frame.source.startswith(
        "https://example.test/sentinel/current"
        "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=current"
    )
    assert baseline.frame.source == "sentinel_baseline_stub"
    assert current.frame.image_ref is not None
    assert baseline.frame.image_ref is not None


def test_stub_service_can_opt_in_current_http_transport(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(url: str, timeout: float):
        assert url == (
            "https://example.test/sentinel/current"
            "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=current"
        )
        assert timeout == 5.0
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "frame_id": "live_cur_demo_port_01_20260415",
                    "captured_at": "2026-04-15T07:10:00Z",
                    "image_ref": "live/demo_port_01/current.png",
                    "cloud_cover": 0.11,
                    "baseline_frame_id": "base_demo_port_01_20250901",
                    "overlay_ref": "live/demo_port_01/overlay.png",
                    "accepted_for_alerting": True,
                    "filter_reason": "accepted",
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="https://example.test/sentinel/current/",
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            simsat_current_http_enabled=True,
        )
    )

    current = service.get_current_frame()
    baseline = service.get_baseline_frame()

    assert current.frame.frame_id == "live_cur_demo_port_01_20260415"
    assert current.frame.source == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=current"
    )
    assert current.frame.image_ref is not None
    assert baseline.frame.source == "sentinel_baseline_stub"


def test_stub_service_uses_baseline_adapter_and_fixture_current_with_baseline_only_endpoint(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    current = service.get_current_frame()
    baseline = service.get_baseline_frame()

    assert current.frame.source == "sentinel_current_stub"
    assert baseline.frame.source == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=baseline"
    )
    assert current.frame.image_ref is not None
    assert baseline.frame.image_ref is not None


def test_stub_service_can_opt_in_baseline_http_transport(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(url: str, timeout: float):
        assert url == (
            "https://example.test/sentinel/baseline"
            "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=baseline"
        )
        assert timeout == 5.0
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "frame_id": "live_base_demo_port_01_20250902",
                    "captured_at": "2025-09-02T10:00:00Z",
                    "image_ref": "live/demo_port_01/baseline.png",
                    "cloud_cover": 0.03,
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.sentinel_client.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
            mapbox_token_present=False,
            watchlist_path=None,
            simsat_baseline_http_enabled=True,
        )
    )

    current = service.get_current_frame()
    baseline = service.get_baseline_frame()

    assert current.frame.source == "sentinel_current_stub"
    assert baseline.frame.frame_id == "live_base_demo_port_01_20250902"
    assert baseline.frame.source == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_port_01&scenario_id=hero_port_disruption&mode=baseline"
    )
    assert baseline.frame.image_ref is not None


def test_stub_service_keeps_opt_in_sentinel_wiring_across_replay_switch(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="https://example.test/sentinel/current/",
            simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )
    service.start_replay(
        ReplayStartRequest(
            asset_id="demo_bridge_01",
            scenario_id="bridge_access_obstruction",
        )
    )

    current = service.get_current_frame()
    baseline = service.get_baseline_frame()

    assert current.frame.source == (
        "https://example.test/sentinel/current"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=current"
    )
    assert baseline.frame.source == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=baseline"
    )
    assert current.frame.image_ref is not None
    assert baseline.frame.image_ref is not None
    assert tmp_path.joinpath(
        ".cache",
        "frames",
        "demo_bridge_01",
        "bridge_access_obstruction",
        "current",
        "cur_demo_bridge_01_20260414",
        "metadata.json",
    ).exists()
    assert tmp_path.joinpath(
        ".cache",
        "frames",
        "demo_bridge_01",
        "bridge_access_obstruction",
        "baseline",
        "base_demo_bridge_01_20251012",
        "metadata.json",
    ).exists()


def test_stub_service_uses_fixture_payload_transport_for_baseline_when_configured(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_fetch(self, plan):
        if plan.params["mode"] != "baseline":
            return None
        return {
            "frame_id": "live_base_demo_bridge_01_20251012",
            "captured_at": "2025-10-12T09:15:00Z",
            "image_ref": "live/demo_bridge_01/baseline.png",
            "cloud_cover": 0.02,
        }

    monkeypatch.setattr(FixtureSentinelPayloadTransport, "fetch", fake_fetch)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint="https://example.test/sentinel/current/",
            simsat_baseline_endpoint="https://example.test/sentinel/baseline/",
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )
    service.start_replay(
        ReplayStartRequest(
            asset_id="demo_bridge_01",
            scenario_id="bridge_access_obstruction",
        )
    )

    baseline = service.get_baseline_frame()

    assert baseline.frame.frame_id == "live_base_demo_bridge_01_20251012"
    assert baseline.frame.source == (
        "https://example.test/sentinel/baseline"
        "?asset_id=demo_bridge_01&scenario_id=bridge_access_obstruction&mode=baseline"
    )
    assert baseline.frame.image_ref is not None


def test_stub_service_loads_assets_from_watchlist_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "watchlist.json"
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "asset_id": "demo_port_01",
                    "asset_name": "Manifest Grain Port",
                    "asset_type": "grain_port",
                    "region": "Manifest Coast",
                    "latitude": 46.501,
                    "longitude": 30.747,
                    "hero": True,
                },
                {
                    "asset_id": "demo_bridge_01",
                    "asset_name": "Manifest Logistics Bridge",
                    "asset_type": "bridge",
                    "region": "Manifest Danube",
                    "latitude": 45.169,
                    "longitude": 28.801,
                    "hero": False,
                },
            ]
        ),
        encoding="utf-8",
    )
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=str(manifest_path),
        )
    )

    assets = service.list_assets()

    assert [asset.asset_id for asset in assets] == ["demo_port_01", "demo_bridge_01"]
    assert assets[0].asset_name == "Manifest Grain Port"
    assert service.hero_asset.asset_name == "Manifest Grain Port"


def test_stub_service_default_watchlist_includes_real_civilian_sites() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    asset_ids = [asset.asset_id for asset in service.list_assets()]
    asset_by_id = {asset.asset_id: asset for asset in service.list_assets()}

    assert asset_ids[:2] == ["demo_port_01", "demo_bridge_01"]
    assert "beirut_port_01" in asset_ids
    assert "port_sudan_01" in asset_ids
    assert "ras_abu_jarjur_01" in asset_ids
    assert "bahri_water_01" in asset_ids
    assert "arbaat_dam_01" in asset_ids
    assert "silpo_kvitneve_01" in asset_ids
    assert "unhcr_baghdad_01" in asset_ids
    assert "mosul_medical_city_01" in asset_ids
    assert "gedaref_silos_01" in asset_ids
    assert "manbij_silos_01" in asset_ids
    assert "okhmatdyt_01" in asset_ids
    assert "roshen_yahotyn_01" in asset_ids
    assert "trostianets_hospital_01" in asset_ids
    assert "kramatorsk_filtration_01" in asset_ids
    assert "kakhovka_dam_01" in asset_ids
    assert "mansour_dam_01" in asset_ids
    assert "mondelez_trostianets_01" in asset_ids
    assert "morandi_bridge_01" in asset_ids
    assert asset_by_id["demo_port_01"].evidence_state == "live_demo"
    assert asset_by_id["beirut_port_01"].evidence_state == "reference_event"
    assert asset_by_id["arbaat_dam_01"].evidence_state == "reference_event"
    assert asset_by_id["silpo_kvitneve_01"].evidence_state == "reference_event"
    assert asset_by_id["ras_abu_jarjur_01"].evidence_state == "reference_control"
    assert asset_by_id["bahri_water_01"].evidence_state == "reference_control"
    assert asset_by_id["mosul_medical_city_01"].evidence_state == "reference_control"
    assert asset_by_id["gedaref_silos_01"].evidence_state == "reference_control"
    assert asset_by_id["manbij_silos_01"].evidence_state == "reference_control"
    assert asset_by_id["okhmatdyt_01"].evidence_state == "reference_event"
    assert asset_by_id["roshen_yahotyn_01"].evidence_state == "reference_event"
    assert asset_by_id["trostianets_hospital_01"].evidence_state == "reference_control"
    assert asset_by_id["kramatorsk_filtration_01"].evidence_state == "reference_control"
    assert asset_by_id["kakhovka_dam_01"].evidence_state == "reference_event"
    assert asset_by_id["mansour_dam_01"].evidence_state == "reference_event"
    assert asset_by_id["mondelez_trostianets_01"].evidence_state == "reference_event"
    assert asset_by_id["morandi_bridge_01"].evidence_state == "reference_event"


def test_stub_service_exposes_seeded_leads() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=None,
        )
    )

    leads = service.list_leads()
    by_id = {lead.lead_id: lead for lead in leads}

    assert "lead_mansour_dam_202309" in by_id
    assert by_id["lead_mansour_dam_202309"].linked_asset_id == "mansour_dam_01"
    assert by_id["lead_qasmiyeh_bridge_202604"].status == "lead_only"


def test_stub_service_can_focus_selected_lead_without_asset() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=None,
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(
            tool="search_live_leads",
            area="South Lebanon",
            selected_lead_id="lead_qasmiyeh_bridge_202604",
        )
    )

    assert response.tool == "search_live_leads"
    assert response.status == "ok"
    assert response.focus_asset_id is None
    assert response.focus_lead_id == "lead_qasmiyeh_bridge_202604"
    assert response.leads[0].lead_id == "lead_qasmiyeh_bridge_202604"
    assert "live source" in response.summary
    assert response.camera is not None
    assert response.camera.mode == "focus_lead"


def test_stub_service_keeps_water_category_when_query_mentions_dam(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "tool": "latest_alerts",
                                        "area": "Arbaat, Red Sea State",
                                        "category": "water_infrastructure",
                                        "site_id": None,
                                        "alert_id": None,
                                    }
                                )
                            }
                        }
                    ]
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            agent_model_version="hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF",
            agent_endpoint="http://127.0.0.1:11434/v1/chat/completions",
            agent_http_enabled=True,
            agent_provider="openai_chat_completions_http",
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(query="show latest dam alerts near Arbaat, Red Sea State"),
    )

    assert response.tool == "latest_alerts"
    assert response.planner.mode == "live"
    assert response.resolved.area == "Arbaat, Red Sea State"
    assert response.resolved.category == "water_infrastructure"


def test_stub_service_can_opt_in_http_agent_planner(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        assert request.full_url == "https://example.test/agent"
        assert timeout == 3.0
        body = json.loads(request.data.decode("utf-8"))
        assert body["model_version"] == "lfm2.5-1.2b-instruct"
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "output_text": json.dumps(
                        {
                            "tool": "site_compare",
                            "site_id": "demo_bridge_01",
                        }
                    )
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            agent_endpoint="https://example.test/agent",
            agent_http_enabled=True,
            agent_provider="atlas_json_http",
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(query="compare the bridge"),
    )

    assert response.tool == "site_compare"
    assert response.planner.mode == "live"
    assert response.focus_asset_id == "demo_bridge_01"
    assert response.compare is not None
    assert response.compare.asset_id == "demo_bridge_01"


def test_stub_service_can_opt_in_openai_chat_agent_planner(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        assert request.full_url == "https://liquid.example/v1/chat/completions"
        assert timeout == 3.0
        body = json.loads(request.data.decode("utf-8"))
        assert body["model"] == "LiquidAI/LFM2.5-1.2B-Instruct"
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][1]["role"] == "user"
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "tool": "site_compare",
                                        "site_id": "demo_bridge_01",
                                    }
                                )
                            }
                        }
                    ]
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            agent_model_version="LiquidAI/LFM2.5-1.2B-Instruct",
            agent_endpoint="https://liquid.example/v1/chat/completions",
            agent_http_enabled=True,
            agent_provider="openai_chat_completions_http",
            agent_api_key="liquid-key",
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(query="compare the bridge"),
    )

    assert response.tool == "site_compare"
    assert response.planner.mode == "live"
    assert response.focus_asset_id == "demo_bridge_01"
    assert response.compare is not None
    assert response.compare.asset_id == "demo_bridge_01"


def test_stub_service_resolves_missing_live_planner_site_id_from_query(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "tool": "site_compare",
                                        "area": "Lower Danube",
                                        "category": "bridge",
                                        "site_id": None,
                                        "alert_id": None,
                                    }
                                )
                            }
                        }
                    ]
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            agent_model_version="hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF",
            agent_endpoint="http://127.0.0.1:11434/v1/chat/completions",
            agent_http_enabled=True,
            agent_provider="openai_chat_completions_http",
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(query="compare the bridge"),
    )

    assert response.tool == "site_compare"
    assert response.planner.mode == "live"
    assert response.focus_asset_id == "demo_bridge_01"
    assert response.resolved.site_id == "demo_bridge_01"


def test_stub_service_sanitizes_invalid_live_planner_area_filter(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "tool": "latest_alerts",
                                        "area": "grain_port",
                                        "category": None,
                                        "site_id": None,
                                        "alert_id": "invented-alert",
                                    }
                                )
                            }
                        }
                    ]
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            agent_model_version="hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF",
            agent_endpoint="http://127.0.0.1:11434/v1/chat/completions",
            agent_http_enabled=True,
            agent_provider="openai_chat_completions_http",
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(query="show latest alerts"),
    )

    assert response.tool == "latest_alerts"
    assert response.planner.mode == "live"
    assert response.resolved.area is None
    assert response.resolved.alert_id is None


def test_stub_service_regrounds_spurious_live_planner_area_from_query(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "tool": "search_live_leads",
                                        "area": "Port Sudan Aid Hub",
                                        "category": None,
                                        "site_id": None,
                                        "alert_id": None,
                                    }
                                )
                            }
                        }
                    ]
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            agent_model_version="hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF",
            agent_endpoint="http://127.0.0.1:11434/v1/chat/completions",
            agent_http_enabled=True,
            agent_provider="openai_chat_completions_http",
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(
            query=(
                "Scan current conflict disruption reports around Sudan and focus the strongest "
                "civilian infrastructure marker with source context."
            )
        ),
    )

    assert response.tool == "search_live_leads"
    assert response.planner.mode == "live"
    assert response.resolved.area == "Sudan"


def test_stub_service_honors_live_planner_category_filter(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "tool": "latest_alerts",
                                        "area": "Black Sea",
                                        "category": "aid_warehouse_cluster",
                                        "site_id": None,
                                        "alert_id": None,
                                    }
                                )
                            }
                        }
                    ]
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            agent_model_version="hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF",
            agent_endpoint="http://127.0.0.1:11434/v1/chat/completions",
            agent_http_enabled=True,
            agent_provider="openai_chat_completions_http",
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(query="show latest aid warehouse cluster alerts near Black Sea"),
    )

    assert response.tool == "latest_alerts"
    assert response.planner.mode == "live"
    assert response.focus_asset_id is None
    assert response.focus_alert_id is None
    assert response.resolved.area == "Black Sea"
    assert response.resolved.category == "aid_warehouse_cluster"


def test_stub_service_drops_inferred_category_for_broad_region_search(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "tool": "search_live_leads",
                                        "area": "Lebanon",
                                        "category": "aid_shelter_campus",
                                        "site_id": None,
                                        "alert_id": None,
                                    }
                                )
                            }
                        }
                    ]
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            agent_model_version="hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF",
            agent_endpoint="http://127.0.0.1:11434/v1/chat/completions",
            agent_http_enabled=True,
            agent_provider="openai_chat_completions_http",
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(query="show recent conflict reports near Lebanon"),
    )

    assert response.tool == "search_live_leads"
    assert response.planner.mode == "live"
    assert response.resolved.area == "Lebanon"
    assert response.resolved.category is None


def test_stub_service_honors_live_planner_region_lead_search(tmp_path: Path, monkeypatch) -> None:
    lead_registry_path = tmp_path / "live_leads.json"
    lead_registry_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "gdeltcloud_iran_tehran",
                    "title": "Reported disruption in Tehran",
                    "region": "Tehran, Iran",
                    "latitude": 35.6892,
                    "longitude": 51.389,
                    "category_guess": "civilian_building_cluster",
                    "status": "lead_only",
                    "summary": "Live source reports disruption affecting a civilian district.",
                    "source_date": "2026-04-29",
                }
            ]
        ),
        encoding="utf-8",
    )

    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "tool": "search_live_leads",
                                        "area": "Tehran, Iran",
                                        "category": None,
                                        "site_id": None,
                                        "alert_id": None,
                                    }
                                )
                            }
                        }
                    ]
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=str(lead_registry_path),
            agent_model_version="hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF",
            agent_endpoint="http://127.0.0.1:11434/v1/chat/completions",
            agent_http_enabled=True,
            agent_provider="openai_chat_completions_http",
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(query="what happened recently in Iran?"),
    )

    assert response.tool == "search_live_leads"
    assert response.status == "ok"
    assert response.focus_lead_id == "gdeltcloud_iran_tehran"
    assert response.camera is not None
    assert response.camera.mode == "focus_lead"
    assert response.resolved.area == "Tehran, Iran"


def test_stub_service_matches_macro_region_alias_for_live_lead_search(
    tmp_path: Path, monkeypatch
) -> None:
    lead_registry_path = tmp_path / "live_leads.json"
    lead_registry_path.write_text(
        json.dumps(
            [
                {
                    "lead_id": "gdeltcloud_iran_bushehr",
                    "title": "Reported blast disruption near Bushehr port",
                    "region": "Bushehr, Iran, Middle East",
                    "latitude": 28.9234,
                    "longitude": 50.8203,
                    "category_guess": "logistics_hub",
                    "status": "lead_only",
                    "summary": "Live source reports disruption affecting a coastal district.",
                    "source_date": "2026-04-29",
                },
                {
                    "lead_id": "gdeltcloud_ukraine_kharkiv",
                    "title": "Reported strike disruption in Kharkiv",
                    "region": "Kharkiv, Ukraine, Europe",
                    "latitude": 49.9935,
                    "longitude": 36.2304,
                    "category_guess": "civilian_building_cluster",
                    "status": "lead_only",
                    "summary": "Live source reports disruption affecting a civilian district.",
                    "source_date": "2026-04-29",
                },
            ]
        ),
        encoding="utf-8",
    )

    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "tool": "search_live_leads",
                                        "area": "Persian Gulf",
                                        "category": None,
                                        "site_id": None,
                                        "alert_id": None,
                                    }
                                )
                            }
                        }
                    ]
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            lead_registry_path=str(lead_registry_path),
            agent_model_version="hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF",
            agent_endpoint="http://127.0.0.1:11434/v1/chat/completions",
            agent_http_enabled=True,
            agent_provider="openai_chat_completions_http",
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(query="Show active conflict disruptions around the Persian Gulf."),
    )

    assert response.tool == "search_live_leads"
    assert response.status == "ok"
    assert response.resolved.area == "Persian Gulf"
    assert response.focus_lead_id == "gdeltcloud_iran_bushehr"
    assert [lead.lead_id for lead in response.leads] == ["gdeltcloud_iran_bushehr"]


def test_stub_service_drops_spurious_live_planner_area_on_selected_site(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        return _FakeHTTPResponse(
            body=json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "tool": "explain_alert",
                                        "area": "Bahrain",
                                        "category": None,
                                        "site_id": "arbaat_dam_01",
                                        "alert_id": None,
                                    }
                                )
                            }
                        }
                    ]
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            agent_model_version="hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF",
            agent_endpoint="http://127.0.0.1:11434/v1/chat/completions",
            agent_http_enabled=True,
            agent_provider="openai_chat_completions_http",
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(query="why is this flagged", selected_asset_id="arbaat_dam_01"),
    )

    assert response.tool == "explain_alert"
    assert response.planner.mode == "live"
    assert response.focus_asset_id == "arbaat_dam_01"
    assert response.focus_alert_id == "blk_nd_00011"
    assert response.resolved.area is None
    assert response.resolved.site_id == "arbaat_dam_01"
    assert response.resolved.selected_asset_id == "arbaat_dam_01"


def test_stub_service_reports_agent_planner_http_fallback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        raise URLError("offline")

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            agent_endpoint="https://example.test/agent",
            agent_http_enabled=True,
            agent_provider="atlas_json_http",
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(query="show biggest disruptions"),
    )

    assert response.tool == "biggest_disruptions"
    assert response.status == "no_result"
    assert response.planner.mode == "fallback"
    assert response.planner.reason == "planner_http_failed"


def test_stub_service_reports_agent_planner_invalid_json_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(request, timeout: float):
        _ = request
        _ = timeout
        return _FakeHTTPResponse(body=b'{"output_text":"not-json"}')

    monkeypatch.setattr("app.services.model_gateway.urlopen", fake_urlopen)
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
            agent_endpoint="https://example.test/agent",
            agent_http_enabled=True,
            agent_provider="atlas_json_http",
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(query="compare the bridge"),
    )

    assert response.tool == "search_live_leads"
    assert response.status == "ok"
    assert response.planner.mode == "fallback"
    assert response.planner.reason == "planner_invalid_json"


def test_stub_service_site_compare_returns_reference_event_for_seeded_real_site() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", site_id="beirut_port_01"),
    )

    assert response.status == "ok"
    assert response.tool == "site_compare"
    assert response.focus_asset_id == "beirut_port_01"
    assert response.focus_alert_id == "blk_nd_00001"
    assert response.compare is not None
    assert response.compare.current_frame.accepted_for_alerting is True
    assert "reference event evidence" in response.summary
    assert response.resolved.site_id == "beirut_port_01"


def test_stub_service_site_compare_returns_reference_control_for_seeded_water_site() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", site_id="ras_abu_jarjur_01"),
    )

    assert response.status == "ok"
    assert response.tool == "site_compare"
    assert response.focus_asset_id == "ras_abu_jarjur_01"
    assert response.focus_alert_id is None
    assert response.compare is not None
    assert response.compare.current_frame.accepted_for_alerting is False
    assert response.alerts == []
    assert "No material change" in response.summary


def test_stub_service_site_compare_returns_reference_event_for_seeded_food_site() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", site_id="silpo_kvitneve_01"),
    )

    assert response.status == "ok"
    assert response.tool == "site_compare"
    assert response.focus_asset_id == "silpo_kvitneve_01"
    assert response.focus_alert_id == "blk_nd_00010"
    assert response.compare is not None
    assert response.compare.current_frame.accepted_for_alerting is True


def test_stub_service_site_compare_returns_reference_control_for_seeded_food_control_site() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", site_id="gedaref_silos_01"),
    )

    assert response.status == "ok"
    assert response.tool == "site_compare"
    assert response.focus_asset_id == "gedaref_silos_01"
    assert response.focus_alert_id is None
    assert response.compare is not None
    assert response.compare.current_frame.accepted_for_alerting is False
    assert response.alerts == []


def test_stub_service_site_compare_returns_reference_event_for_seeded_medical_aid_site() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", site_id="okhmatdyt_01"),
    )

    assert response.status == "ok"
    assert response.tool == "site_compare"
    assert response.focus_asset_id == "okhmatdyt_01"
    assert response.focus_alert_id == "blk_nd_00014"
    assert response.compare is not None
    assert response.compare.current_frame.accepted_for_alerting is True
    assert "reference event evidence" in response.summary


def test_stub_service_site_compare_returns_reference_event_for_seeded_food_site_roshen() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", site_id="roshen_yahotyn_01"),
    )

    assert response.status == "ok"
    assert response.tool == "site_compare"
    assert response.focus_asset_id == "roshen_yahotyn_01"
    assert response.focus_alert_id == "blk_nd_00015"
    assert response.compare is not None
    assert response.compare.current_frame.accepted_for_alerting is True
    assert "reference event evidence" in response.summary


def test_stub_service_site_compare_returns_reference_event_for_seeded_food_site_mondelez() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", site_id="mondelez_trostianets_01"),
    )

    assert response.status == "ok"
    assert response.tool == "site_compare"
    assert response.focus_asset_id == "mondelez_trostianets_01"
    assert response.focus_alert_id == "blk_nd_00021"
    assert response.compare is not None
    assert response.compare.current_frame.accepted_for_alerting is True
    assert "reference event evidence" in response.summary


def test_stub_service_site_compare_returns_reference_control_for_seeded_medical_soft_site() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", site_id="trostianets_hospital_01"),
    )

    assert response.status == "ok"
    assert response.tool == "site_compare"
    assert response.focus_asset_id == "trostianets_hospital_01"
    assert response.focus_alert_id is None
    assert response.compare is not None
    assert response.compare.current_frame.accepted_for_alerting is False
    assert response.alerts == []


def test_stub_service_site_compare_returns_reference_control_for_seeded_water_soft_site() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", site_id="kramatorsk_filtration_01"),
    )

    assert response.status == "ok"
    assert response.tool == "site_compare"
    assert response.focus_asset_id == "kramatorsk_filtration_01"
    assert response.focus_alert_id is None
    assert response.compare is not None
    assert response.compare.current_frame.accepted_for_alerting is False
    assert response.alerts == []


def test_stub_service_site_compare_returns_reference_event_for_seeded_water_site_kakhovka() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", site_id="kakhovka_dam_01"),
    )

    assert response.status == "ok"
    assert response.tool == "site_compare"
    assert response.focus_asset_id == "kakhovka_dam_01"
    assert response.focus_alert_id == "blk_nd_00018"
    assert response.compare is not None
    assert response.compare.current_frame.accepted_for_alerting is True
    assert "reference event evidence" in response.summary


def test_stub_service_site_compare_returns_reference_event_for_seeded_water_site_mansour() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", site_id="mansour_dam_01"),
    )

    assert response.status == "ok"
    assert response.tool == "site_compare"
    assert response.focus_asset_id == "mansour_dam_01"
    assert response.focus_alert_id == "blk_nd_00020"
    assert response.compare is not None
    assert response.compare.current_frame.accepted_for_alerting is True
    assert "reference event evidence" in response.summary


def test_stub_service_site_compare_returns_reference_event_for_morandi() -> None:
    service = StubAtlasService(
        Settings(
            app_env="test",
            app_port=8000,
            model_version="lfm2.5-vl-450m-prompted",
            simsat_current_endpoint=None,
            simsat_baseline_endpoint=None,
            mapbox_token_present=False,
            watchlist_path=None,
        )
    )

    response = service.run_agent_query(
        AtlasAgentQueryRequest(tool="site_compare", site_id="morandi_bridge_01"),
    )

    assert response.status == "ok"
    assert response.tool == "site_compare"
    assert response.focus_asset_id == "morandi_bridge_01"
    assert response.focus_alert_id == "blk_nd_00022"
    assert response.compare is not None
    assert response.compare.current_frame.accepted_for_alerting is True
    assert "reference event evidence" in response.summary


class _FakeHTTPResponse:
    def __init__(self, *, body: bytes, status: int = 200) -> None:
        self.status = status
        self._body = body

    def __enter__(self) -> _FakeHTTPResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self.status
