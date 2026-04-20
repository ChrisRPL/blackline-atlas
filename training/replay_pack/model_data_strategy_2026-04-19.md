# Model Data Strategy — 2026-04-19

Purpose:

- make current data truth explicit
- split VLM data needs from agent-model data needs
- stop mixing image supervision with planner routing work

## Repo state

### VLM / image-lane truth

- `hero_eval.jsonl`: `2`
- `non_demo_eval.jsonl`: `17`
- overall annotated rows: `19`
- non-demo positives: `7`
  - `food`: `3`
  - `aid`: `2`
  - `mobility`: `1`
  - `water`: `1`
- non-demo controls / stress: `10`
  - `water`: `4`
  - `food`: `3`
  - `aid`: `3`
- split shape:
  - `holdout_geo`: `6`
  - `holdout_stress`: `10`
  - `dev`: `1`
  - `train`: `0`

Implication:

- VLM eval lane is real
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
  - `19`

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

- total missing rows: `5`
- missing positives: `5`
  - `food`: `1`
  - `water`: `2`
  - `aid`: `1`
  - `mobility`: `1`
- missing controls / stress: `0`

Most important missing pieces:

1. one second exact water positive
2. one second aid positive with inland parcel lock
3. more exact positive anchors before any adapter prep
4. first real train split after the gold eval set is no longer tiny

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

1. count `Roshen Yahotyn Logistics Center` as the new third inland food positive and stop spending time on it
2. keep `Okhmatdyt Children's Hospital` as the inland medical-aid anchor
3. keep `Wad Medani main water treatment plant` as exact water evidence, but not as a second water positive until the signal is honest
4. keep `Ayn al-Bayda Water Pumping Station` reopened as evidence, but not as a second water positive until the signal is honest
5. count `Trostianets City Hospital` as the third exact medical-aid control and stop spending more bounded review on it
6. keep `Bashtanka Multiprofile Hospital` as the strongest remaining inland medical backup board, but not a promotion-ready row
7. keep `Veggy Trend Invest` on hold; the Soborna `111/111A` campus is still too mixed for a defendable parcel read
8. keep `Novus Logistics Center` on hold unless a clearly better post-strike frame appears
9. planner eval expansion only after watchlist/query breadth grows again

## Current recommendation

- VLM: data-first
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
