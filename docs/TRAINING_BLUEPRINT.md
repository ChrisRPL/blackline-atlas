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

## Baseline model behavior

The model should do three narrow things:
- ground the relevant region
- answer a constrained operational question
- provide a short rationale

Policy and routing remain deterministic.

## Eval goals

Measure:
- JSON validity
- enum correctness
- bbox validity
- action calibration
- false positives

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
