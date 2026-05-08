from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_ui_shell_serves_same_origin_dashboard() -> None:
    client = TestClient(create_app())

    response = client.get("/ui")
    trailing_response = client.get("/ui/")
    static_response = client.get("/ui-static/shell.js")

    assert response.status_code == 200
    assert trailing_response.status_code == 200
    assert static_response.status_code == 200
    assert "Blackline Atlas" in response.text
    assert "/ui-static/shell.css?v=" in response.text
    assert response.text.index("maplibre-gl.js") < response.text.index("/ui-static/shell.js")
    assert '<script defer src="https://unpkg.com/maplibre-gl@5.12.0/dist/maplibre-gl.js">' in (
        response.text
    )
    assert "/assets" in static_response.text
    assert "/leads" in static_response.text
    assert "/leads/refresh" in static_response.text
    assert "/replay/snapshot" in static_response.text
    assert "/evidence/current" in static_response.text
    assert "/evidence/assets/" in static_response.text
    assert "/replay/status" in static_response.text
    assert "/frames/current" in static_response.text
    assert "/frames/baseline" in static_response.text
    assert "/frame-image" in static_response.text
    assert "/alerts" in static_response.text
    assert "/metrics" in static_response.text
    assert "/model/status" in static_response.text
    assert "/agent/query" in static_response.text
    assert "selected_lead_id" in static_response.text
    assert 'id="chat-form"' in response.text
    assert 'id="lead-refresh"' in response.text
    assert 'id="map-stage"' in response.text
    assert "live leads loading" in response.text
    assert 'id="model-chip"' in response.text
    assert 'id="model-gate-decision"' in response.text
    assert 'id="lead-popover"' in response.text
    assert 'id="lead-popover-inspect"' in response.text
    assert 'id="liquid-analyst-card"' in response.text
    assert 'id="current-image"' in response.text
    assert 'id="baseline-image"' in response.text
    assert 'id="site-name"' in response.text
    assert 'id="signal-action"' in response.text
    assert 'id="metrics-alerts"' in response.text
    assert 'id="planner-chip"' in response.text
    assert "planner degraded" in response.text
    assert "local command mode" not in response.text
    assert "Using local command parsing" not in static_response.text
    assert "Thinking. Routing the request" in static_response.text
    assert "thinking-dots" in static_response.text
    assert "renderPlannerChip" in static_response.text
    assert "renderModelGate" in static_response.text
    assert "Segment read:" in static_response.text
    assert "live leads loading" in static_response.text
    assert "liveLeadCount" in static_response.text
    assert "inspectableLeadCount" in static_response.text
    assert "site reviews" not in static_response.text
    assert "noisy frames filtered" not in static_response.text
    assert "evidence sent" not in static_response.text
    assert "Liquid VLM analyst" in response.text
    assert "Liquid VLM live" in static_response.text
    assert "send evidence now" in static_response.text
    assert "blackline-lead-zone-glow" in static_response.text
    assert "blackline-lead-hit" in static_response.text
    assert "leadFeedNeedsRefresh" in static_response.text
    assert "lead-only" in static_response.text
    assert "countryFlagForLead" in static_response.text
    assert "Lead registry:" in static_response.text
    assert "leadModeSuffix" in static_response.text
    assert "refreshLiveLeads" in static_response.text
    assert "diagnostics" in static_response.text
    assert "Operator alerts use validated rules" in static_response.text
    assert "runtime ${runtime}" in static_response.text
    assert 'alerts ${status.can_affect_alerts ? "model reviewed" : "rule checked"}' in (
        static_response.text
    )
    assert "downlink ${adapter.downlink_recall}/${adapter.downlink_total}" in static_response.text
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert static_response.headers["cache-control"] == "no-store, max-age=0"
