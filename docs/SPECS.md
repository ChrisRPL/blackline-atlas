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
- SAM3/SAM3.1 concept-segmentation evidence lane
- optional Liquid paired-image analyst lane for safe civilian summaries
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

- fast enough for interactive local use
- easy to recover from API slowness
- fully typed internal data models
- robust to malformed model outputs
- one-command local startup

## Alert schema

Runtime alerts remain compact, but the VLM prompt and v2 training rows should be evidence-first. In live inspection, the Liquid VLM output is a source-led visual site brief first and a triage hint second; it should describe visible context and imagery limits even when it cannot visually confirm the source-reported event.

```json
{
  "visual_evidence_tags": ["burn_scar", "damaged_port_or_logistics_apron"],
  "evidence_strength": "strong",
  "damage_mechanism": "fire_burning",
  "visibility_quality": "good",
  "negative_type": "none",
  "bbox_norm": [0.19, 0.26, 0.73, 0.84],
  "bbox_quality": "tight",
  "change_confidence": 0.89,
  "civilian_infrastructure_type": "port_logistics_apron",
  "rationale": "Large terminal burn scar is visible versus baseline.",
  "triage_action": "downlink_now"
}
```

The runtime parser still accepts the legacy compact candidate shape and normalizes
evidence-first candidates into this alert candidate shape by deriving
`event_type`, `severity`, and `civilian_impact` from the evidence fields:

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

Guardrails:

- parser accepts common JSON wrappers, fences, action aliases, confidence strings, and single-item arrays
- negative/artifact evidence such as SAR speckle, seasonal change, construction change, or no visible change is downgraded away from `downlink_now`
- low-confidence positive outputs are repaired to `discard`
- alert IDs, timestamps, asset metadata, and source metadata remain seed-authoritative
- unrepairable output fails closed and emits no alert

## API

- `GET /health`
- `GET /health.debug`
- `GET /model/status`
- `GET /assets`
- `GET /leads`
- `GET /agent/tools`
- `POST /agent/query`
- `POST /replay/start`
- `POST /replay/stop`
- `GET /replay/status`
- `GET /replay/snapshot`
- `GET /evidence/current`
- `GET /evidence/assets/{asset_id}`
- `GET /analyst/assets/{asset_id}`
- `GET /frames/current`
- `GET /frames/baseline`
- `GET /alerts`
- `GET /metrics`

## UI

Single page only.

- top rail: mode, trust, replay state, planner fallback state
- model gate: visible adapter acceptance status and recommended runtime
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
    - request current/baseline evidence when the selected lead is linked
- center:
  - globe-first at wide zoom
  - map-first at inspection zoom
- command dock:
  - compact agent control for live-source search, latest confirmed alerts, biggest alerts,
    compare, explain, live refresh, and geographic drill-down flows
- agent response contract:
  - `summary` is the text shown in chat
  - `camera` drives map movement and marker highlights
  - `focus_asset_id` / `focus_lead_id` updates selection
  - `compare` populates current and baseline evidence
  - `analyst_report` may add a paired-image Liquid VLM summary when available
  - `alerts` updates alert cards and metrics
  - `leads` carries refreshed or matching lead markers when a command touches live lead state
  - `observations` records which typed tools ran and what they returned
- agent tools:
  - `search_live_leads`
  - `latest_alerts`
  - `biggest_disruptions`
  - `site_compare`
  - `explain_alert`
  - `refresh_live_leads`
- evidence tray or drawer:
  - current
  - baseline
  - alert
  - metrics
- evidence quality:
  - SimSat/Sentinel tiles that are mostly blank/no-data pixels are rejected
    before SAM3 or Liquid VLM analysis
  - wide/context imagery can orient the user, but it is not model evidence
- optional inspection context only after selection; no dashboard-first layout

## First interaction rules

- user should understand the product in under `20` seconds
- globe should answer:
  - where are current disruption leads
- chat should answer:
  - what changed
  - why it matters
  - show me nearby
  - what evidence is loaded or missing
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
- app refresh uses `POST /leads/refresh` with `source_mode=auto`
- `auto` uses GDELT Cloud v2 Events when `GDELT_API_KEY` or
  `GDELT_CLOUD_API_KEY` exists
- `auto` falls back to public GDELT Project exports when Cloud is unavailable
- ACLED remains disabled until `/api/acled/read` access is confirmed; UCDP
  Candidate is useful for slower validation, not the interactive local UX
- do not run the VLM on every point by default
- evidence review runs only when:
  - a point is selected
  - a chat flow requests review
  - a background batch explicitly targets a shortlist
- linked live leads may be converted into runtime assets for SimSat current-versus-baseline review
- on app open, the UI auto-selects the newest reviewable live lead and starts
  selected-site satellite review without waiting for a chat command
- current repo command:
  - `python3 -m app.services.lead_registry_refresh --dry-run`
  - dry-run probes source reachability and prints counts
  - full write mode is deliberate, not automatic on app boot

## Optional segmentation evidence lane

Segmentation is optional support, not part of the default inference path.
The fine-tuned Liquid VLM adapter is the guarded paired-image analyst, not the
final alert authority.
The runtime seam is:

- source/API lead registry provides the event context, location, and source
  summary
- Liquid text planner chooses the UI/tool action and derives situation-specific
  visual focus prompts from the lead context
- selected lead or watchlist asset
- current/baseline satellite pair
- prompt set such as `bridge span`, `container yard`, `rubble pile`, `debris field`, or `burn scar`
- optional SAM-compatible concept segmentation masks when the image pair has
  enough resolution for reliable masks
- Liquid analyst summary over the same pair and source context
- malformed or looping Liquid analyst JSON is repaired only when the action and
  confidence are recoverable; low-confidence `discard` outputs suppress positive
  damage claims and keep the source report as context, not imagery proof
- evidence tags, bbox, score, and area ratio
- deterministic rule layer emits `discard | defer | downlink_now`

Fixture masks are allowed only for tests and offline replay/reference evals. The
default runtime suppresses segmentation on low-resolution Sentinel pairs because
it adds latency without defensible visual value. A future high-resolution lane
can reattach the local SAM bridge once masks are measurable and useful.

## Acceptance criteria

- local run works with one command
- at least one stable hero scenario
- malformed model output does not break the UI
- counters update live
- current and baseline are visually clear inside the selected-site flow
- action decision is visible
