# Product And Technical Specs

## Product

- Product name: Blackline Atlas
- Product category: onboard civilian lifeline monitoring and alert triage
- Primary user: civilian resilience operators and analysts who want a small queue of meaningful alerts about lifelines near cities, regions, and nearby countries rather than a firehose of imagery
- Core outcome: translate raw orbital imagery into compact, credible, structured alerts

## Functional requirements

### Must-have
- curated watchlist
- current Sentinel frame retrieval
- historical Sentinel baseline retrieval
- lifeline classes centered on food, water, aid, and only then mobility
- missing and cloudy frame rejection
- anomaly proposal
- structured alert generation
- policy action: `discard | defer | downlink_now`
- metrics panel
- deterministic replay

### Nice-to-have
- Mapbox inspection context
- alert history
- offline cached replay
- optional adapter checkpoint switcher

## Non-functional requirements

- fast enough for demo
- easy to recover from API slowness
- fully typed internal data models
- robust to malformed model outputs
- one-command local startup

## Alert schema

```json
{
  "alert_id": "blk_00017",
  "timestamp": "2026-04-14T18:40:00Z",
  "asset_id": "demo_port_01",
  "asset_name": "Demo Port 01",
  "asset_type": "grain_port",
  "event_type": "probable_large_scale_disruption",
  "severity": "high",
  "confidence": 0.89,
  "bbox": [0.19, 0.26, 0.73, 0.84],
  "civilian_impact": "shipping_or_aid_disruption",
  "why": "significant surface change near terminal footprint versus recent baseline",
  "action": "downlink_now",
  "source": {
    "current_frame_id": "cur_001",
    "baseline_frame_id": "base_001",
    "model_version": "lfm2.5-vl-450m-prompted"
  }
}
```

## API

- `GET /health`
- `GET /health.debug`
- `GET /assets`
- `GET /agent/tools`
- `POST /agent/query`
- `POST /replay/start`
- `POST /replay/stop`
- `GET /replay/status`
- `GET /frames/current`
- `GET /frames/baseline`
- `GET /alerts`
- `GET /metrics`

## UI

Single page only.

- top rail: mode, trust, replay state, planner fallback state
- center: map-first canvas with watchlist and selected-site focus
- command dock: compact agent control for latest, biggest, compare, and explain flows
- evidence tray or drawer: current, baseline, alert, and metrics for the selected site
- optional inspection context only after selection; no dashboard-first layout

## Acceptance criteria

- demo works with one command
- at least one stable hero scenario
- malformed model output does not break the UI
- counters update live
- current and baseline are visually clear inside the selected-site flow
- action decision is visible
