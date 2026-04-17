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
  - no promoted candidate yet
- next action:
  - source `3` exact-site candidates with clear civilian service role
  - reject mixed power+water unless water-first and macro-visible

#### `water_02`
- target type:
  - pumping station or reservoir compound
- current lead quality:
  - no promoted candidate yet
- next action:
  - prioritize assets with obvious basins / tanks / service compounds visible in Sentinel

#### `water_03`
- target type:
  - desalination plant only if clearly water-first
- current lead quality:
  - category seed exists, but exact promoted row does not
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
  - `Tyre Red Cross center`
- blocker:
  - may be too small for honest Sentinel labeling
- next action:
  - probe only if compound scale looks real enough
  - otherwise replace with a larger WFP / UN / NGO warehouse asset

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
- `Vasyshcheve` is a good shape for this class

### `control_stale_01` to `control_stale_02`
- visible non-conflict drift
- construction / seasonal / normal industrial change

## Immediate next work order

1. exact-site `water` longlist
2. exact-site `aid` longlist
3. control rows from already-known ambiguous / weather-blocked cases
4. only then reopen blocked `food` leads

## Stop rules

- one hard map/geocode pass only per candidate before downgrade
- one honest SimSat pair only if the parcel is exact
- if the site is still ambiguous after that, downgrade and move on
