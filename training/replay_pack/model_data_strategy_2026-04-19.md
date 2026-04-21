# Model Data Strategy — 2026-04-19

Purpose:

- make current data truth explicit
- split VLM data needs from agent-model data needs
- stop mixing image supervision with planner routing work

## Repo state

### VLM / image-lane truth

- `hero_eval.jsonl`: `2`
- `non_demo_eval.jsonl`: `22`
- overall annotated rows: `24`
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
  - `train`: `0`

Implication:

- VLM eval lane is real
- first gold eval set is complete
- VLM train lane does not exist yet
- adapter tuning is still premature

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

First gold-set target stays:

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

Most important next pieces:

1. freeze the finished `22`-row gold eval set
2. materialize the first local capture manifest and train-prep corpus from that frozen set
3. start the first real train tranche after the gold eval set is no longer tiny

## What the agent model still needs

Do not build a fine-tune dataset yet.

Reason:

- the planner is plan-only, not answer-generation
- backend already owns truth, ranking, trust, evidence, and replay/live state
- current failure modes are better handled by eval growth than by training

What is needed now instead:

- expand `agent_command_eval.jsonl` from `30` rows to roughly `60-120`
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

- training row should be:
  - watchlist context
  - selected asset context
  - user query
  - expected `AtlasAgentPlan` JSON only
- not image pairs
- not alert candidates
- not final natural-language answers

## Next data order

1. count `Mondelez Trostianets Confectionery Factory` as the fourth exact food positive and stop spending more bounded time on `food_04`
2. count `Morandi Bridge` as the second exact mobility positive and stop pushing `Qasmiyeh Bridge`
3. freeze the gold eval pack at `22` non-demo rows
4. materialize the local SimSat capture manifest and first `lfm25-vl-v1` corpus
5. open the first train-row tranche toward `40-80` rows while leaving the gold pack stable
6. planner eval expansion only after watchlist/query breadth grows again

## Current recommendation

- VLM: freeze gold eval, then data-first toward train rows
- planner: eval-first
- both: no fine-tune rush

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
- keep our stricter structured eval outside the trainer too:
  - action accuracy
  - schema-valid rate
  - bbox-valid rate
  - false-positive rate
  - `defer` calibration
