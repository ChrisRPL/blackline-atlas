# Model Data Strategy — 2026-04-19

Purpose:

- make current data truth explicit
- split VLM data needs from agent-model data needs
- stop mixing image supervision with planner routing work

## Repo state

### VLM / image-lane truth

- `hero_eval.jsonl`: `2`
- `non_demo_eval.jsonl`: `10`
- overall annotated rows: `12`
- non-demo positives: `4`
  - `food`: `2`
  - `aid`: `1`
  - `mobility`: `1`
  - `water`: `0`
- non-demo controls / stress: `6`
  - `water`: `3`
  - `food`: `1`
  - `aid`: `2`
- split shape:
  - `holdout_geo`: `3`
  - `holdout_stress`: `6`
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
  - `training/replay_pack/agent_command_eval.jsonl`: `10`
- current watchlist assets:
  - `12`

Implication:

- planner lane already has deterministic fallback and sanitization
- planner fine-tuning is not the right next move
- planner eval breadth is the real gap

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

- total missing rows: `12`
- missing positives: `8`
  - `food`: `2`
  - `water`: `3`
  - `aid`: `2`
  - `mobility`: `1`
- missing controls / stress: `4`

Most important missing pieces:

1. one exact water positive
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

- expand `agent_command_eval.jsonl` from `10` rows to roughly `60-120`
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

1. `water` positive acquisition
2. planner eval expansion
3. inland aid positive retry only when parcel-tight
4. more controls only as support work

## Current recommendation

- VLM: data-first
- planner: eval-first
- both: no fine-tune rush
