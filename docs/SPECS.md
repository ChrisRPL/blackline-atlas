# Product And Technical Specs

## Product

- Product name: Blackline Atlas
- Product category: onboard civilian lifeline monitoring and alert triage
- Primary user: civilian resilience operators and analysts who want a small queue of meaningful alerts about lifelines near cities, regions, and nearby countries rather than a firehose of imagery
- Core outcome: translate raw orbital imagery into compact, credible, structured alerts
- first impression: operational globe with current disruption points, then drill into evidence with chat or click

## Functional requirements

### Must-have
- public disruption-location fetch layer
  - refresh on schedule
  - default cadence: once per day unless manually refreshed
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
- `GET /leads`
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
- landing state:
  - branded dark 3D globe
  - disruption / conflict lead markers already visible
  - no heavy dashboard chrome
- interaction pattern:
  - click a point:
    - focus camera
    - open compact pop-up card above the point
    - show chat + evidence tray context
  - prompt in chat:
    - resolve geography or category intent
    - animate globe / map to the area
    - highlight matching points
    - summarize in chat
- center:
  - globe-first at wide zoom
  - map-first at inspection zoom
- command dock:
  - compact agent control for latest, biggest, compare, explain, and geographic drill-down flows
- evidence tray or drawer:
  - current
  - baseline
  - alert
  - metrics
- optional inspection context only after selection; no dashboard-first layout

## First interaction rules

- user should understand the product in under `20` seconds
- globe should answer:
  - where are current disruption leads
- chat should answer:
  - what changed
  - why it matters
  - show me nearby
- point markers are not all equal:
  - some are news / source leads
  - some are VLM-reviewed reference sites
  - trust state must remain visible
- first point click should open a compact source popup
  - awareness only
  - title, region, source date, summary, inspect action if linked
  - evidence drawer stays separate

## Lead registry

Before a user asks anything, the system should maintain a small lead registry of current disruption locations.

Each lead should carry:

- source URL
- source date
- locality / region
- approximate lat / lon
- category guess
- status:
  - `lead_only`
  - `vlm_reviewed`
  - `reference_event`
  - `reference_control`

Rule:

- registry refresh is a fetch / sourcing problem, not a VLM training problem
- do not run the VLM on every point by default
- VLM runs only when:
  - a point is selected
  - a chat flow requests review
  - a background batch explicitly targets a shortlist

## Acceptance criteria

- demo works with one command
- at least one stable hero scenario
- malformed model output does not break the UI
- counters update live
- current and baseline are visually clear inside the selected-site flow
- action decision is visible
