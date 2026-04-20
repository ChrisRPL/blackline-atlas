# Gold Eval Tranche 01

Purpose:

- turn the matrix into concrete next work
- stop ad hoc scouting
- fill the biggest coverage gaps first

## Tranche composition

Open `8` near-term slots:

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
- target type:
  - pumping station or reservoir compound
- current lead quality:
  - `Ayn al-Bayda Water Pumping Station` is the cleanest exact next lead
  - archive blocker is resolved, but plant-scale structural signal is still too soft
- next action:
  - keep as evidence unless a tighter plant-only disruption signal becomes defendable

#### `water_03`
- target type:
  - desalination plant only if clearly water-first
- current lead quality:
  - category now has one exact positive and three exact controls
  - second positive row does not exist yet
  - working memo: `training/replay_pack/water_tranche_01.md`
- next action:
  - use only if plant identity is exact and visual disruption is honest

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
  - exact named humanitarian depot / warehouse cluster
- current lead:
  - `Saudi Teaching Maternal Hospital`, `El Fasher`
  - working board:
    - `training/replay_pack/aid_tranche_01.md`
- blocker:
  - exact parcel is real, but hospital-only Sentinel signal is still too mixed for promotion
- next action:
  - keep `Saudi Teaching Maternal Hospital` as evidence-only unless a tighter hospital-only read emerges
  - keep `El Obeid` blocked unless the ABS complex itself becomes publicly mappable
  - keep `Tyre Red Cross center` as evidence-only unless compound scale becomes obviously warehouse-yard sized
  - keep `Urum al-Kubra` and `Abs hospital` as archive-blocked retrospective backups
  - no current aid lead is promotion-ready again
  - `Mosul Medical City Hospital` now fills one exact inland medical-aid control slot, but not the missing positive slot

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
  - one clearly civilian bridge / causeway only
- current lead:
  - `Qasmiyeh Bridge`
- blocker:
  - sensitivity and visibility
- next action:
  - keep narrow
  - use only if the case remains clearly civilian and macro-visible

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

1. keep `Roshen Yahotyn logistics center` as the best new inland food lead; exact parcel is solved, but the whole post-strike window is cloud-blocked
2. keep `Veggy Trend Invest` on hold; the `Soborna 111/111A` campus still reads too mixed for another probe
3. keep `Novus Logistics Center` on hold unless a clearly better post-strike frame appears than the current January/March pair
4. keep `Wad Medani main water treatment plant` as an exact water evidence lead, but not a promotion until plant-scale change is defendable
5. keep `Ayn al-Bayda Water Pumping Station` reopened as exact evidence, but not as `water_02` until plant-scale damage is defendable
6. use `Okhmatdyt Children's Hospital` as the inland medical-aid anchor while the next aid-positive search runs in parallel
7. keep `Bashtanka Multiprofile Hospital` as the cleanest inland medical backup, but weather-blocked
8. keep `Bahri Water Station` as the exact water control row for this tranche
9. keep the planner eval pack stable at its current widened shape unless watchlist/query breadth grows again

## Stop rules

- one hard map/geocode pass only per candidate before downgrade
- one honest SimSat pair only if the parcel is exact
- if the site is still ambiguous after that, downgrade and move on
