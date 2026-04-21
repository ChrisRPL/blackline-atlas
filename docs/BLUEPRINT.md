# Blueprint

## Project definition

Blackline Atlas is onboard civilian lifeline monitoring.

Demo promise:
Blackline Atlas watches a small list of public civilian lifelines from orbit and only downlinks compact disruption alerts when something materially changes.

## Product architecture

```text
public lead registry
  -> web/news source fetch
  -> geocode / dedupe / daily refresh
  -> globe markers

watchlist assets or selected lead
  -> current Sentinel fetch
  -> historical Sentinel baseline
  -> hard filters
  -> anomaly proposer
  -> VLM grounding / VQA / rationale
  -> policy decision
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

Important rule:

- a visible point on the globe is a lead, not always a model-confirmed alert
- point selection should trigger the expensive review path only when needed

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
- call VLM
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

## Demo-safe asset strategy

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
- deterministic replay
- cache everything
- structured outputs only
- visible metrics
- one hero workflow
