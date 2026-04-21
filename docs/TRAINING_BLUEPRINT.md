# Training Blueprint

## Principle

Do not make training the critical path.

Start with the prompted baseline.
Only move to fine-tuning after the schema, policy, and replay loop are stable.

## Data lane

Use the official SimSat path first.

- freeze historical current/baseline pairs from `/data/image/sentinel`
- keep `/data/current/image/sentinel` for live smoke and later demo validation
- keep Mapbox out of the first training lane; use it only for post-alert inspection context
- hold demo and hero AOIs out of train until non-demo captures exist
- prefer food, water, and aid lifelines near population centers
- treat mobility as a narrower fourth lane, not the default
- keep ports as one lane, not the whole product
- hold bridges to a higher sensitivity bar than food, water, and aid
- avoid mixed-use military ports, fuel depots, and frontline route-intel assets

Dataset-shape rule:

- one canonical row format for both train and benchmark when possible
- prefer timestamp cutoffs over random splits once train rows exist
- promote only after human review; model-generated labels can accelerate drafts, not replace the gate

## Model-role split

Do not treat the whole product as one model problem.

Use three separate lanes:

1. lead-registry lane
   - job:
     - fetch public conflict / disruption locations
     - dedupe
     - geocode
     - refresh daily
   - model need:
     - none by default
     - optional text extraction later
   - training need now:
     - none

2. agent-planner lane
   - job:
     - interpret chat request
     - choose filters, site, region, and camera move
   - training need now:
     - none
   - eval need:
     - query -> plan JSON

3. VLM evidence lane
   - job:
     - inspect one selected site or one shortlisted lead
     - compare current vs baseline
     - emit strict structured alert candidate
   - training need now:
     - yes, eventually
   - eval need:
     - image-pair -> strict JSON

Rule:

- do not train all lanes together
- train or adapt the VLM lane first, if and only if the gold set becomes strong enough
- keep lead-registry and planner lanes eval-first, not fine-tune-first

## Baseline model behavior

The model should do three narrow things:
- ground the relevant region
- answer a constrained operational question
- provide a short rationale

Policy and routing remain deterministic.

In the globe-first product, this narrows further:

- globe markers come from the lead registry
- the VLM should not be responsible for discovering the entire world
- the VLM should review one location at a time, after selection or shortlist

## Eval goals

Measure:
- JSON validity
- enum correctness
- bbox validity
- action calibration
- false positives

Keep separate eval tracks:

- lead registry:
  - source freshness
  - dedupe quality
  - geocode correctness
- planner:
  - query -> plan accuracy
  - area/category/site grounding
  - camera / selection intent
- VLM:
  - action accuracy
  - false positives
  - `defer` calibration
  - bbox validity

## Training stages

1. Prompted baseline with strict JSON
2. Held-out eval harness
3. Narrow custom dataset
4. Optional adapter training
5. Compare against known-good baseline

## Gate before adapter work

1. self-host SimSat locally
2. freeze the capture manifest
   - if one facility needs a tighter capture window, keep it in a case-keyed
     capture-override file; do not mutate the annotated row itself
3. build the `lfm25-vl-v1` corpus
4. score the prompted baseline on the held-out candidate-eval set
5. only then decide whether adapter tuning is worth doing

## Current seed path

- smoke/demo pack: `training/replay_pack/hero_eval.jsonl`
- first non-demo pack: `training/replay_pack/non_demo_eval.jsonl`
- prompted baseline runner: `training/scripts/run_lfm25_vl_prompted_eval.py`

## Future trainer fit

When the first real train split exists, prefer adapting it into an existing VLM SFT path like `leap-finetune` rather than building custom trainer plumbing.

Use the trainer only after:

1. exact-site registry is stable
2. timestamp-aware splits are frozen
3. the same row shape can serve both train and benchmark

## New data needs from the globe-first concept

### Lead-registry data

Need a small canonical table for every current globe point:

- `lead_id`
- `title`
- `source_url`
- `source_date`
- `region`
- `latitude`
- `longitude`
- `category_guess`
- `status`
- `last_refreshed_at`

This is product data, not VLM fine-tune data.

### Planner data

If planner work expands later, training / eval rows should look like:

- current visible globe state
- selected point or null
- watchlist / lead context
- user query
- expected plan JSON

Examples:

- `show disruptions near Poland`
- `zoom to water incidents near Lebanon`
- `compare this point`

### VLM data

No change in core row philosophy:

- exact site only
- current/baseline pair
- strict JSON target
- timestamp-aware split

But priority shifts:

- best VLM rows are exact sites that can also appear as clickable globe points
- broad city points are good registry items, bad VLM supervision items
