# Gold Eval Acquisition Matrix

Use this to grow `training/replay_pack/non_demo_eval.jsonl` from a tiny demo-adjacent pack into a defensible civilian-lifeline eval set.

## Current truth

- demo/smoke rows:
  - `hero_eval.jsonl`: `2`
- real/manual non-demo rows:
  - `non_demo_eval.jsonl`: `6`
- current real positive non-demo mix:
  - `food`: `1` (`Beirut Grain Silos`)
  - `aid`: `1` (`Port Sudan Aid Hub`)
  - `mobility`: `1` (`Baltimore Bridge`)
  - `water`: `0`
- current non-demo controls / stress rows:
  - `water`: `2`
    - `Ras Abu Jarjur`
    - `Doha West`
  - `food`: `1`
    - `Vasyshcheve ATB Distribution Center`
- overall annotated rows:
  - `8`
- current split shape:
  - `holdout_geo`: `4`
  - `dev`: `1`
  - `holdout_stress`: `3`
  - `train`: `0`
- train rows:
  - `0`

This means the pipeline is mostly ready, but the dataset is still far too small and skewed to represent the app’s intended civilian use.

## Goal

Build one first-pass gold eval set that is:

- small enough to finish
- broad enough to cover the app’s main civilian use
- strict enough that later training will mean something

## Gold set shape

### Core rows: `12`

- `food`: `4`
- `water`: `3`
- `aid`: `3`
- `mobility`: `2`

Rule:
- no category is considered covered until it has at least `2` exact-parcel rows

### Controls: `10`

- hard negatives: `4`
  - same asset class, no disruption
- weather controls: `2`
  - cloud / haze / low-trust visual conditions
- ambiguity controls: `2`
  - nearby strike, smoke, or disturbance, but target parcel itself not honestly labelable
- stale-change controls: `2`
  - visible difference from non-conflict drift, construction, or normal operations

### Total first gold set: `22`

## Category rules

### Food

Preferred asset classes:

- grain silos
- flour mills
- cold storage
- city-serving food warehouses

Why first:

- strongest civilian-value story
- often macro-visible in Sentinel
- lower tactical drift than bridges and transport

### Water

Preferred asset classes:

- pure treatment plants
- pumping stations
- reservoir / basin compounds
- desalination plants only when clearly water-first

Why second:

- very high civilian value
- strong public-interest framing
- fills the biggest current gap

### Aid

Preferred asset classes:

- aid warehouse clusters
- Red Cross / UN / WFP depots
- refugee / relief supply hubs

Why third:

- high humanitarian value
- good fit for public accountability
- currently under-covered

### Mobility

Preferred asset classes:

- clearly civilian bridges
- ferry nodes
- causeways serving population access

Why last:

- useful
- but tactical drift risk is highest
- keep narrow and benchmark-only

## Gold row gates

A case becomes a gold row only if all of these are true:

1. exact parcel
   - named civilian facility
   - stable coordinates
   - no village-level guesswork
2. clear civilian function
   - obvious in one sentence
   - food / water / aid / civilian mobility
3. Sentinel-legible footprint
   - roofs, silos, yards, basins, or large compounds
   - not tiny-building semantics
4. honest pre/post pair
   - no tile-edge weirdness
   - no fake date reuse
   - no “best we have” if the post frame is actually pre-event
5. macro-visible change
   - burn scar
   - roof loss
   - collapse
   - yard-scale destruction
   - basin / compound disruption
6. human-defensible label
   - explainable in under `10s`
   - another reviewer could defend it from the images + sources

## Red lines

Reject immediately:

- mixed-use logistics compounds
- rail yards / freight terminals
- border warehouses
- crossings / convoy-route assets
- ports unless tightly cropped to food or aid function
- fuel, oil, power, telecom
- airports / airbases / military-adjacent parcels
- broad city AOIs instead of named facilities
- anything where Sentinel cannot show an honest macro change

Rule:
- keep if it answers `did a civilian lifeline get disrupted?`
- reject if it answers `how is movement, routing, or sustainment working?`

## Acquisition workflow

For every candidate:

1. source lock
   - at least `2` credible public references if possible
   - event date and facility role pinned
2. parcel lock
   - exact address, coordinates, or defendable map clue
3. SimSat probe
   - one clean baseline
   - one clean post-event frame
4. visibility check
   - macro-visible or reject
5. label draft
   - candidate action
   - bbox
   - civilian impact
   - why
6. control pairing
   - same class or same facility, no-event or ambiguous counterpart

## What counts right now

Counts toward the future gold set:

- `Beirut Grain Silos`
- `Port Sudan Aid Hub`
- `Baltimore Bridge`

Do not count toward gold coverage:

- `hero_eval.jsonl`
  - demo/smoke only
- unresolved backlog holds
  - not coverage

## Immediate implication

The next acquisition push should not chase more food-only cases blindly.

Better order now:

1. fill `water`
2. fill `aid`
3. keep `food` alive only where exact parcel + honest visibility already exist
4. use already-scouted ambiguity and weather cases to widen control coverage while positive rows remain blocked
5. keep `mobility` narrow
