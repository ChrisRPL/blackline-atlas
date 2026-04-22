# Water Tranche 01

Purpose:

- fill the biggest category gap in the gold eval plan
- turn scattered water probes into one bounded acquisition lane
- promote only city-serving civilian water sites with honest Sentinel-scale signal

## Current water truth

Prompted-baseline gate, `2026-04-18`:

- frozen non-demo corpus: `10` cases
- `LiquidAI/LFM2.5-VL-450M` after prompt/parser hardening:
  - pass rate: `6 / 10`
  - false positives: `0`
- important read:
  - all `4` real positive anchors were still discarded
  - water was the biggest civilian-usefulness gap
- the lane now has its third exact positive and no longer needs more bounded water churn for tranche-01 coverage

- promoted water rows: `3`
- exact promoted water rows:
  - `Arbaat Dam`
  - `Kakhovka Dam`
  - `Mansour Dam`
- exact water controls:
  - `Ras Abu Jarjur`
  - `Doha West`
  - `Bahri Water Station`
  - `Kramatorsk Filtration Station`
- strongest existing evidence:
  - `Doha West` -> exact site, but clouded + mixed-use
  - `Ras Abu Jarjur` -> exact site, but no honest macro-visible change
  - `Al-Arshani` -> exact public coords, but no defendable plant-scale structural change in bounded SimSat pass
  - `Babiri` -> strong civilian story, but service-outage framing and parcel still soft
  - `Maisat / Wazzani` -> strong source trail, but border-sensitive and still too soft for a first positive row
  - `Bahri` -> now promoted as an exact no-material-change control, not a positive row

Rule:
- the next water row should be a `facility`, not a `city`
- visible physical disruption, not only service interruption

## Active shortlist after `2026-04-19` planning pass

### `water_07` Arbaat Dam

- country:
  - `Sudan`
- type:
  - dam / reservoir water source
- why:
  - main potable-water source system for Port Sudan
  - strong civilian dependence, low tactical drift
  - breach / reservoir-shape change is exactly the kind of macro signal the lane needs
- parcel state:
  - exact public lead:
    - `19.833554, 36.941204`
- final SimSat truth:
  - baseline request `2024-07-20T08:00:00Z` -> returned `2024-07-17T08:14:43Z` with `13.07416` cloud
  - post sweep:
    - request `2024-08-24T08:00:00Z` -> returned `2024-08-21T08:14:42Z` with `75.901413` cloud
    - request `2024-08-30T08:00:00Z` -> returned `2024-08-26T08:14:40Z` with `18.400928` cloud
    - request `2024-09-05T08:00:00Z` -> returned `2024-08-31T08:14:44Z` with `13.812824` cloud
    - request `2024-09-12T08:00:00Z` -> returned `2024-09-10T08:14:44Z` with `38.68123` cloud
    - request `2024-09-20T08:00:00Z` -> returned `2024-09-15T08:14:41Z` with `6.886818` cloud
    - request `2024-10-05T08:00:00Z` -> returned `2024-09-30T08:14:43Z` with `0.018271` cloud
    - request `2024-10-20T08:00:00Z` -> returned `2024-10-15T08:14:42Z` with `2.463562` cloud
  - result:
    - exact facility lead is good
    - later clean post-event frames show a defendable drained-reservoir / breach morphology at Sentinel scale
- status:
  - `added_to_non_demo_eval_as_reference_event`
- next action:
  - keep as the first exact water positive anchor
  - no more probe churn needed unless a tighter crop is needed in capture overrides
- sources:
  - [World Bank on Arbaat critical water source](https://documents1.worldbank.org/curated/en/650011609914976904/pdf/Management-of-Critical-Water-Supply-Sources-near-Port-Sudan-Sudan-Arbaat-Dam-and-Well-Fields-at-Arbaat-and-Moj.pdf)
  - [UNDP on Port Sudan dependence on Arbaat](https://www.undp.org/stories/restoring-water)
  - [UN Geneva / OCHA on the 2024-08-24 collapse](https://www.ungeneva.org/en/news-media/news/2024/08/96844/flooding-sudan-dam-collapse-worsens-humanitarian-crisis)

### `water_08` Ayn al-Bayda Water Pumping Station

- country:
  - `Syria`
- type:
  - pumping station
- why:
  - direct civilian drinking-water source for al-Bab and nearby towns
  - exact public geolocation exists
  - better fixed-facility semantics than pipeline / outage stories
- parcel state:
  - exact public lead:
    - `36.224362, 37.566329`
- status:
  - `hold_archive_resolved_signal_still_soft`
- next action:
  - bounded SimSat pass was run on the exact public lead
  - original blocker was the pre-event side:
    - request `2016-10-15T08:00:00Z` -> no image
    - request `2016-11-10T08:00:00Z` -> returned `2016-11-09T08:17:59Z` with `81.460319` cloud
    - request `2016-12-05T08:00:00Z` -> returned `2016-12-02T08:23:15Z` with `48.905083` cloud
    - wider pre sweep:
      - `2016-06-15`, `2016-07-10`, `2016-08-15`, `2016-09-10` -> no image
      - `2017-01-10` -> returned `2017-01-08T08:13:13Z` with `57.327253` cloud
  - reopened local pass found one honest pre-event baseline:
    - request `2016-11-22T08:00:00Z` -> returned `2016-11-19T08:18:06Z` with `9.476642` cloud
  - post side was readable:
    - request `2017-02-20T08:00:00Z` -> returned `2017-02-17T08:15:12Z` with `4.672619` cloud
    - request `2017-04-05T08:00:00Z` -> returned `2017-03-29T08:16:03Z` with `1.179413` cloud
  - result:
    - exact lead is good
    - archive blocker is resolved
    - bounded `0.64 km` and tighter `0.4 km` parcel review still failed to show a defendable plant-scale structural change
  - keep crop on the station only, not surrounding pipeline politics
- sources:
  - [UNICEF June 2025 sitrep](https://www.unicef.org/syria/media/20661/file/Syria-Humanitarian-situation-report-June-2025.pdf)
  - [Syrians for Truth and Justice geolocated station report](https://stj-sy.org/en/al-babs-thirsty-is-the-syrian-government-using-dehydration-as-a-punishment/)
  - [UN statement on damage and rehabilitation context](https://www.un.org/sg/en/content/highlight/2024-12-27.html)

### `water_09` Al-Khafsa retrospective reopen

- country:
  - `Syria`
- type:
  - pure treatment plant
- why:
  - very large water-first campus
  - strongest morphology in the repo
  - still worth a retrospective reopen even though the recent `2025` pair failed
- parcel state:
  - best current public lead remains around `36.1839511, 38.0086273`
- status:
  - `retrospective_archive_unavailable`
- next action:
  - do not reopen as a fresh `2025` hit
  - retrospective archive check on the current parcel lock failed:
    - request `2015-10-20T08:00:00Z` -> no image
    - request `2015-11-10T08:00:00Z` -> no image
    - request `2015-12-05T08:00:00Z` -> no image
    - request `2015-12-20T08:00:00Z` -> no image
    - request `2016-01-10T08:00:00Z` -> no image
  - result:
    - keep as morphology evidence only
    - not currently actionable in the local SimSat archive lane

### `water_10` Wad Medani main water treatment plant

- country:
  - `Sudan`
- type:
  - pure treatment plant
- why:
  - exact public parcel clue exists
  - strong civilian dependence in Aj Jazirah
  - low tactical drift compared with mixed utility sites
- parcel state:
  - OSM way clue:
    - `585752244`
  - centroid:
    - `14.318616, 33.583363`
- bounded probe truth:
  - exact parcel requests returned readable clean windows:
    - `2024-11-20T08:00:00Z` -> `2024-11-17T08:26:15Z` with `0.00006` cloud
    - `2024-12-20T08:00:00Z` -> `2024-12-17T08:26:09Z` with `0.00113` cloud
    - `2025-01-05T08:00:00Z` -> `2025-01-01T08:26:16Z` with `0.000342` cloud
    - `2025-02-10T08:00:00Z` -> `2025-02-05T08:26:42Z` with `0.000136` cloud
  - result:
    - exact parcel is good
    - weather is no longer the blocker
    - bounded `0.8 km` then `0.4 km` review still failed to show a defendable plant-scale structural scar
- status:
  - `hold_exact_parcel_signal_soft`
- next action:
  - keep only as exact evidence unless a later clean window shows a clearer compound-scale disruption than the current January/February pair
- sources:
  - [UNICEF Sudan SitRep No. 29, March 2025](https://www.unicef.org/media/170421/file/UNICEF%20Sudan%20Humanitarian%20Situation%20Report%20No.%2029%20-%20March%202025.pdf)
  - [AidData project page with OSM way clue](https://china.aiddata.org/projects/208/)

### `water_11` Kramatorsk Filtration Station

- country:
  - `Ukraine`
- type:
  - filtration station
- why:
  - exact named OSM water-works parcel exists
  - clear civilian drinking-water role for Kramatorsk
  - strong stress-control shape: real strike reporting, clean pair, still no honest plant-scale scar
- parcel state:
  - exact public way:
    - `OSM way 105507934`
  - centroid:
    - `48.7310014, 37.6010781`
- bounded probe truth:
  - exact parcel requests returned one honest clean pre and post pair:
    - `2023-09-25T08:00:00Z` -> `2023-09-20T08:36:48Z` with `3.190563` cloud
    - `2024-04-25T08:00:00Z` -> `2024-04-22T08:36:45Z` with `3.575131` cloud
  - strike-window frames stayed weak:
    - `2024-02-21T08:00:00Z` -> `2024-02-20T08:46:40Z` with `99.959219` cloud
    - `2024-02-28T08:00:00Z` -> `2024-02-27T08:36:45Z` with `13.590509` cloud
  - result:
    - exact parcel is good
    - clean pair exists
    - compound-scale signal is still too soft and mixed for a defendable station-specific positive at Sentinel scale
- status:
  - `added_to_non_demo_eval_as_exact_control`
- next action:
  - keep as a water stress/control row
  - do not spend more bounded review unless a cleaner plant-scale scar appears
- sources:
  - [UNICEF on the February 2024 strike and four-day outage](https://www.unicef.org/ukraine/en/stories/keeping-water-flowing-despite-attacks)
  - [Detector Media on the 2024-02-20 filtration-station destruction claim](https://en.detector.media/post/state-terrorism-why-does-russia-resort-to-the-tactics-of-pure-terror-against-ukraine)
  - [OSM parcel](https://www.openstreetmap.org/way/105507934)

### `water_12` Kakhovka Dam

- country:
  - `Ukraine`
- type:
  - dam / reservoir water source
- why:
  - macro-visible breach and reservoir drainage are unambiguous at Sentinel scale
  - strong civilian water-supply consequences are explicitly documented in public humanitarian reporting
  - fast, high-confidence second water positive anchor
- parcel state:
  - exact public clue:
    - `OSM dam ways 1478535993 / 1478535994`
  - capture center:
    - `46.776336, 33.371477`
- bounded probe truth:
  - clean pre-event frame:
    - `2023-06-04T08:00:00Z` -> `2023-06-03T08:57:21Z` with `3.621003` cloud
  - clean post-event frame:
    - `2023-07-05T08:00:00Z` -> `2023-07-03T08:57:22Z` with `8.647124` cloud
  - result:
    - exact site is good
    - breach and drained-reservoir morphology are obvious
    - mixed hydro semantics are real, but the row is still defensible as civilian water-infrastructure disruption
- status:
  - `added_to_non_demo_eval_as_reference_event`
- next action:
  - keep as a retrospective major water-source anchor
  - no more bounded review needed unless we later want a tighter crop override
- sources:
  - [AP on the 2023-06-06 breach](https://apnews.com/article/russia-ukraine-war-dam-collapse-kakhovka-kherson-daacdc431f42912dfb91548794f03a3c)
  - [WHO on water-supply disruption after the breach](https://www.who.int/europe/news/item/13-06-2023-who-steps-up-its-humanitarian-response-in-southern-ukraine-following-the-destruction-of-the-kakhovka-dam)
  - [Global Energy Observatory facility clue](https://globalenergyobservatory.org/geoid/43018)

### `water_13` Mansour Dam

- country:
  - `Libya`
- type:
  - dam / reservoir water source
- why:
  - macro-visible dam-failure morphology is obvious at Sentinel scale
  - exact public parcel clue exists for the failed structure above Derna
  - the flood aftermath had clear downstream civilian water and infrastructure consequences
- parcel state:
  - exact public clue:
    - `Mapcarta / OSM way 1207192349`
  - capture center:
    - `32.65937, 22.57708`
- bounded probe truth:
  - clean pre-event frame:
    - `2023-09-05T08:00:00Z` -> `2023-09-02T09:21:27Z` with `0.486787` cloud
  - clean post-event frame:
    - `2023-11-05T08:00:00Z` -> `2023-11-01T09:21:20Z` with `0.785303` cloud
  - result:
    - exact site is good
    - breach and widened flood-corridor morphology are obvious
    - row is defensible as catastrophic civilian water-infrastructure disruption
- status:
  - `added_to_non_demo_eval_as_reference_event`
- next action:
  - keep as a retrospective dam-failure water-source anchor
  - stop bounded churn on softer water leads until a clearly better future case appears
- sources:
  - [AP on the September 2023 collapse of two dams above Derna](https://apnews.com/article/libya-floods-dams-storm-daniel-derna-6988c0502c713af29989ce8118b618e6)
  - [UNICEF Libya humanitarian situation report on washed-out wells and inaccessible clean water after the floods](https://www.unicef.org/media/151781/file/Libya%20Humanitarian%20Situation%20Report%20No.%201%20%28End%20of%20Year%29%201%20Jan%20-%2031%20December%202023.pdf)
  - [Mapcarta exact facility clue](https://mapcarta.com/W1207192349)

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
  - `added_to_non_demo_eval_as_exact_control`
- next action:
  - keep as a conflict-adjacent water no-change benchmark
  - do not spend more time unless a stronger plant polygon or independent parcel anchor appears for a future positive lane
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
  - strongest current parcel clue is a riverfront utility compound around `13.1601864, 32.6865113`
  - JICA brochure confirms the real site should read as a rectilinear intake / basin / filtration campus, but the current clue is still weaker than that expected morphology
- status:
  - `hold_plausible_parcel_no_structural_signal`
- next action:
  - do not promote from the current clue
  - tight pair on the parcel clue:
    - baseline request `2025-01-20T08:00:00Z` -> returned `2025-01-16T08:26:31Z` with `40.911147` cloud
    - current request `2025-03-29T08:00:00Z` -> returned `2025-03-27T08:26:54Z` with `0.280961` cloud
  - result:
    - good civilian story, but no defendable plant-compound damage signature
    - pair reads as weak parcel match plus weather / land-cover shift, not a positive eval row
  - keep only as evidence unless a better parcel lock or cleaner baseline appears
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
  - best current geography clue:
    - Babiri village seed `36.1254475, 38.0005080`
    - on the Euphrates between `Qafsa / Khafsa` and `Maskana / Meskene`, east of Aleppo
- blocker:
  - current `2026` reporting is mostly about pumping stoppage and restoration
  - still not a clean structural-damage case
- status:
  - `hold_river_corridor_still_soft`
- next action:
  - first `1.5 km` locator sweep around the village seed on `2025-01-30T08:00:00Z` did not isolate the station parcel
  - follow-up `0.8 km` `3x3` river-corridor sweep around the nearest dark riverbank utility band also failed to show defendable `intake + basins + reservoir` morphology
  - result:
    - Babiri stays a strong civilian service story
    - but not yet a parcel-tight Sentinel story
  - keep only as evidence unless a better parcel anchor appears
- sources:
  - [SANA on Babiri cutoff affecting Aleppo](https://sana.sy/en/syria/2289847/)
  - [Anadolu on Babiri serving Aleppo city and countryside](https://www.aa.com.tr/en/middle-east/sdf-cuts-water-supply-to-syria-s-aleppo/3796034)
  - [Levant24 on Babiri restoration and field inspection](https://levant24.com/news/2026/01/syria-boosts-water-security-through-major-infrastructure-projects/)
  - [Türkiye Today on Babiri lying between Qafsa and Meskene on the Euphrates](https://www.turkiyetoday.com/region/sdf-uses-water-control-as-leverage-as-syrian-armys-operations-could-expand-north-3212792)

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
  - facility clue is stronger than most remaining water leads:
    - on the coastal road
    - south / southwest of Deir al-Balah
    - within the southwestern Deir al-Balah evacuation zone in later reporting
- blocker:
  - current public evidence is mainly electricity-line / cable damage and output collapse
  - not yet an honest plant-structure damage story
- status:
  - `hold_sensitive_outage_story`
- next action:
  - keep as backlog evidence only
  - do not keep exact-parcel hunting this site as the active next move
  - only reopen if:
    - the plant compound is already publicly pinned in humanitarian / utility docs
    - and visible plant / service-compound damage is separable from cable / outage reporting
- sources:
  - [AP on electricity cutoff affecting Gaza desalination plant](https://apnews.com/article/ba90f0de3d4f64a1762d1a39f787817f)
  - [UNICEF on March 2026 cable damage and 80 per cent output drop](https://www.unicef.org/sop/stories/unicef-restores-water-access-tens-thousands-children-gaza)
  - [UN/UNICEF on Southern Gaza Seawater Desalination Plant identity](https://www.un.org/unispal/document/eu-and-unicef-mark-completion-of-expansion-of-the-southern-gaza-seawater-desalination-plant-press-release/)
  - [Sawa on the plant site being on the coastal road south of Deir al-Balah](https://palsawa.com/post/99981/%D8%A7%D9%84%D8%A7%D8%AD%D8%AA%D9%81%D8%A7%D9%84-%D8%A8%D8%A7%D9%81%D8%AA%D8%AA%D8%A7%D8%AD-%D9%85%D8%AD%D8%B7%D8%A9-%D8%AA%D8%AD%D9%84%D9%8A%D8%A9-%D9%85%D9%8A%D8%A7%D9%87-%D8%A7%D9%84%D8%A8%D8%AD%D8%B1)
  - [ieCRES 2023 on the plant being at the coastal road in front of Deir el-Balah](https://eftaa.iugaza.edu.ps/wp-content/uploads/sites/20/2023/07/ieCRES-2023_paper_4560.pdf)

### `water_06` Al-Arshani Water Station

- country:
  - `Syria`
- type:
  - water station
- why:
  - exact public coordinates now exist
  - explicit civilian-service role for Idlib city
  - one of the cleanest exact-site humanitarian water clues tried so far
- parcel state:
  - exact public coordinate clue:
    - `35.948861, 36.556375`
  - source trail says the station was struck on `2022-01-02`
- probe truth:
  - clean pre frame exists:
    - request `2021-12-10T08:00:00Z` -> returned `2021-12-06T08:30:13Z` with `0.097488` cloud
  - near-event post windows were mostly cloud-blocked:
    - request `2022-01-10T08:00:00Z` -> returned `2022-01-05T08:30:15Z` with `60.027914` cloud
    - request `2022-01-20T08:00:00Z` -> returned `2022-01-15T08:30:15Z` with `34.647347` cloud
  - one later clean post frame exists:
    - request `2022-03-20T08:00:00Z` -> returned `2022-03-16T08:30:18Z` with `0.785722` cloud
  - tight `0.8 km` parcel pass still failed:
    - no defendable roof loss
    - no basin breach
    - no compound burn scar
    - only tonal / seasonal drift
- status:
  - `hold_exact_public_coords_no_structural_signal`
- next action:
  - do not promote
  - keep as evidence only unless a cleaner near-event post frame or stronger plant-scale damage clue appears
- sources:
  - [Airwars on the `2022-01-02` strike and exact coordinates](https://airwars.org/civilian-casualties/r4433-january-2-2022/)
  - [SNHR on partial structural damage and pumping-line damage](https://news.snhr.org/2022/01/02/russian-air-attack-targeted-a-water-station-in-idlib-city-on-january-2/)
  - [UNICEF whole-of-Syria sitrep on Arshani water-station disruption](https://www.unicef.org/media/120251/file/Whole-of-Syria-Humanitarian-SitRep-March-2022.pdf)

### `water_07` Khartoum Bahri Water Station

- country:
  - `Sudan`
- type:
  - water station
- why:
  - exact named utility site, not a vague city-wide outage
  - direct civilian-service role for Khartoum North
  - public reporting explicitly says the station was heavily damaged
- parcel state:
  - existing exact family already in repo as `Bahri Water Station`
  - this means row shape and control history are already known
- source truth:
  - damage window reported between `2025-01-30` and `2025-02-04`
  - transformers, pumps, cables, tanks, and operations were all reported hit
- why this matters:
  - strongest new water-positive reopening clue since `Kakhovka` / `Mansour`
  - better fit than generic outage stories because the damage claim is tied to one fixed plant
- status:
  - `probe_exact_windows_soft_keep_control`
- next action:
  - exact-site probe already returned very clean Jan-Mar 2025 windows
  - local visual review still did not show a defendable plant-scale macro scar
  - keep the existing Bahri control and stop unless a stronger parcel anchor appears
- sources:
  - [Sudan Tribune, 2025-02-04](https://sudantribune.com/article/296726)

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

1. freeze `water` positive hunting for now
2. keep `Al-Arshani`, `South Gaza`, `Babiri`, `Kosti JICA`, and `Bahri` as evidence only unless stronger public parcel anchors or cleaner structural post frames appear
3. do not spend another tranche move on `water` until a candidate clears:
   - exact named public parcel or polygon
   - clean pre/post pair
   - defendable plant-scale structural change
4. shift the next tranche slot to a new `aid_02` inland lead search or another non-water control
