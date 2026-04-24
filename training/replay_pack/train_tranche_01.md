# Train Tranche 01

Purpose:

- move from frozen gold eval to first real train-lane acquisition
- keep the `22`-row gold eval set fixed
- build the first honest `40-80` train rows without temporal leakage

## Current status

- promoted train rows: `30`
- current mix:
  - positives: `21`
  - controls: `9`
- promoted dataset:
  - [train_01.jsonl](/Users/krzysztof/blackline-atlas/training/replay_pack/train_01.jsonl)
- first active families with real rows:
  - `Al-Ahli Arab Hospital`
  - `Arbaat Dam`
  - `Mansour Dam`
  - `Baltimore Bridge`
  - `Beirut Grain Silos`
  - `European Gaza Hospital`
  - `Morandi Bridge`
  - `Kakhovka Dam`
  - `Khan Younis Training Centre`
  - `Port Sudan Aid Hub`
  - `Ras Abu Jarjur`
  - `Silpo Kvitneve Distribution Center`
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

## 2026-04-23 live SimSat recheck

- `Roshen Yahotyn Logistics Center`
  - exact non-gold pre still not honest enough
  - `2025-11-14T08:56:33Z` came back with `32.921478` cloud
  - `2026-03-14T08:56:26Z` stayed the best clean current at `1.198145` cloud
  - result: keep blocked
- `Mondelez Trostianets Confectionery Factory`
  - clean extra pre exists:
    - `2021-10-01T08:56:15Z` with `0.001587` cloud
  - most of the extra current side stayed too compromised:
    - `2022-04-04T08:56:17Z` with `32.389462` cloud
    - `2022-05-19T08:56:15Z` with `25.729567` cloud
  - one later clean current cleared the bar:
    - `2022-08-24T08:46:19Z` with `0` cloud
  - result: promoted as a second internal train variant
- `Silpo Kvitneve Distribution Center`
  - one non-gold train pair cleared the bar:
    - baseline `2021-09-14T09:06:21Z` with `7.622002` cloud
    - current `2022-04-07T09:06:26Z` with `22.338516` cloud
  - the April frame still shows a defendable warehouse-scale scar versus the intact September 2021 baseline
  - result: promoted as a second internal food-distribution train variant
- `Okhmatdyt Children's Hospital`
  - near-event pre side remains weather-blocked:
    - `2024-04-14T09:16:24Z` with `98.655981` cloud
    - `2024-05-14T09:16:22Z` with `88.792944` cloud
    - `2024-05-29T09:16:25Z` with `93.978631` cloud
  - later current side is still readable:
    - `2024-08-14T09:06:28Z` with `8.936304` cloud
    - `2024-09-28T09:06:27Z` with `6.686892` cloud
  - result: existing `2024-05-01 -> 2024-09-06` train row remains the best honest variant
- `Port Sudan Aid Hub`
  - family depth is already sufficient at `3` train variants
  - new probe confirmed one more readable current:
    - `2025-06-24T08:14:53Z` with `9.246881` cloud
  - result: do not widen further unless a materially different failure mode appears
- `Novus Logistics Center`
  - one last bounded late-April pass did not rescue the site:
    - `2026-04-10` -> `2026-04-09T09:16:20Z` with `99.702668` cloud
    - `2026-04-20` -> `2026-04-19T09:16:23Z` with `56.211323` cloud
    - `2026-04-24` -> `2026-04-21T09:16:41Z` with `97.702181` cloud
  - result: keep on hold; no honest row
- `European Gaza Hospital`
  - second clean non-gold current is now promotable:
    - `2025-05-21T08:31:47Z` with `0.244382` cloud
  - the May frame already shows broad campus scarring versus the intact `2021-04-30T08:31:29Z` baseline
  - result: promoted as a second internal train variant
- `Arbaat Dam`
  - bounded pre-event sweep finally found the missing non-gold baseline:
    - `2024-06-20T08:00:00Z` -> `2024-06-17T08:14:47Z` with `0` cloud
  - later clean current also cleared the train bar:
    - `2024-10-20T08:00:00Z` -> `2024-10-15T08:14:42Z` with `2.463562` cloud
  - the October frame still shows the drained-reservoir / breach morphology versus the intact June 2024 baseline
  - result: promoted as the first internal water-family train variant
- `Mansour Dam`
  - one earlier non-gold baseline cleared the leakage bar:
    - `2023-08-20T09:21:00Z` -> `2023-08-18T09:21:27Z` with `3.153944` cloud
  - one later non-gold current stayed readable:
    - `2023-11-15T09:21:00Z` -> `2023-11-11T09:21:21Z` with `16.155596` cloud
  - the mid-November frame still shows the same blown-out breach and widened flood-corridor morphology versus the intact late-August baseline
  - result: promoted as a second internal water-family train variant
- `Al-Ahli Arab Hospital`
  - `2025-05-11T08:31:44Z` is clean, but too close to the existing May row to add a new failure mode
  - result: keep single-row family depth for now

## Rule first

- do not mutate `training/replay_pack/non_demo_eval.jsonl`
- gold stays eval-only
- train rows live in a separate train dataset once they are promoted
- no random split
- use timestamp cutoffs and fixed site families
- current-source lead intake stays separate from train promotion
- for active conflict facilities, try a before-war baseline if near-event pre frames stay weak

## Auxiliary lane

- auxiliary-train rows are allowed
- keep them out of core Blackline gold metrics
- current first sources:
  - `xBD`
  - `SpaceNet 8`
  - `KOlegaBB/damage_assessment_ukraine`
- current auxiliary pool, after materialization:
  - `248` train rows
- current practical trainer-side pool:
  - raw row math: `30` internal + `248` auxiliary = `278`
  - current LEAP-exportable train records: `278`
- materialize them through:
  - `python3 training/scripts/materialize_aux_train_slice.py`
- rule:
  - same canonical `blackline_candidate_eval.jsonl` row shape
  - copied local images
  - split forced to `train`
  - separate from internal gold / holdout reporting

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

Current trainer path:

1. `training/scripts/train_adapter.py`
2. `training/scripts/run_train_backend.py`
3. `training/scripts/submit_train_backend_hf_job.py`

Rule:

- local machine prepares and bundles
- HF GPU runs the actual trainer
- frozen Blackline eval stays outside the trainer

## Immediate next work

1. keep widening under-depth internal positive families
2. keep `Roshen` blocked until a genuinely non-gold clean pre appears
3. keep `Mondelez` warm, but only promote a new row if the current side is cleaner than the `2022-04-04` and `2022-05-19` reads
4. keep `Arbaat` and `Mansour` warm only if another non-gold current adds a new honest failure mode
5. keep `Khan Younis` and `Okhmatdyt` strict on leakage and weather
6. materialize the first auxiliary-train slice from checked-in `xBD` and `SpaceNet 8` public seeds
7. merge auxiliary gain only in trainer-side runs, never in the frozen Blackline scorecard
8. treat `Nasser` as soft-stopped after the long-range recheck; do not spend more internal time there without a clearly better parcel read
9. widen auxiliary train aggressively with public Ukraine building-damage rows before spending more bounded time on soft internal candidates
10. keep `Novus Logistics Center` as the next internal exact-site retry once aux widening stops being the highest-ROI move
11. next public-source scouts, after Ukraine:
  - `WayBob/Disaster_Recognition_RemoteSense_EN_CN_JA` for xBD-derived widening
  - `Sen1Floods11` for flood-heavy auxiliary transfer rows
