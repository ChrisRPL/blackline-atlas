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

### Hold; retry with different timestamps

#### Chornomorsk Grain Port
- asset type: `grain_port`
- why:
  - civilian grain/export artery
  - good category fit
  - clear pre/post pair now exists
  - still no honest macro label yet from the visible pair
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

#### Babiri Water Station
- asset type: `water_infrastructure`
- why:
  - publicly described as a main water source for Aleppo city and surrounding rural areas
  - strong user-value shape: city-scale civilian water interruption
  - better product fit than another port retry
- status: `hold_independent_sourcing_and_geolocation`
- notes:
  - keep as a search seed only until exact site identity, coordinates, and honest Sentinel-scale change are verified
  - do not label from outage claims alone
- sources:
  - [SANA, 2026-01-10](https://sana.sy/en/syria/2289847/)
  - [A News, 2026-01-11](https://www.anews.com.tr/middle-east/2026/01/11/syria-restores-water-supply-to-aleppo-after-sdf-disruption)

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
