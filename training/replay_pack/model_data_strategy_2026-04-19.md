# Model Data Strategy — 2026-04-19

Purpose:

- make current data truth explicit
- split VLM data needs from agent-model data needs
- stop mixing image supervision with planner routing work

## Repo state

### VLM / image-lane truth

- `hero_eval.jsonl`: `2`
- `non_demo_eval.jsonl`: `22`
- `train_01.jsonl`: `33`
- current auxiliary train rows: `2,417`
- current LEAP-exportable train pool: `2,450`
- overall internal annotated rows: `57`
- non-demo positives: `12`
  - `food`: `4`
  - `aid`: `3`
  - `mobility`: `2`
  - `water`: `3`
- non-demo controls / stress: `10`
  - `water`: `4`
  - `food`: `3`
  - `aid`: `3`
- split shape:
  - `holdout_geo`: `11`
  - `holdout_stress`: `10`
  - `dev`: `1`
  - `train`: `33`

Implication:

- VLM eval lane is real
- first gold eval set is complete
- VLM train lane exists but is still small internally
- public auxiliary data now gives the next adapter run enough scale to test the fixed exporter
- production-quality tuning still needs more internal rows and a stronger `defer` lane

### Agent / planner truth

- planner tool set: `4`
  - `latest_alerts`
  - `biggest_disruptions`
  - `site_compare`
  - `explain_alert`
- current frozen planner eval rows:
  - `training/replay_pack/agent_command_eval.jsonl`: `30`
- current watchlist assets:
  - `24`

Implication:

- planner lane already has deterministic fallback and sanitization
- planner fine-tuning is not the right next move
- planner eval breadth is now strong enough for the current watchlist
- next pressure moves back to VLM data growth, not planner training

## What the VLM still needs

Gold-set target stays frozen:

- total: `22`
- core rows: `12`
  - `food`: `4`
  - `water`: `3`
  - `aid`: `3`
  - `mobility`: `2`
- controls: `10`

Current gap against that target:

- total missing rows: `0`
- missing positives: `0`
- missing controls / stress: `0`

Current train pool:

- internal train: `33`
- auxiliary train: `2,417`
- total trainer rows: `2,450`
- action mix:
  - `discard`: `569`
  - `defer`: `1,165`
  - `downlink_now`: `716`

Required dataset targets for a strong VLM adapter:

- internal gold eval:
  - current: `22`
  - minimum useful: `50`
  - strong target: `100`
  - chosen target for a strong adapter claim: `100`
  - remaining to collect: `78`
  - required shape: roughly balanced positives / controls, at least `15-20` `defer` or ambiguity cases
- internal train:
  - current: `33`
  - minimum useful: `150`
  - strong target: `400`
  - chosen target for the main Blackline adapter: `400`
  - remaining to collect: `367`
  - preferred shape: `45% downlink_now`, `35% discard`, `20% defer`
  - exact target mix: `180 downlink_now`, `140 discard`, `80 defer`
  - family target: at least `40` exact civilian facility families, with `3-6` rows per main family
- public auxiliary train:
  - current: `2,417`
  - minimum useful: `1,000`
  - strong target: `3,000-5,000`
  - chosen target for transfer robustness: `4,000`
  - remaining to collect: `1,583`
  - use: transfer and robustness only, lower trust than internal rows
- public auxiliary eval:
  - current usable public eval: `1,163` held-out source rows from `satellite-disruption-triage-aux-v1-3`
  - target: `300-500`
  - chosen target for transfer diagnostics: `400`
  - remaining to collect: `0`
  - use: transfer diagnostics only, never headline Blackline metric

Exact target for the next strong VLM training set:

- `400` internal exact-site train rows
- `4,000` public auxiliary train rows
- `4,400` total train rows before synthetic augmentation
- `100` internal gold eval rows
- `400` public transfer eval rows

Current VLM gap:

- internal train gap: `367`
- public auxiliary train gap: `1,583`
- internal gold eval gap: `78`
- public transfer eval gap: `0`
- total train-row gap to the strong target: `1,950`

Most important next pieces:

1. move the VLM lane from policy-first labels to evidence-first labels
   - evidence tags before `triage_action`
   - hard negatives explicitly labeled by negative type
   - modality artifacts marked rather than hidden
2. keep finding internal `defer` and hard-negative rows
3. require the next adapter to beat the base model without increasing false positives
4. ask `ml-intern` to scale public auxiliary train only when rows include evidence primitives,
   not only `discard | defer | downlink_now`

Evidence-first row target:

- required visual evidence fields:
  - `visual_evidence_tags`
  - `evidence_strength`
  - `damage_mechanism`
  - `visibility_quality`
  - `negative_type`
  - `bbox_norm`
  - `bbox_quality`
  - `change_confidence`
  - `civilian_infrastructure_type`
  - `rationale`
  - `triage_action`
- positive visual tags should be visible in the image pair, not inferred from location
- hard-negative tags are first-class:
  - `no_visible_change`
  - `sar_speckle_or_modality_artifact`
  - `seasonal_or_lighting_change`
  - `construction_or_non_conflict_change`
  - `low_visibility`

## What the agent model still needs

Do not fine-tune the planner yet.

Reason:

- the planner is plan-only, not answer-generation
- backend already owns truth, ranking, trust, evidence, and replay/live state
- current failure modes are better handled by eval growth than by training

What is needed now instead:

- expand `agent_command_eval.jsonl` from `30` rows to roughly `150`
- exact planner eval target: `150`
- remaining planner eval rows to add: `120`
- keep the current `AgentCommandEvalCase` schema
- score routing correctness, not prose quality

Required eval buckets:

1. tool paraphrases
2. area grounding
   - region names
   - asset names
   - nearby-country phrasing
3. category synonyms
4. selected-asset precedence
5. explicit-tool bypass
6. no-result geography
7. ambiguous-site nulling
8. planner failure / sanitization regressions

If planner fine-tuning is ever revisited later:

- minimum SFT rows: `500`
- strong SFT target: `1,500-3,000`
- chosen SFT target: `2,000`
- current SFT rows: `0`
- remaining SFT rows to create: `2,000`
- eval target before training claim: `300`
- remaining eval rows before a planner training claim: `270`
- training row should be:
  - watchlist context
  - selected asset context
  - user query
  - expected `AtlasAgentPlan` JSON only
- not image pairs
- not alert candidates
- not final natural-language answers

## Lead-registry extraction data targets

The lead registry should stay deterministic first.

Fine-tune a text extractor only if source-normalization throughput becomes the bottleneck.

If that happens, target:

- lead extraction eval:
  - minimum: `200` source snippets
  - strong target: `500`
  - chosen target: `500`
  - current reviewed snippets: `0`
  - remaining snippets: `500`
- lead extraction SFT:
  - minimum: `1,000` reviewed snippets
  - strong target: `3,000`
  - chosen target: `3,000`
  - current reviewed snippets: `0`
  - remaining snippets: `3,000`
- required labels:
  - source URL / publisher / date
  - location string
  - latitude / longitude if derivable
  - candidate category
  - confidence / reject reason
  - civilian-only safety classification

This data is text-only and must not be mixed with VLM image-pair training.

## Next data order

1. count `Mondelez Trostianets Confectionery Factory` as the fourth exact food positive and stop spending more bounded time on `food_04`
2. count `Morandi Bridge` as the second exact mobility positive and stop pushing `Qasmiyeh Bridge`
3. freeze the gold eval pack at `22` non-demo rows
4. materialize the local SimSat capture manifest and first `lfm25-vl-v1` corpus
5. open the first train-row tranche toward `40-80` rows while leaving the gold pack stable
6. planner eval expansion only after watchlist/query breadth grows again

Working train-row board:

- see [train_tranche_01.md](./train_tranche_01.md)

## Current recommendation

- VLM: freeze gold eval, then data-first toward train rows
- planner: eval-first
- both: no fine-tune rush
- fastest extra training breadth:
  - exact internal family depth first
  - plus a separate auxiliary-train lane from checked-in `xBD` and `SpaceNet 8` public seeds
  - never mix auxiliary rows into frozen Blackline scorecards

## External reference

For external datasets, cross-model cohort, and benchmark structure:

- see [external_benchmark_research_2026-04-19.md](./external_benchmark_research_2026-04-19.md)

External-ready slices now:

- `internal_public_seed_v0`
- `xbd_public_seed_v0`
- `spacenet8_public_seed_v0`

Rule:

- external slices help eval, transfer research, and hackathon storytelling
- they do not increase the internal Blackline gold-row count
- they should not be mixed into the core gold metrics without explicit remapping
- the tiny internal public seed is benchmark-only, not the full internal non-demo benchmark

First real cohort result:

- see [liquid_benchmark_cohort_2026-04-20.md](./liquid_benchmark_cohort_2026-04-20.md)
- summary:
  - internal public seed: schema-valid but recall-collapsed
  - `xBD` and `SpaceNet 8`: transfer outputs malformed under the frozen prompt contract

Net:

- benchmark lane is now useful for research and hackathon proof
- core Blackline priority does not change
- next core move is fresh gold-row acquisition, not more benchmark churn

For the faster current view on why data growth slows down, how current-source lead intake should stay separate from VLM rows, and which external datasets are worth using right now:

- see [data_acquisition_speedup_2026-04-22.md](./data_acquisition_speedup_2026-04-22.md)

## External dataset-generation findings to keep

From the `leap-finetune` repo plus Pau Labarta Bajo's VLM dataset recipe:

1. training infra is not the hard part
   - data generation and split hygiene are
2. use one canonical messages format for both train and benchmark rows
   - `leap-finetune` expects VLM SFT rows in HF messages schema
   - the same format can drive eval during training
3. do not use random temporal splits for imagery
   - use timestamp cutoffs
   - avoid near-duplicate pre/post tiles leaking across train and test
4. favor diverse fixed locations over random open-world grabs
   - Pau's workflow starts from representative locations, then tiles them
   - for Blackline this maps to curated civilian lifeline sites, not generic world tiles
5. frontier-model labeling is useful only behind a hard human gate
   - model-generated JSON can accelerate labels
   - exact-parcel promotion still needs human review for honesty
6. benchmark during training using the same row shape
   - `leap-finetune` already supports eval-on-train for VLM SFT
   - useful once our first real train split exists

## Blackline adaptation of those findings

Use them this way, not literally:

1. curated AOI registry first
   - exact civilian site
   - fixed capture center
   - fixed size_km override if needed
2. temporal registry second
   - clean pre
   - clean post
   - timestamp-cutoff split once train rows exist
3. row generation third
   - baseline/current image pair
   - strict JSON candidate label
   - optional grounding target for bbox checks
4. human promotion gate last
   - exact parcel
   - honest macro scar
   - no tactical drift

## What this changes for implementation

- do not build custom training infra first
- do export Blackline train/eval rows into one LEAP-compatible VLM SFT format once we have enough train rows
- the exporter path now exists in `training/scripts/export_leap_vlm_sft.py`
- keep our stricter structured eval outside the trainer too:
  - action accuracy
  - schema-valid rate
  - bbox-valid rate
  - false-positive rate
  - `defer` calibration

## Cookbook-specific notes from Liquid's official repo

From `Liquid4All/cookbook`:

1. `examples/satellite-vlm/prepare_vrsbench.py` keeps the trainer row dead simple
   - one `messages` conversation
   - image path
   - text instruction
   - text answer
2. trainer config owns the rest
   - `image_root`
   - eval limits
   - metrics
   - checkpoint cadence
3. grounding uses normalized `0-1` JSON boxes
   - aligned with our current bbox contract
4. benchmark-on-start is worth copying
   - fast signal before wasting a full fine-tune run
5. local computer should act like an orchestrator for heavy jobs
   - prepare
   - launch
   - monitor
   - retrieve artifacts

Blackline adaptation:

- keep `AnnotatedCaseRecord` and frozen replay packs canonical
- materialize trainer rows from that source, never the other way around
- keep small capped eval subsets for quick training iteration
- keep full structured eval as a separate gate after trainer-side metrics
- prioritize food-family widening next because Train 01 is still underweight on inland food positives
