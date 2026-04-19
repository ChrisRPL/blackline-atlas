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
  - blocker is still missing honest pre-event archive coverage
- next action:
  - reopen only if a real pre-event baseline appears

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
  - exact parcel is now real, but hospital-only damage still needs an honest Sentinel read
- next action:
  - do one bounded bbox review on `Saudi Teaching Maternal Hospital`
  - keep `El Obeid` blocked unless the ABS complex itself becomes publicly mappable
  - keep `Tyre Red Cross center` as evidence-only unless compound scale becomes obviously warehouse-yard sized
  - keep `Urum al-Kubra` and `Abs hospital` as archive-blocked retrospective backups
  - this stays the next open positive gap unless `Saudi Hospital` proves too mixed or too soft
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

1. finish the bounded `aid_02` review on `Saudi Teaching Maternal Hospital`
2. keep `Ayn al-Bayda Water Pumping Station` as the second-water lead only if archive baseline truth improves
3. keep `Bahri Water Station` as the exact water control row for this tranche
4. if `Saudi Hospital` downgrades, add one more inland food positive/control pair before more prompt churn
5. expand planner eval before any agent-model fine-tune dataset work

## Stop rules

- one hard map/geocode pass only per candidate before downgrade
- one honest SimSat pair only if the parcel is exact
- if the site is still ambiguous after that, downgrade and move on
