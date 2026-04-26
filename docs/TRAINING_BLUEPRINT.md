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
- use public auxiliary lanes for fast trainer-side widening, but keep them out of Blackline gold scorecards
- current practical trainer-side pool can be widened much faster with public auxiliary rows than with bounded exact-site probing alone
- for active conflict facilities, use a before-conflict baseline pass if near-event pre frames are weak
- promote only after human review; model-generated labels can accelerate drafts, not replace the gate
- keep the training row itself minimal:
  - `messages`
  - image reference
  - text instruction
  - text answer
  - trainer-side metadata such as `image_root`, metrics, and limits should stay in config, not be baked into each row

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
- Ukraine auxiliary-train materializer: `training/scripts/materialize_ukraine_damage_aux_slice.py`
- conflict auxiliary materializer/validator: `training/scripts/materialize_conflict_disruption_aux_slice.py`
- adapter acceptance gate: `training/scripts/check_adapter_acceptance.py`

Current state:

- the non-demo gold eval pack is now frozen at `22` exact-site rows
- next step is local capture freeze plus the first train-prep corpus build
- LEAP-compatible VLM SFT export now comes from the same frozen candidate corpus, not a parallel ad hoc format
- `training/scripts/train_adapter.py` is now the config-first prep seam for train/eval artifacts and run metadata
- `training/scripts/run_train_backend.py` now turns that prep seam into a real LEAP backend handoff plus a portable bundle
- `training/scripts/submit_train_backend_hf_job.py` is the remote-first path for actual trainer execution
- current practical trainer-side pool:
  - `33` internal `train_01` rows
  - `2,417` public auxiliary rows
  - `2,450` total raw trainer-side rows without mutating Blackline gold eval
  - current LEAP-exportable train count: `2,450`
  - current train action mix:
    - `discard`: `569`
    - `defer`: `1,165`
    - `downlink_now`: `716`
  - strong VLM target:
    - `400` internal exact-site train rows
    - `4,000` public auxiliary train rows
    - `100` internal gold eval rows
    - `400` public transfer eval rows
  - remaining VLM data gap:
    - `367` internal train rows
    - `1,583` public auxiliary train rows
    - `78` internal gold eval rows
    - public transfer eval target is covered by the `1,163` held-out v1.3 source rows, but it is not a canonical Blackline metric

## Train 01 opening contract

- keep `training/replay_pack/non_demo_eval.jsonl` frozen and eval-only
- promote train rows in a separate tranche board:
  - [training/replay_pack/train_tranche_01.md](/Users/krzysztof/blackline-atlas/training/replay_pack/train_tranche_01.md)
- no random split
- no hero/demo rows
- no external benchmark rows in the first train tranche
- external slices may still widen training in a separate auxiliary lane:
  - materialize them with `training/scripts/materialize_aux_train_slice.py`
  - keep them out of frozen Blackline eval reporting
  - current auxiliary lane can already reach `248` train-only rows with:
    - checked-in `xBD` + `SpaceNet 8` seeds
    - widened `KOlegaBB/damage_assessment_ukraine` slices
  - current aux-backed HF train config:
    - `training/configs/lfm25_vl_sft_train_hf_aux_v7.yaml`
  - latest completed adapter:
    - `ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v7-adapter`
- use the same exact-site pair shape for:
  - prompted eval
  - benchmark
  - later LEAP-compatible VLM SFT

## Future trainer fit

When the first real train split exists, prefer adapting it into an existing VLM SFT path like `leap-finetune` rather than building custom trainer plumbing.

Current honest boundary:

1. local machine:
   - capture freeze
   - corpus build
   - LEAP export
   - bundle creation
2. remote GPU:
   - actual `leap-finetune` run
3. authoritative eval:
   - stays outside the trainer
   - frozen Blackline held-out slices, not the trainer's internal random split

Checkpoint eval rule:

- when an adapter checkpoint lands, keep the base model fixed and score it with:
  - `python3 training/scripts/run_lfm25_vl_prompted_eval.py --model-id LiquidAI/LFM2.5-VL-450M --adapter-ref <adapter_dir_or_hub_repo>`
- do not overload `--model-id` to mean both base and adapter
- reject the adapter unless `check_adapter_acceptance.py` shows:
  - same frozen gold dataset as base
  - action-match count strictly better than base
  - `downlink_now` recall strictly better than base
  - false positives not worse than base
  - schema validity not worse than base

Use the trainer only after:

1. exact-site registry is stable
2. timestamp-aware splits are frozen
3. the same row shape can serve both train and benchmark
4. the first trainer config can benchmark on start against held-out eval slices before burning a full run

## Liquid cookbook notes we should actually copy

From Liquid's official cookbook:

- `examples/satellite-vlm` confirms the right split of work:
  - data prep
  - JSONL conversion
  - trainer config
  - benchmark config
  - checkpoint retrieval
- keep grounding outputs in normalized `0-1` JSON bbox form
  - that matches our current structured candidate format already
- trainer eval should stay cheap and frequent
  - small capped eval slices during iteration
  - full eval as a separate explicit run
- heavy prep and training can run remote
  - local machine should mostly launch jobs, stream logs, and inspect artifacts
- do not mutate row format just to satisfy one trainer
  - adapt the exporter to the trainer, not the annotated truth

This means Blackline should keep:

1. exact-site annotated truth as canonical
2. `build_lfm25_vl_corpus.py` as the row materializer
3. `export_leap_vlm_sft.py` as the trainer-format exporter
4. `train_adapter.py` as the config-first prep and run-manifest seam
5. `run_train_backend.py` as the LEAP handoff + bundle seam
6. `submit_train_backend_hf_job.py` as the HF remote execution seam
7. our stricter structured eval outside the trainer:
   - action accuracy
   - schema-valid rate
   - bbox-valid rate
   - false-positive rate
   - `defer` calibration

Current config files:

- `training/configs/lfm25_vl_sft_smoke.yaml`
- `training/configs/lfm25_vl_sft_train_hf.yaml`
- `training/configs/lfm25_vl_full_eval.yaml`

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
