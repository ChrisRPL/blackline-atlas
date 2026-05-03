# Judge Brief

## What To Open

Run the app and open `/ui`. The intended review path is one operator workflow: live disruption leads, chat-driven globe focus, selected-point current-versus-baseline evidence, structured alert, and metrics.

## Live Mode Preflight

- Start SimSat on `localhost:9005` before the app if judging live imagery.
- Set `SIMSAT_REQUIRED=true`, `SIMSAT_CURRENT_HTTP_ENABLED=true`, and `SIMSAT_BASELINE_HTTP_ENABLED=true`.
- Set `GDELT_API_KEY` or `GDELT_CLOUD_API_KEY` for Cloud-first live leads; without it, the app falls back to public GDELT Project exports.
- Open `/ui` and verify the topbar before promising imagery. If SimSat is degraded, show source-lead routing and disclose that selected-point evidence may be unavailable.

Recommended prompts:

- `What happened recently in Iran?`
- `Show disruptions near Ukraine`
- `What happened in Gaza?`
- `Compare current and baseline evidence`

## What Is Real

- The backend API, schemas, agent query loop, live lead cache, selected-point evidence seam, and UI shell are implemented in this repo.
- Lead refresh can use GDELT Cloud or public GDELT conflict/disruption events.
- The UI uses a real WebGL globe surface with live source labels, selected-lead cards, and chat-driven camera intents.
- UI live refresh posts `source_mode=auto`, uses GDELT Cloud first when a key is present, then public GDELT Project fallback.
- Equivalent Cloud command: `python3 -m app.services.lead_registry_refresh --source-mode gdelt_cloud --output-path var/live_leads.json --gdelt-cloud-days 30 --gdelt-cloud-limit 500 --gdelt-cloud-confidence-profile loose --gdelt-cloud-countries all`.
- Equivalent public fallback command: `python3 -m app.services.lead_registry_refresh --source-mode gdelt --output-path var/live_leads.json --gdelt-hours 72 --gdelt-max-files 288 --gdelt-limit 500`.
- Set `LEAD_REGISTRY_PATH=var/live_leads.json` to make `/leads` and the agent planner consume the refreshed markers.
- `/agent/query` returns the operator summary plus camera/selection/evidence instructions used by the UI.
- `/replay/snapshot` remains available as a fallback payload for regression and reliability checks.
- `/evidence/current` and `/evidence/assets/{asset_id}` expose the SAM3-compatible segmentation evidence seam.
- Real SAM3 is treated as selected-site supporting evidence, not as an autonomous alert gate.
- The parser accepts messy model JSON but fails closed when outputs are malformed, low-confidence, or negative/artifact-only.

## Model Status

- Base VLM: `LiquidAI/LFM2.5-VL-450M`
- Latest adapter: `ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v10-adapter`
- Dataset lane: `ChrisRPL/satellite-disruption-triage-aux-v2-2`
- Latest HF job: `69f0ac8bd70108f37ace0f4d`
- Training loss improved from `2.9309` to `1.2123`
- Smoke eval still failed: `0/3` evidence-schema valid, `0/3` action match

Decision: the adapter is not promoted. The runtime is live tool routing plus deterministic guardrails, and the adapter is documented as a research artifact.

## Architecture Pivot

The VLM fine-tune did not become reliable enough for runtime-critical alerting, so the runtime architecture pivots to tool-based evidence:

- Liquid text model for agent planning and source/lead routing.
- LiquidAI/LFM2.5-VL paired-image analyst lane for selected current-baseline evidence summaries.
- Public lead registry for conflict/disruption map points.
- SimSat/Sentinel current and baseline imagery for selected sites.
- Required real SAM3-compatible concept segmentation for visible evidence masks.
  Fixture segmentation is reserved for tests/evals and is not treated as live
  model evidence.
- Deterministic rule layer for `discard | defer | downlink_now`.

Real SAM3 v2 smoke result: current-only and temporal checks both kept the hard
negative clean, but missed the Beirut positive. The runtime therefore keeps SAM3
behind deterministic guardrails instead of promoting it to the decision scorer.

## Why Fallback Exists

The product goal is a stable civilian lifeline triage workflow, not a speculative model showcase. Live lead ingestion and selected-point imagery are the primary path. Cached replay remains only as fallback and regression coverage so the workflow stays reviewable when external services are unavailable.

## Safety Boundary

Blackline Atlas is scoped to civilian infrastructure disruption triage. It does not rank military assets, support targeting, track troops or convoys, or provide attack/sabotage guidance.
