# Gold Eval Tranche 01

Purpose:

- turn the matrix into concrete next work
- stop ad hoc scouting
- fill the biggest coverage gaps first

## Tranche composition

Original `8`-slot tranche:

- `food`: `2`
- `water`: `3`
- `aid`: `2`
- `mobility`: `1`

This is not the whole gold set.
It is the first acquisition batch with the best chance of moving coverage, not just producing more notes.

## Slot queue

### Food

#### `food_01`
- target:
  - `Beirut Grain Silos`
- role:
  - already landed
  - anchor / benchmark
- status:
  - `done`

#### `food_02`
- target:
  - `Silpo Kvitneve Distribution Center`
- role:
  - already landed
  - current-conflict inland food-distribution anchor
- status:
  - `done`

#### `food_03`
- target:
  - `Roshen Yahotyn Logistics Center`
- role:
  - already landed
  - inland food-distribution anchor
- status:
  - `done`

#### `food_04`
- target:
  - `Mondelez Trostianets Confectionery Factory`
- role:
  - already landed
  - inland food-manufacturing anchor
- status:
  - `done`

### Water

#### `water_01`
- target:
  - `Arbaat Dam`
- role:
  - already landed
  - current-conflict civilian water-source anchor
- status:
  - `done`

#### `water_02`
- target:
  - `Kakhovka Dam`
- role:
  - retrospective major water-source anchor
- status:
  - `done`

#### `water_03`
- target:
  - `Mansour Dam`
- role:
  - retrospective dam-failure water-source anchor
- status:
  - `done`

### Aid

#### `aid_01`
- target:
  - `Port Sudan Aid Hub`
- role:
  - already landed
  - current-conflict humanitarian anchor
- status:
  - `done`

#### `aid_02`
- target:
  - `Khan Younis Training Centre`
- role:
  - already landed
  - humanitarian shelter-campus anchor
- status:
  - `done`
- follow-up board:
  - `training/replay_pack/aid_tranche_01.md`

### Mobility

#### `mobility_01`
- target:
  - `Baltimore Bridge`
- role:
  - already landed
  - benchmark-only
- status:
  - `done`

#### `mobility_02`
- target:
  - `Morandi Bridge`
- role:
  - already landed
  - retrospective civilian bridge-collapse anchor
- status:
  - `done`
- note:
  - `Qasmiyeh Bridge` stays in backlog only as a sensitivity-bound mobility example, not a gold-row target

## Control tranche

Do in parallel with positive cases:

### `control_neg_01` to `control_neg_04`
- same-class no-event controls
- prefer same facility family where possible
- `Gedaref Grain Silos` now fills one exact inland food no-event control slot
- `Manbij Grain Silo Complex` now fills a second exact inland food no-event control slot

### `control_weather_01` to `control_weather_02`
- cloud-heavy or haze-heavy frames
- should prove “don’t trust this”

### `control_ambig_01` to `control_ambig_02`
- nearby disruption, but target parcel not honestly labelable
- `Vasyshcheve` now fills `control_ambig_01`
- keep `control_ambig_02` open for the next exact parcel / nearby-scar mismatch

### `control_stale_01` to `control_stale_02`
- visible non-conflict drift
- construction / seasonal / normal industrial change

## Immediate next work order

External benchmark seeds now exist:

- `internal_public_seed_v0`
- `xbd_public_seed_v0`
- `spacenet8_public_seed_v0`

They are useful for:

- frozen baseline research
- cross-model comparison
- hackathon materials
- first real Liquid cohort proof

Current read:

- internal public seed is benchmark-only, not the full internal slice
- first real Liquid cohort still collapsed on all three ready slices
- that does not change the core tranche order below

They are not replacements for the internal tranche below.

1. freeze the completed `22`-row non-demo gold eval set
2. materialize the local SimSat capture manifest against the frozen pack
3. build the first `lfm25-vl-v1` corpus from that manifest
4. keep `Qasmiyeh Bridge` out of the gold set; use `Morandi Bridge` as the final mobility anchor
5. start the first train-row tranche instead of growing gold coverage further
6. keep the planner eval pack stable at its current widened shape unless watchlist/query breadth grows again

## Closeout

- tranche complete
- the first internal non-demo gold eval set is now frozen at `22` rows
- no new gold-row acquisition unless product scope changes or a frozen row is invalidated
- all new data work moves to [train_tranche_01.md](/Users/krzysztof/blackline-atlas/training/replay_pack/train_tranche_01.md)
- the next useful pressure is train-row promotion, not more gold coverage

## Stop rules

- one hard map/geocode pass only per candidate before downgrade
- one honest SimSat pair only if the parcel is exact
- if the site is still ambiguous after that, downgrade and move on
