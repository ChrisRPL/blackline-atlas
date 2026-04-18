# Gold Eval Tranche 01

Purpose:

- turn the matrix into concrete next work
- stop ad hoc scouting
- fill the biggest coverage gaps first

## Tranche target

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
  - exact inland food facility still needed
- current best leads:
  - `Star Brands Pavlohrad`
  - `Vasyshcheve ATB distribution center`
- blocker:
  - weather for `Star Brands`
  - soft address-to-scar match for `Vasyshcheve`
- next action:
  - do not force promotion
  - only reopen when either weather clears or a sharper parcel clue appears

### Water

#### `water_01`
- target type:
  - pure treatment plant
- current lead quality:
  - first concrete lead now tracked in `training/replay_pack/water_tranche_01.md`
- next action:
  - source `3` exact-site candidates with clear civilian service role
  - reject mixed power+water unless water-first and macro-visible

#### `water_02`
- target type:
  - pumping station or reservoir compound
- current lead quality:
  - `Bahri Water Station` now landed as an exact water control
- next action:
  - prioritize the next water candidate only if it has obvious basins / tanks / service compounds visible in Sentinel

#### `water_03`
- target type:
  - desalination plant only if clearly water-first
- current lead quality:
  - category seed exists, but exact promoted row does not
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
  - working board:
    - `training/replay_pack/aid_tranche_01.md`
- blocker:
  - current Lebanon lead may be too small for honest Sentinel labeling
- next action:
  - prefer inland WFP / UN / NGO / MSF aid compounds first
  - probe `Tyre Red Cross center` only if compound scale looks real enough
  - priority is now higher because current water-positive hunting remains soft
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

1. keep `water` positive hunt paused after the bounded exact-site pass stayed soft
2. keep `Bahri Water Station` as the exact water control row for this tranche
3. reopen blocked `food` positives now, because the active inland-aid lead still lacks a public parcel
4. only resume `aid_02` when a parcel-tight inland depot survives the stop rules

## Stop rules

- one hard map/geocode pass only per candidate before downgrade
- one honest SimSat pair only if the parcel is exact
- if the site is still ambiguous after that, downgrade and move on
