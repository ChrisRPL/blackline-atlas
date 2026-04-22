# Train Tranche 01

Purpose:

- move from frozen gold eval to first real train-lane acquisition
- keep the `22`-row gold eval set fixed
- build the first honest `40-80` train rows without temporal leakage

## Current status

- promoted train rows: `23`
- current mix:
  - positives: `14`
  - controls: `9`
- promoted dataset:
  - [train_01.jsonl](/Users/krzysztof/blackline-atlas/training/replay_pack/train_01.jsonl)
- first active families with real rows:
  - `Baltimore Bridge`
  - `Beirut Grain Silos`
  - `Morandi Bridge`
  - `Kakhovka Dam`
  - `Khan Younis Training Centre`
  - `Port Sudan Aid Hub`
  - `Ras Abu Jarjur`
  - `Doha West`
  - `Bahri Water Station`
  - `Kramatorsk Filtration Station`
  - `Trostianets City Hospital`
  - `UNHCR Baghdad Warehouse`
  - `Okhmatdyt Children's Hospital`
  - `Gedaref Grain Silos`
  - `Manbij Grain Silo Complex`
  - `Vasyshcheve ATB Distribution Center`
  - `Mondelez Trostianets Confectionery Factory`
- still blocked / not yet promotable:
  - `Roshen Yahotyn Logistics Center`
  - `Arbaat Dam`

## Rule first

- do not mutate `training/replay_pack/non_demo_eval.jsonl`
- gold stays eval-only
- train rows live in a separate train dataset once they are promoted
- no random split
- use timestamp cutoffs and fixed site families

## First target

- target train rows: `48`
- minimum acceptable range: `40-80`

Composition:

- positive-family rows: `36`
  - `12` exact positive anchor families
  - `3` non-gold temporal or crop variants per family
- control / defer rows: `12`
  - exact control families
  - weather-limited reads
  - ambiguity traps

## Positive anchor families

### Food

- `Beirut Grain Silos`
- `Silpo Kvitneve Distribution Center`
- `Roshen Yahotyn Logistics Center`
- `Mondelez Trostianets Confectionery Factory`

### Water

- `Arbaat Dam`
- `Kakhovka Dam`
- `Mansour Dam`

### Aid

- `Port Sudan Aid Hub`
- `Okhmatdyt Children's Hospital`
- `Khan Younis Training Centre`

### Mobility

- `Baltimore Bridge`
- `Morandi Bridge`

## Control families

- `Ras Abu Jarjur`
- `Doha West`
- `Bahri Water Station`
- `Kramatorsk Filtration Station`
- `Vasyshcheve ATB Distribution Center`
- `Gedaref Grain Silos`
- `Manbij Grain Silo Complex`
- `UNHCR Baghdad Warehouse`
- `Mosul Medical City Hospital`
- `Trostianets City Hospital`

## Acquisition pattern

For each positive family:

1. keep the gold pair out of train
2. collect `2-3` additional temporal variants
3. prefer one cleaner variant and one harder-but-honest variant
4. keep the same exact parcel center unless a tighter crop is truly needed

For each control family:

1. collect at least one clean no-event or signal-soft variant
2. prefer timestamp distance from gold rows
3. keep weather and ambiguity examples explicit

## Split policy

- gold eval remains:
  - `dev`
  - `holdout_geo`
  - `holdout_stress`
- new train rows:
  - `train`
- train vs eval separation:
  - timestamp cutoff
  - no near-duplicate frames across splits

## Family scaling rule

- scale by family depth, not by random new leads
- positive family:
  - require at least `2` honest non-gold train windows on the same exact parcel
  - a `3rd` variant is optional if it adds a harder-but-honest read
- control family:
  - require `1` clean no-event or signal-soft variant
  - add a `2nd` only if it adds a distinct failure mode
- same exact parcel center
- capture changes belong in overrides and family policy, not in the row JSONL
- lead-registry or current web ingest never enters VLM train rows directly

## Export path

Use the same frozen candidate corpus shape first, then export it to LEAP-compatible VLM SFT:

1. `training/scripts/build_lfm25_vl_corpus.py`
2. `training/scripts/export_leap_vlm_sft.py`

This keeps one canonical row family for:

- prompted eval
- benchmark
- later LEAP fine-tune

## Immediate next work

1. widen inland `food` next, not another bridge or port family
2. keep `Roshen` blocked until a genuinely non-gold clean pair exists
3. use `Arbaat` as the water backup lane only if a non-gold pre-event pair appears
4. hold `Khan Younis` until a genuinely non-gold clean pair exists
5. first `12`-row train mini-pack is closed; current pack is `23`, and the next push should prefer under-depth food families or a fresh non-leaky control
