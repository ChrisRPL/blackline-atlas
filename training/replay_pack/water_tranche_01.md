# Water Tranche 01

Purpose:

- fill the biggest category gap in the gold eval plan
- turn scattered water probes into one bounded acquisition lane
- promote only city-serving civilian water sites with honest Sentinel-scale signal

## Current water truth

- promoted water rows: `0`
- strongest existing evidence:
  - `Doha West` -> exact site, but clouded + mixed-use
  - `Ras Abu Jarjur` -> exact site, but no honest macro-visible change
  - `Babiri` -> strong civilian story, but service-outage framing and parcel still soft
  - `Maisat / Wazzani` -> strong source trail, but border-sensitive and still too soft for a first positive row
  - `Bahri` -> exact coords + clean windows, but dense urban fabric blocked the hard parcel-tight pass

Rule:
- the next water row should be a `facility`, not a `city`
- visible physical disruption, not only service interruption

## Promotion candidates

### `water_01` Bahri Water Treatment Plant

- country:
  - `Sudan`
- type:
  - pure treatment plant
- why:
  - explicit city-serving drinking-water plant for Khartoum North / Bahri
  - large Nile-edge footprint, better user value than another border utility
  - strong public reporting of war damage
- parcel state:
  - exact lead exists at `15.6169, 32.5347`
  - source trail calls this the `Khartoum State Water Corporation Bahri Station`
- probe truth:
  - clean Sentinel windows already confirmed:
    - pre request `2023-12-01T08:00:00Z` -> returned `2023-11-28T08:25:46Z` with `0.000982` cloud
    - mid request `2024-12-01T08:00:00Z` -> returned `2024-11-27T08:25:47Z` with `0.001288` cloud
    - post request `2025-03-29T08:00:00Z` -> returned `2025-03-27T08:26:11Z` with `0.0025` cloud
  - first `3.0 km` and `1.5 km` sweeps at the lead coordinates did not yet isolate one defendable plant-compound scar inside the dense urban fabric
  - follow-up `0.8 km` parcel-tight `3x3` grid around the lead still failed to isolate a clean treatment-plant footprint honest enough for promotion
- status:
  - `hold_dense_urban_fabric`
- next action:
  - do not spend more time unless a stronger plant polygon or independent parcel anchor appears
- sources:
  - [Sudan Tribune on heavy damage to Bahri water station](https://sudantribune.com/archives/296726)
  - [Wikimapia lead for Khartoum State Water Corporation Bahri Station](https://wikimapia.org/891493/Khartoum-State-Water-Corporation-Bahri-Station)

### `water_02` Kosti New Water Treatment Plant (JICA)

- country:
  - `Sudan`
- type:
  - pure treatment plant
- why:
  - explicit city-serving drinking-water role
  - cholera-linked civilian impact after attack-driven outage
  - cleaner humanitarian story than mixed utility sites
- parcel state:
  - named facility is clear
  - exact parcel still needs one hard geocode / map pass
- status:
  - `active_exact_geocode`
- next action:
  - lock exact parcel from JICA + local-source naming
  - only then run the first SimSat probe
- sources:
  - [AP on Kosti water-supply facility outage and cholera surge](https://apnews.com/article/47ac3f39c10eb549785c7fc24608551a)
  - [JICA project page for the Kosti water-treatment plant](https://www.jica.go.jp/english/our_work/social_environmental/id/africa/sudan/c8h0vm00009u5bwh.html)
  - [Sudan Events on Kosti new drinking-water station / JICA](https://sudanevents.com/index.php/2024/08/16/resumption-of-operations-at-the-new-drinking-water-station-in-kosti/)

### `water_03` Al-Khafsa Water Treatment Plant

- country:
  - `Syria`
- type:
  - pure treatment plant
- why:
  - one of Aleppo's main drinking-water sources
  - explicit city-scale civilian value
  - public reporting says the station's main building was partially damaged on `2025-02-23`
- source-backed role:
  - UNICEF and ICRC both describe Al-Khafsa as a main water source for Aleppo
- parcel state:
  - named facility is clear
  - hard map pass found a treatment-like compound south of Al-Khafsa town around `36.1839511, 38.0086273`
  - clue quality is still imperfect because the public map tag is only `man_made=wastewater_plant`
- why this is the best next positive hunt:
  - pure water semantics
  - big enough footprint
  - stronger structural-damage story than outage-only water cases
- next action:
  - bounded probe was run and should not be promoted as a positive row
  - clean `2.0 km` pair:
    - baseline request `2025-01-30T08:00:00Z` -> returned `2025-01-26T08:20:27Z` with `0.009107` cloud
    - current request `2025-03-15T08:00:00Z` -> returned `2025-03-12T08:20:01Z` with `0.006421` cloud
  - result:
    - no honest macro-visible disruption on the compound in the clean pair
    - wider `5.0 km` crop also suffered tile-edge / no-data artifacts
  - keep as ambiguity evidence only unless a stronger parcel lock or clearer structural change appears
- sources:
  - [UNICEF on Al-Khafsa treatment plant serving Aleppo](https://www.unicef.org/syria/stories/unicef-rehabilitates-conflict-damaged-sedimentation-tanks-enhance-production-treated-water)
  - [ICRC on Al-Khafsa water station role](https://www.icrcnewsroom.org/story/en/2058/syria-urgent-action-needed-to-address-humanitarian-needs)
  - [SNHR on `2025-02-23` damage to Al-Khafsa station main building](https://news.snhr.org/2025/02/24/sdf-bomb-a-water-station-in-e-aleppo-february-23-2025/)

### `water_04` Babiri Pumping Station

- country:
  - `Syria`
- type:
  - pumping station
- why:
  - repeatedly described as the main source feeding Aleppo and surrounding countryside
  - strong user-value story: millions lose water if this site stops
- parcel state:
  - named site is clear
  - exact parcel still soft
  - location clue: eastern Aleppo countryside, near Deir Hafer / Maskana axis
- blocker:
  - current `2026` reporting is mostly about pumping stoppage and restoration
  - still not a clean structural-damage case
- status:
  - `hold_service_outage_until_structural_signal`
- next action:
  - only continue if one exact parcel clue appears or imagery shows clear compound damage
- sources:
  - [SANA on Babiri cutoff affecting Aleppo](https://sana.sy/en/syria/2289847/)
  - [Anadolu on Babiri serving Aleppo city and countryside](https://www.aa.com.tr/en/middle-east/sdf-cuts-water-supply-to-syria-s-aleppo/3796034)
  - [Levant24 on Babiri restoration and field inspection](https://levant24.com/news/2026/01/syria-boosts-water-security-through-major-infrastructure-projects/)

### `water_05` Southern Gaza Seawater Desalination Plant

- country:
  - `Gaza`
- type:
  - desalination plant
- why:
  - large civilian drinking-water role
  - serves central and southern Gaza / displacement areas
  - useful for user-facing crisis framing
- parcel state:
  - named facility is clear
  - exact site is known at Deir al-Balah level
- blocker:
  - current public evidence is mainly electricity-line / cable damage and output collapse
  - not yet an honest plant-structure damage story
- status:
  - `hold_structural_visibility`
- next action:
  - keep only if damage at the plant or immediately associated service compound becomes macro-visible
- sources:
  - [AP on electricity cutoff affecting Gaza desalination plant](https://apnews.com/article/ba90f0de3d4f64a1762d1a39f787817f)
  - [UNICEF on March 2026 cable damage and 80 per cent output drop](https://www.unicef.org/sop/stories/unicef-restores-water-access-tens-thousands-children-gaza)
  - [UN/UNICEF on Southern Gaza Seawater Desalination Plant identity](https://www.un.org/unispal/document/eu-and-unicef-mark-completion-of-expansion-of-the-southern-gaza-seawater-desalination-plant-press-release/)

## Control candidates

### `control_ambig_water_01` Ras Abu Jarjur Desalination Plant

- country:
  - `Bahrain`
- type:
  - desalination plant
- why useful:
  - exact pure-water site
  - pair already usable
  - current review showed no honest macro-visible disruption for bbox labeling
- use:
  - ambiguity control
  - prove that public claims do not force a positive label
- status:
  - promoted to `training/replay_pack/non_demo_eval.jsonl`
- linked source:
  - [AP on Gulf desalination risk and Bahrain damage claim](https://apnews.com/article/12b23f2fa26ed5c4a10f80c4077e61ce)

### `control_weather_water_01` Doha West Power And Desalination Plant

- country:
  - `Kuwait`
- type:
  - power + desalination complex
- why useful:
  - exact site
  - current-side weather was bad
  - mixed-use sensitivity also blocks promotion
- use:
  - weather control
  - mixed-use rejection example
- status:
  - promoted to `training/replay_pack/non_demo_eval.jsonl`
- linked source:
  - [AP on Doha West damage report](https://apnews.com/article/12b23f2fa26ed5c4a10f80c4077e61ce)

## Keep out

### Maisat / Wazzani water-project lane

- why out for tranche 01:
  - report evidence is strong, but first parcel pass is still too soft
  - border sensitivity is too high for the first clean water-positive lane
  - first `1.5 km` SimSat sweep around `Maisat` / `Wazzani` clues used:
    - pre request `2024-01-25T08:00:00Z` -> returned `2024-01-20T08:30:58Z` with `8.311412` cloud
    - post request `2025-03-15T08:00:00Z` -> returned `2025-03-10T08:31:22Z` with `26.562682` cloud
  - keep as evidence and possible retrospective benchmark, not the first promoted water row

### Qeshm Island desalination lane

- why out:
  - too close to Hormuz strategic sensitivity
  - drifts toward regional war / chokepoint intelligence
  - wrong lane for first Blackline water set

## Immediate next work order

1. do one exact geocode pass on `Kosti JICA`
2. keep `Bahri` on hold unless a stronger parcel anchor appears
3. keep `Ras Abu Jarjur` and `Doha West` as the first real water controls
4. keep `Maisat / Wazzani` as evidence only for now
5. only then reopen `Babiri` or `Southern Gaza`
