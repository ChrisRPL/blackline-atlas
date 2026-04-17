# Civilian AOI Backlog

Use this when expanding `training/replay_pack/non_demo_eval.jsonl`.

Rule:
- public civilian lifeline
- macro visible in Sentinel
- current/recent conflict context allowed
- no mixed-use military ports
- no fuel depots
- no crossing-gate route intel

User-value rule:
- ask first: would a civilian near this city, region, or nearby country care if this lifeline were disrupted?
- rank by human dependence, not by how dramatic the satellite scene looks
- require honest macro visibility before labeling anything
- if a case answers route-open or convoy-flow questions faster than civilian-impact questions, drop it

Priority order:
- food
- water
- aid
- mobility

Primary buckets:
- food
- water
- aid
- mobility

## Current shortlist

### Go now

#### Port Sudan Aid Hub
- asset type: `container_port`
- why:
  - public aid gateway
  - visible port-scale burn/smoke change in local SimSat probe
- dates:
  - baseline probe: `2025-04-18T08:14:40Z`
  - current probe: `2025-05-08T08:14:40Z`
- status: added to `non_demo_eval.jsonl`
- sources:
  - [UN Geneva, 2025-05-19](https://www.ungeneva.org/en/news-media/news/2025/05/106496/drone-strikes-civilian-infrastructure-port-sudan-must-end-un-expert)
  - [AP, 2025-05-06](https://apnews.com/article/396f67d3fada66707094858086b2ee53)

#### Beirut Grain Silos
- asset type: `grain_port`
- why:
  - clear food-security benchmark, not just a generic port scene
  - exact site identity and coordinates are stable
  - local SimSat probe returned an honest pre/post pair with obvious macro disruption
- coordinates:
  - `33.901111, 35.517778`
- dates:
  - baseline request `2020-07-25T08:00:00Z` -> returned `2020-07-24T08:30:50Z`
  - current request `2020-08-10T08:00:00Z` -> returned `2020-08-08T08:30:48Z`
- status:
  - added to `non_demo_eval.jsonl`
  - treat as `retrospective_food_security_anchor`, not a train row
- sources:
  - [Reuters via Al Arabiya, 2020-08-05](https://english.alarabiya.net/News/middle-east/2020/08/05/Beirut-grain-silo-destroyed-Lebanon-s-needs-still-covered-Minister)
  - [AP, 2025-08-04](https://apnews.com/article/d558e3fde568ab1d5a952d898f18fab2)

### Hold; retry with different timestamps

#### Chornomorsk Grain Port
- asset type: `grain_port`
- why:
  - civilian grain/export artery
  - good category fit
  - clear pre/post pair now exists
  - still no honest macro label yet from the visible pair
- notes:
  - only keep this alive as a tightly cropped grain-handling / storage sub-AOI
  - do not promote the whole port footprint
- dates probed:
  - initial cloudy pair: baseline `2025-12-14T08:57:36Z`, current `2026-01-08T09:07:47Z`
  - clearer pair: baseline `2025-10-15T08:57:39Z`, current `2026-03-04T08:57:28Z`
- status: `hold_visual_review`
- sources:
  - [Reuters via Investing.com, 2026-01-07](https://www.investing.com/news/world-news/russia-attacks-two-ukrainian-ports-kyiv-says-4435521)
  - [Reuters syndication, 2026-03-05](https://wsau.com/2026/03/05/russian-drone-strikes-foreign-cargo-ship-near-ukraine-black-sea-port/)

#### Pivdennyi Export Port
- asset type: `container_port`
- why:
  - major civilian export artery
  - clear pre/post pair now exists
  - still no honest macro label yet from the visible pair
- dates probed:
  - initial cloudy pair: baseline `2025-12-14T08:57:36Z`, current `2026-01-08T09:07:47Z`
  - clearer pair: baseline `2025-10-15T08:57:39Z`, current `2026-03-04T08:57:28Z`
- status: `hold_visual_review`
- sources:
  - [Reuters via Investing.com, 2026-01-07](https://www.investing.com/news/world-news/russia-attacks-two-ukrainian-ports-kyiv-says-4435521)

#### Agrico Ukraine / AF Andriivske potato storage
- asset type: `logistics_hub`
- why:
  - inland food-storage case, closer to civilian food resilience than another seaport
  - seed-potato storage and packaging is a real upstream food-chain lifeline
  - reported strike is tied to a named civilian agricultural enterprise, not a vague city hit
- status: `hold_exact_parcel_and_visibility`
- notes:
  - verify the exact parcel in or near Avdiivka village, Chernihiv Oblast
  - only promote if the storage-yard footprint is large enough for honest Sentinel labeling
  - useful because it tests whether Blackline can see food-chain disruption away from export ports
- sources:
  - [Ukrainska Pravda, 2025-05-26](https://www.pravda.com.ua/eng/news/2025/05/26/7514098/)
  - [EastFruit, 2025-05-27](https://east-fruit.com/en/news/russian-strike-on-agrico-ukraine-an-attack-on-food-security-and-the-resilience-of-ukrainian-farmers/)
  - [Agrico Ukraine demo centers](https://www.agrico.com.ua/en/agrico-demo-centers)

#### Star Brands Pavlohrad food warehouse
- asset type: `logistics_hub`
- why:
  - regional warehouse for grocery goods, flour, pasta, cereals, and finished food products
  - stronger household-facing story than another export-only node
  - inland, city-edge distribution case is closer to how civilians actually feel disruption
- status: `hold_food_only_crop_and_exact_site`
- notes:
  - keep only if the struck footprint is predominantly food storage, not mixed FMCG/logistics
  - exact warehouse parcel still needs verification before SimSat probe
  - if verified, this is one of the better “something is wrong near my region” food cases
- sources:
  - [Kyiv Post, 2026-04-08](https://www.kyivpost.com/post/73498)
  - [Star Grocery official site](https://stargrocery.com.ua/en/)

#### Qasmiyeh Bridge
- asset type: `bridge`
- why:
  - direct civilian mobility lifeline
  - publicly reported as the last bridge linking southern Lebanon to the rest of the country
  - right product shape for a civilian user
- dates probed:
  - promising baseline: `2026-03-10T08:31:00Z`
  - promising current: `2026-04-16T08:31:18Z`
- status: `hold_sensitivity_and_visibility`
- notes:
  - local SimSat probe around the likely crossing returned a tile-edge baseline artifact
  - safety review says major bridges drift tactical faster than food, water, and aid
  - keep as a mobility example, not the next forced eval row
- sources:
  - [Reuters syndication, 2026-04-16](https://wsau.com/2026/04/16/israeli-strike-severs-last-bridge-linking-southern-lebanon-to-rest-of-country-lebanese-security-official-says/)
  - [Le Monde, 2026-03-24](https://www.lemonde.fr/en/international/article/2026/03/24/in-southern-lebanon-civilians-are-trapped-after-israel-destroys-bridges_6751768_4.html)

#### Gulf desalination plants
- asset type: `water_infrastructure`
- why:
  - extremely people-facing
  - good long-term category for Blackline
  - current conflict relevance in 2026
- status: `hold_category_seed`
- sources:
  - [AP, 2026-03-08](https://www.kktv.com/2026/03/08/bahrain-says-iran-hit-desalination-plant-stoking-fears-attacks-civilian-sites/)
  - [AP, 2026-03-30](https://apnews.com/article/f624bed66bee79f68454d581ae1d624a)

#### Doha West Power And Desalination Plant
- asset type: `water_infrastructure`
- why:
  - major drinking-water infrastructure for Kuwait
  - exact plant identity and coordinates are easy to verify
  - useful civilian framing if a clean macro-visible disruption exists
- coordinates:
  - `29.368333, 47.788333`
- dates probed:
  - baseline request `2026-03-01T08:00:00Z` -> returned `2026-02-28T07:41:39Z`
  - current request `2026-03-31T08:00:00Z` -> returned `2026-03-30T07:41:39Z`
- status: `hold_clouded_and_mixed_use`
- notes:
  - current-side probe was heavily clouded (`86.009896`)
  - facility is integrated power + water, which raises mixed-use sensitivity versus pure water infrastructure
  - do not promote unless a cleaner current pair appears and the civilian water story remains primary
- sources:
  - [AP, 2026-03-08](https://apnews.com/article/12b23f2fa26ed5c4a10f80c4077e61ce)
  - [Al Jazeera, 2026-03-30](https://www.aljazeera.com/news/2026/3/30/iranian-attack-damages-kuwait-power-and-desalination-plant-kills-worker)
  - [Wikimapia coordinates](https://wikimapia.org/9034607/DOHA-WEST-POWER-PLANT)

#### Ras Abu Jarjur Desalination Plant
- asset type: `water_infrastructure`
- why:
  - pure water-infrastructure shape
  - exact plant identity and coordinates are easy to verify
  - strong civilian dependence framing
- coordinates:
  - `26.073889, 50.621944`
- dates probed:
  - baseline request `2026-03-01T08:00:00Z` -> returned `2026-02-27T07:22:33Z`
  - current request `2026-03-09T08:00:00Z` -> returned `2026-03-09T07:22:33Z`
- status: `hold_no_honest_macro_change`
- notes:
  - pair is usable (`1.555283` / `16.679116` cloud), but local visual review did not show a clear macro disruption honest enough for a bbox label
  - keep as a search seed, not an eval row
- sources:
  - [AP, 2026-03-08](https://apnews.com/article/12b23f2fa26ed5c4a10f80c4077e61ce)
  - [Wikimapia coordinates](https://wikimapia.org/447048/Ras-Abu-Jarjur-Desalination-plant)

#### Babiri Water Station
- asset type: `water_infrastructure`
- why:
  - publicly described as a main water source for Aleppo city and surrounding rural areas
  - strong user-value shape: city-scale civilian water interruption
  - better product fit than another port retry
- status: `hold_independent_sourcing_and_geolocation`
- coordinates:
  - approximate village seed: `36.1254475, 38.0005080`
- dates probed:
  - baseline request `2025-12-20T08:00:00Z` -> returned `2025-12-17T08:30:11Z`
  - current request `2026-01-10T08:00:00Z` -> returned `2026-01-06T08:20:12Z`
- notes:
  - keep as a search seed only until exact site identity, coordinates, and honest Sentinel-scale change are verified
  - do not label from outage claims alone
  - first current-side probe was heavily clouded (`80.994809`)
  - likely risk: service interruption matters to users, but the site may still lack a clean structural before/after signal at Sentinel scale
- sources:
  - [SANA, 2026-01-10](https://sana.sy/en/syria/2289847/)
  - [A News, 2026-01-11](https://www.anews.com.tr/middle-east/2026/01/11/syria-restores-water-supply-to-aleppo-after-sdf-disruption)

### Rejected after probe

#### Sarrin grain-silo seed
- why rejected:
  - usable pair, but no honest macro food-disruption signal showed up
  - source trail never became strong enough to justify a real eval row
- dates probed:
  - baseline request `2026-01-05T08:00:00Z` -> returned `2026-01-03T08:20:18Z`
  - current request `2026-01-24T08:00:00Z` -> returned `2026-01-21T08:19:56Z`
- notes:
  - cloud was acceptable enough to decide (`1.083115` / `28.538302`)
  - visual diff looked like ordinary town/agricultural variation, not a civilian food-lifeline disruption
- status: `reject_no_honest_signal`

### Keep out for now

#### Hodeidah / Ras Issa Port Lane
- why:
  - humanitarian relevance, yes
  - dual-use risk too high for first Blackline lane
  - local probe was usable, but category safety not clean enough
- status: `avoid_dual_use`
- sources:
  - [Human Rights Watch, 2025-06-04](https://www.hrw.org/news/2025/06/04/yemen-us-strikes-port-apparent-war-crime)
  - [Reuters via Yahoo, 2025-01-21](https://www.yahoo.com/news/yemen-red-sea-port-capacity-202915714.html)

#### Bandar Abbas / Hormuz lane
- why:
  - visible, yes
  - too strategically loaded for first Blackline lane
  - drifts from civilian lifeline monitoring into maritime/energy conflict intelligence
- status: `avoid_strategic_sensitivity`
- sources:
  - [AP, 2025-04-28](https://apnews.com/article/fd31972422ae1612006b1c8005f58440)
  - [AP, 2026-04-17](https://apnews.com/article/10518e69aecbb986c9118ff42ab0ca02)

#### Gaza Crossing Gates
- why:
  - humanitarian importance, yes
  - macro Sentinel signal too weak for honest first-pass labels
  - too close to route/gate intelligence
- status: `avoid_visibility_and_sensitivity`
- sources:
  - [OCHA OPT, 2026-04-02](https://www.ochaopt.org/content/humanitarian-situation-report-2-april-2026)

## Next search pattern

Prefer:
- food hubs
- water infrastructure
- aid warehouse clusters
- only then clearly civilian bridges
- large logistics yards only when the civilian function is obvious

Active next search:
- inland grain silo clusters
- flour mills with large storage yards
- wholesale food depots near major cities
- pure water-treatment assets with visible ponds, tanks, or plant-footprint damage

Avoid:
- airports
- naval adjacency
- fuel/oil terminals
- convoy timing
- camp interiors

## Country scan notes

Use these as search constraints, not as automatic watchlist adds.

### Venezuela
- keep:
  - school-meal supply chains
  - municipal water systems
  - disaster-relief warehouses
- avoid:
  - oil terminals
  - border crossings
  - national power hubs

### Sudan
- keep:
  - aid warehouses
  - grain storage
  - water points and treatment assets
  - humanitarian logistics hubs
- avoid:
  - bridges and river crossings
  - convoy corridors
  - frontline access roads

### Pakistan
- keep:
  - flood-hit grain storage
  - irrigation and water-distribution assets
  - relief warehouses
  - washed-out civilian roads at district scale
- avoid:
  - border logistics
  - security-sensitive bridges
  - airports

### Iraq
- keep:
  - municipal water treatment and pumping
  - grain silos and flour mills
  - IDP and returnee service hubs
- avoid:
  - oil terminals and pipelines
  - contested-corridor bridges
  - mixed-use airports

### Syria
- keep:
  - water stations
  - wastewater plants
  - public bakeries and flour-supply hubs
  - humanitarian warehouse clusters
- avoid:
  - border crossings
  - ports and airports
  - fuel depots

### Russia
- keep:
  - only non-war disaster-response classes far from the war context
  - flood or water infrastructure if clearly civilian
- avoid:
  - ports
  - bridges
  - rail hubs
  - grain export terminals
  - logistics parks

### Sources for country scan
- [WFP Venezuela CSP](https://www.wfp.org/operations/ve02-bolivarian-republic-venezuela-interim-country-strategic-plan-2023-2025)
- [WFP Sudan emergency](https://www.wfp.org/emergencies/sudan-emergency)
- [WFP Pakistan floods](https://www.wfp.org/stories/we-just-ran-families-struggle-pakistan-floods-destroy-homes-fields-and-food-supplies)
- [WFP Iraq CSP](https://www.wfp.org/operations/iq03-iraq-country-strategic-plan-2026-2029)
- [UNICEF Syria WASH](https://www.unicef.org/syria/press-releases/unicef-and-germany-strengthen-access-safe-water-and-sanitation-children-and-families)
- [WFP Syria bread programme](https://www.wfp.org/news/wfp-expands-and-extends-its-subsidized-bread-programme-across-syria)
