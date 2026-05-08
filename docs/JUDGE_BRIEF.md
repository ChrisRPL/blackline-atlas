# Judge Brief

## What To Open

Run the app and open `/ui`. The intended review path is one operator workflow: live disruption leads, chat-driven globe focus, selected-point current-versus-baseline imagery, Liquid visual site brief, and guarded metrics.

## Judging Criteria Fit

Liquid Track rubric from the provided judging document:

- Satellite imagery, 10%: SimSat/DPhi-style current and historical satellite
  imagery is the core evidence source for selected sites.
- Innovation and fit, 35%: the product focuses on civilian lifeline disruption
  triage, where live source leads plus before/after imagery plus Liquid VLM
  analyst summaries create a practical operator workflow.
- Technical implementation, 35%: the app must run without debugging; preflight
  is SimSat, optional local Liquid adapter bridge, GDELT key, then
  `/ui`.
- Fine-tuning reward: LFM2.5-VL was fine-tuned on domain-specific satellite
  data, public weights are published, training/eval code is in `training/`, and
  the measured improvement is documented in `/model/status` and `docs/HF_JOBS.md`.
- Demo and communication, 20%: show one end-to-end question-to-evidence flow and
  explain why source leads provide event context while Liquid provides the visual
  site brief, not an autonomous targeting or alerting oracle.

## Live Mode Preflight

- Start SimSat on `localhost:9005` before the app if judging live imagery.
- Set `SIMSAT_REQUIRED=true`, `SIMSAT_CURRENT_HTTP_ENABLED=true`, and `SIMSAT_BASELINE_HTTP_ENABLED=true`.
- Start the local Liquid analyst bridge with the full-v1b adapter if paired-image
  summaries are part of the demo.
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
- `/evidence/current` and `/evidence/assets/{asset_id}` remain available as an experimental segmentation seam.
- SAM-compatible segmentation is not part of the judge path until imagery resolution supports reliable masks.
- The right-side inspection tray must show current/baseline frames first, then
  Liquid VLM visual-site-brief output when the model lane returns a report,
  including cloud/quality caveats instead of blank “no useful data” states.
- The parser accepts messy model JSON but fails closed when outputs are malformed, low-confidence, or negative/artifact-only.

## Model Status

- Base VLM: `LiquidAI/LFM2.5-VL-450M`
- Latest adapter: `ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter`
- Dataset lane: `ChrisRPL/blackline-atlas-training-corpus-v1`
- Latest HF job: `69f66f889d85bec4d76f0be0`
- Training loss improved from `3.0021` to `0.3273`
- Corpus-native SimSat gold eval: `22/22` JSON valid, `19/22` schema valid,
  `9/22` action match

Decision: the adapter is promoted only as a guarded paired-image analyst lane.
It does not autonomously emit alerts. Alerts remain source-led, parser-guarded,
and deterministic at the final action boundary.

## Architecture Pivot

The VLM fine-tune is useful for analyst narration, but not reliable enough for
runtime-critical alerting, so the runtime architecture uses tool-based evidence:

- Liquid text model for agent planning and source/lead routing.
- LiquidAI/LFM2.5-VL paired-image analyst lane for selected current-baseline evidence summaries.
- Public lead registry for conflict/disruption map points.
- SimSat/Sentinel current and baseline imagery for selected sites.
- Selected-site imagery uses an AOI ladder tuned for model visibility and site
  context: exact `5km -> 8km -> 3km`, then nearby `5km`, then broader regional
  context.
- SimSat PNGs that are mostly black/white no-data pixels are rejected before
  SAM3 or Liquid VLM analysis; the resolver keeps searching or falls back to
  labeled context imagery instead of presenting blank tiles as evidence.
- Segmentation is optional support only. The judge path does not run SAM on
  low-resolution Sentinel pairs because masks are too unstable to justify the
  added latency.
- Lead context drives visual focus prompts for the Liquid VLM analyst. Mapbox-only
  context is blocked from model evidence; real cloud-limited SimSat pairs still
  receive a visibility caveat report.
- Deterministic rule layer for `discard | defer | downlink_now`.

Real SAM smoke tests kept hard negatives clean but missed positive disruption
cases at this imagery scale. The runtime therefore keeps segmentation out of the
normal inference path instead of promoting it to a value claim.

## Why Fallback Exists

The product goal is a stable civilian lifeline triage workflow, not a speculative model showcase. Live lead ingestion and selected-point imagery are the primary path. Cached replay remains only as fallback and regression coverage so the workflow stays reviewable when external services are unavailable.

## Safety Boundary

Blackline Atlas is scoped to civilian infrastructure disruption triage. It does not rank military assets, support targeting, track troops or convoys, or provide attack/sabotage guidance.
