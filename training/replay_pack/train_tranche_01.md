# Train Tranche 01

Purpose:

- move from frozen gold eval to first real train-lane acquisition
- keep the `22`-row gold eval set fixed
- build the first honest `40-80` train rows without temporal leakage

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

## Export path

Use the same frozen candidate corpus shape first, then export it to LEAP-compatible VLM SFT:

1. `training/scripts/build_lfm25_vl_corpus.py`
2. `training/scripts/export_leap_vlm_sft.py`

This keeps one canonical row family for:

- prompted eval
- benchmark
- later LEAP fine-tune

## Immediate next work

1. start with `Mondelez`, `Morandi`, `Roshen`, and `Kakhovka`
2. collect non-gold timestamp variants only
3. promote the first `8-12` train rows
4. then widen to the rest of the frozen positive families
