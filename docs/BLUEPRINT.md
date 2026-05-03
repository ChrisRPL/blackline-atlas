# Blueprint

## Project definition

Blackline Atlas is onboard civilian lifeline monitoring.

Runtime promise:
Blackline Atlas watches a small list of public civilian lifelines from orbit and only downlinks compact disruption alerts when something materially changes.

## Product architecture

```text
public lead registry
  -> GDELT Cloud live refresh; GDELT Project fallback; ACLED/UCDP validation later
  -> already-geocoded event/source-url ingest
  -> rank / dedupe / refresh by CLI, UI button, or stale-on-boot check
  -> globe markers

watchlist assets or selected lead
  -> agent planner resolves tool + camera intent
  -> current Sentinel fetch
  -> historical Sentinel baseline
  -> hard filters
  -> SAM3 concept evidence
  -> optional Liquid paired-image analyst summary
  -> deterministic policy decision
  -> alert queue
  -> optional Mapbox context
  -> globe/card/chat/evidence UI
```

## UX shape

Default product shape:

- globe first
- chat second
- evidence third

Meaning:

- the globe is the browsing and awareness surface
- the chat is the agentic control surface
- the evidence tray is the proof surface
- every agent answer should include operator prose plus UI intent:
  camera focus, highlighted leads/assets, selected evidence, and alert summary

Important rule:

- a visible point on the globe is a lead, not always a model-confirmed alert
- point selection should trigger the expensive review path only when needed
- linked live leads can become inspectable assets for current-versus-baseline review

## Recommended build phases

### Phase 0
- verify current Sentinel endpoint
- verify historical Sentinel endpoint
- verify optional Mapbox endpoint
- save stable example areas
- create repo scaffold

### Phase 1
- build lead registry fetch + refresh
- build globe marker layer
- build FastAPI app
- build cache-backed service
- implement watchlist
- display current frame and baseline
- add rules-based filters
- add anomaly overlay
- emit rules-based alert card
- add metrics counters

### Phase 2
- add chat-driven globe control
- add prompt builder
- call agent planner
- call required selected-site SAM3 evidence lane for live image masks
- call optional Liquid analyst lane after evidence is loaded
- parse strict JSON
- retry or discard malformed outputs
- merge outputs into alert schema

### Phase 3
- create held-out eval set
- score JSON validity
- score action calibration
- score bbox formatting
- score false positives

### Phase 4
- optional adapter
- compare against prompted baseline

## Civilian Asset Strategy

Prefer:
- food hubs near population centers
- water infrastructure serving cities or districts
- aid warehouse clusters and aid-corridor nodes
- logistics hubs only when the civilian function is obvious
- only then a narrow set of clearly civilian mobility chokepoints

Avoid:
- military sites
- tactical watchlists
- active sensitive targets
- arbitrary village-by-village monitoring
- tiny-object use cases
- route-open / convoy-flow intelligence

## Non-negotiables

- one-page, globe-to-map UI
- planner-first routing; no keyword fallback for open-ended chat
- cache everything
- structured outputs only
- visible metrics
- one hero workflow
