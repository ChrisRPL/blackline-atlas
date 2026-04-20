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

#### Silpo Kvitneve Distribution Center
- asset type: `logistics_hub`
- why:
  - exact named inland food-distribution campus, not a vague city-edge warehouse guess
  - direct grocery and frozen-food supply-chain relevance for civilians around Kyiv
  - clean pre/post SimSat pair with a defendable warehouse-scale disruption signal
- coordinates:
  - source address anchor: `50.529365, 30.852823` (`Hoholivska 1-A`)
  - warehouse-centered eval crop: `50.528965, 30.849714`
- dates:
  - baseline request `2022-03-01T08:00:00Z` -> returned `2022-02-26T09:06:28Z`
  - current request `2022-03-25T08:00:00Z` -> returned `2022-03-23T09:06:23Z`
- status:
  - added to `non_demo_eval.jsonl`
  - treat as `current_conflict_inland_food_distribution_anchor`
- sources:
  - [Silpo-Food annual report PDF, lines 2289-2294](https://content.silpo.ua/uploads/2022/10/06/633e8c17a30f8.pdf)
  - [Ukrainska Pravda, 2022-03-12](https://www.pravda.com.ua/eng/news/2022/03/12/7330610/)

### Recently landed

#### Arbaat Dam
- asset type: `water_infrastructure`
- why:
  - exact public water-source asset for Port Sudan
  - high civilian dependence
  - breach / reservoir-shape change is a good macro-signal candidate
- coordinates:
  - `19.833554, 36.941204`
- final bounded probe:
  - baseline request `2024-07-20T08:00:00Z` -> returned `2024-07-17T08:14:43Z` with `13.07416` cloud
  - post requests:
    - `2024-08-24T08:00:00Z` -> `2024-08-21T08:14:42Z` with `75.901413` cloud
    - `2024-08-30T08:00:00Z` -> `2024-08-26T08:14:40Z` with `18.400928` cloud
    - `2024-09-05T08:00:00Z` -> `2024-08-31T08:14:44Z` with `13.812824` cloud
    - `2024-09-12T08:00:00Z` -> `2024-09-10T08:14:44Z` with `38.68123` cloud
    - `2024-09-20T08:00:00Z` -> `2024-09-15T08:14:41Z` with `6.886818` cloud
    - `2024-10-05T08:00:00Z` -> `2024-09-30T08:14:43Z` with `0.018271` cloud
    - `2024-10-20T08:00:00Z` -> `2024-10-15T08:14:42Z` with `2.463562` cloud
- status:
  - `added_to_non_demo_eval`
- notes:
  - exact lead held up
  - later clean post-event frames show a defendable drained-reservoir / breach signature
  - this is now the first real water positive in the pack
- sources:
  - [World Bank on Arbaat critical water source](https://documents1.worldbank.org/curated/en/650011609914976904/pdf/Management-of-Critical-Water-Supply-Sources-near-Port-Sudan-Sudan-Arbaat-Dam-and-Well-Fields-at-Arbaat-and-Moj.pdf)
  - [UNDP on Port Sudan dependence on Arbaat](https://www.undp.org/stories/restoring-water)
  - [UN Geneva / OCHA on the collapse](https://www.ungeneva.org/en/news-media/news/2024/08/96844/flooding-sudan-dam-collapse-worsens-humanitarian-crisis)

### Hold; retry with different timestamps

#### Ayn al-Bayda Water Pumping Station
- asset type: `water_infrastructure`
- why:
  - direct civilian drinking-water source for al-Bab and nearby towns
  - exact public geolocation exists
  - fixed pumping-station semantics are cleaner than pipeline/outage stories
- coordinates:
  - `36.224362, 37.566329`
- bounded probe:
  - first pass had looked archive-blocked:
    - `2016-10-15` -> no image
    - `2016-11-10` -> `2016-11-09T08:17:59Z` with `81.460319` cloud
    - `2016-12-05` -> `2016-12-02T08:23:15Z` with `48.905083` cloud
    - wider pre sweep `2016-06` through `2016-09` -> no image
    - `2017-01-10` -> `2017-01-08T08:13:13Z` with `57.327253` cloud
  - reopening pass found one honest pre-event side:
    - `2016-11-22` -> `2016-11-19T08:18:06Z` with `9.476642` cloud
  - post side usable:
    - `2017-02-20` -> `2017-02-17T08:15:12Z` with `4.672619` cloud
    - `2017-04-05` -> `2017-03-29T08:16:03Z` with `1.179413` cloud
- status:
  - `hold_archive_resolved_signal_still_soft`
- notes:
  - exact lead is good
  - pre-event archive blocker is no longer the main problem
  - bounded `0.64 km` and tighter `0.4 km` pre/post review still did not isolate a defendable plant-scale damage signature
  - do not promote yet; keep only as an exact reopened evidence lead
- sources:
  - [UNICEF June 2025 sitrep](https://www.unicef.org/syria/media/20661/file/Syria-Humanitarian-situation-report-June-2025.pdf)
  - [Syrians for Truth and Justice geolocated station report](https://stj-sy.org/en/al-babs-thirsty-is-the-syrian-government-using-dehydration-as-a-punishment/)
  - [UN statement on damage and rehabilitation context](https://www.un.org/sg/en/content/highlight/2024-12-27.html)

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
  - public reporting points to the damaged facility in `Avdiivka` village, Chernihiv Oblast, while the company registry address in `Andriivka, Mykhailivska 131` looks more like a legal/admin clue than the actual hit parcel
  - village-seed SimSat probe was readable:
    - baseline request `2025-04-25T08:00:00Z` -> returned `2025-04-23T09:06:11Z`
    - current request `2025-06-04T08:00:00Z` -> returned `2025-06-02T09:06:14Z`
  - result: no honest macro storage disruption was visible at village scale
  - only promote if the exact storage parcel becomes identifiable and shows a clearer Sentinel-scale footprint than the village-seed pair
  - useful because it tests whether Blackline can see food-chain disruption away from export ports
- sources:
  - [Ukrainska Pravda, 2025-05-26](https://www.pravda.com.ua/eng/news/2025/05/26/7514098/)
  - [EastFruit, 2025-05-27](https://east-fruit.com/en/news/russian-strike-on-agrico-ukraine-an-attack-on-food-security-and-the-resilience-of-ukrainian-farmers/)
  - [Agrico Ukraine demo centers](https://www.agrico.com.ua/en/agrico-demo-centers)
  - [Liga, 2025-05-26](https://biz.liga.net/en/all/prodovolstvie/novosti/russian-attack-destroys-dutch-agrico-potato-storage-facility-in-chernihiv-region)
  - [Opendatabot company record](https://opendatabot.ua/c/39174244)

#### Star Brands Pavlohrad food warehouse
- asset type: `logistics_hub`
- why:
  - regional warehouse for grocery goods, flour, pasta, cereals, and finished food products
  - stronger household-facing story than another export-only node
  - inland, city-edge distribution case is closer to how civilians actually feel disruption
- status: `hold_post_strike_weather_blocked`
- notes:
  - strongest public parcel clue so far is `3 Mykoly Shutia St, Pavlohrad`
  - exact parcel seed used: `48.542772, 35.883719`
  - exact parcel clue is now reinforced by a direct map/address source, not just hiring-page context
  - keep only if the struck footprint is predominantly food storage, not mixed FMCG/logistics
  - best pre-strike baseline now pinned:
    - request `2026-04-07T08:47:00Z` -> returned `2026-04-05T08:46:43Z` with `0.652506` cloud
  - bounded post-strike sweep failed:
    - request `2026-04-10T08:47:00Z` -> returned `2026-04-10T08:46:42Z` with `99.947125` cloud
    - request `2026-04-13T08:47:00Z` -> returned `2026-04-12T08:47:04Z` with `77.931386` cloud
    - request `2026-04-16T08:47:00Z` -> returned `2026-04-15T08:46:42Z` with `46.458131` cloud
    - spill request `2026-04-19T08:47:00Z` -> `image_available=false`
  - final bounded daily pass on the exact parcel for `2026-04-08` through `2026-04-17` at both `1.0 km` and `0.5 km` found no cleaner post-hit frame:
    - `2026-04-08/09` -> still pre-strike `2026-04-05T08:46:43Z` with `0.652506` cloud
    - `2026-04-10/11/12` -> `2026-04-10T08:46:42Z` with `99.947125` cloud
    - `2026-04-13/14` -> `2026-04-12T08:47:04Z` with `77.931386` cloud
    - `2026-04-15/16/17` -> `2026-04-15T08:46:42Z` with `46.458131` cloud
  - one final RGB-only check for `2026-04-16` through `2026-04-19` at `0.5 km`, `0.8 km`, and `1.0 km` still returned the same `2026-04-15T08:46:42Z` frame with `46.458131` cloud
  - result: exact parcel is solved, but weather still blocks an honest post-strike frame as of `2026-04-17`
  - if we ever get a clear post-strike frame, this becomes one of the better “something is wrong near my region” food cases
- sources:
  - [Kyiv Post, 2026-04-08](https://www.kyivpost.com/post/73498)
  - [Star Grocery official site](https://stargrocery.com.ua/en/)
  - [Ukrinform, 2026-04-07](https://www.ukrinform.net/rubric-ato/4110088-russian-drones-strike-snack-manufacturers-warehouse-in-pavlohrad-overnight.html)
  - [Visicom exact parcel clue](https://maps.visicom.ua/i/ADR3JRG76VJINYTJ1N)
  - [Work.ua address clue](https://www.work.ua/jobs/7221388/)

#### Novus Logistics Center
- asset type: `logistics_hub`
- why:
  - one of the clearest civilian food-distribution leads outside the current pack
  - exact source trail is stronger than most new food candidates:
    - single centralized grocery logistics center
    - dry, cold, and deep-freeze storage
    - built specifically for a major supermarket chain
  - user story is strong:
    - disruption near Kyiv
    - visible risk to grocery distribution, not just generic warehousing
- status: `hold_exact_pair_signal_too_soft`
- coordinates:
  - recommended crop center:
    - `50.404419, 30.419830`
  - strongest street/service anchor:
    - `50.4043373, 30.4240833` (`Проектна, 3`)
- notes:
  - MIGA project docs identify the site as the Novus logistics center between `вул. Якова Качури` and `вул. Миру` in Kyiv's Sviatoshynskyi district
  - the same EIA gives cadastral parcel `8000000000:75:199:0001`
  - exact parcel is now publicly defensible, not just improving:
    - the Kyiv construction registry
    - the EIA
    - MIGA / EBRD project pages
    - and the named OSM footprint all converge on the same logistics-center parcel
  - best current crop recommendation is a `640 m x 640 m` square centered on `50.404419, 30.419830`
  - first bounded SimSat pass on the strongest current anchor was unusable on the strike windows:
    - `2025-11-10` -> `2025-11-09T09:06:42Z` with `99.992341` cloud
    - `2025-11-28` -> `2025-11-27T09:06:36Z` with `99.978232` cloud
    - `2025-12-10` -> `2025-12-07T09:06:35Z` with `99.998862` cloud
  - reopening pass finally found readable post-event windows:
    - `2026-01-15` -> `2026-01-14T09:16:20Z` with `4.837549` cloud
    - `2026-03-15` -> `2026-03-12T09:16:44Z` with `18.896043` cloud
  - best near-strike pre side remained weak but usable:
    - `2025-11-20` -> `2025-11-19T09:06:43Z` with `22.037385` cloud
  - result:
    - exact product semantics: good
    - exact parcel lock: good
    - current post-strike archive/weather truth: no longer blocked
    - but the bounded pre/post review still fails the honesty bar:
      - the January frame is snow-dominated
      - the March frame is readable but still does not show a defendable parcel-scale macro scar
  - keep on hold; stop spending time unless a clearly better post-strike frame appears
- sources:
  - [Kyiv construction registry / parcel permit](https://e-construction.gov.ua/document_detail/doc_id=3227146532302095948/optype=100)
  - [Public cadastral map query](https://map.land.gov.ua/?cadnum=8000000000:75:199:0001)
  - [MIGA project page for Novus Logistics Center](https://www.miga.org/project/novus-logistics-center)
  - [MIGA EIA PDF](https://www.miga.org/sites/default/files/2025-02/Environmental%20Impact%20Assessment%20%28EIA%29_Ukranian.pdf)
  - [EBRD Novus Retail and Logistics project](https://www.ebrd.com/home/work-with-us/projects/psd/51639.html)
  - [OpenStreetMap footprint](https://www.openstreetmap.org/way/1211057658)
  - [Kyiv Independent on the strike](https://kyivindependent.com/ukrainian-supermarket-chain-torn-apart-by-russian-attack//)

#### Veggy Trend Invest vegetable storehouse
- asset type: `logistics_hub`
- why:
  - single-function inland food-storage site
  - strong civilian story for Kyiv-region fresh-food supply
  - cleaner semantics than mixed logistics parks
- status: `hold_address_anchor_parcel_not_locked`
- coordinates:
  - strongest current address-zone clue:
    - `50.595098, 30.857445`
- notes:
  - public company sources place the storehouse at `Soborna St. 111, Velyka Dymerka`
  - municipal emergency-planning records also place mixed industrial activity at `Soborna 111A`
  - source trail says the complex includes:
    - vegetable storehouse
    - weigh-house
    - substation
    - open reservoir
    - pumping-station premises
  - first wide local SimSat scout on the strongest current road-segment clue was not enough:
    - pre `2022-03-08T09:06:16Z` with `81.201971` cloud
    - post `2022-04-07T09:06:13Z` with `38.7281` cloud
    - later post `2022-04-22T09:06:07Z` with `99.042356` cloud
  - result:
    - semantics are promising
    - address truth is good
    - parcel lock is still not good enough for a real row
    - campus now reads mixed, not clearly single-function
    - stop probing until one better parcel clue appears inside the Soborna `111/111A` industrial campus
- sources:
  - [The Page dossier on Veggy Trend Invest](https://en.thepage.ua/dossier/vegi-trend)
  - [UACRISIS note on the warehouse burning during shelling](https://uacrisis.org/en/march-2022/10)
  - [Velyka Dymerka emergency-planning annex](https://vdsr.gov.ua/sites/vdsr.gov.ua/files/document_files/%D0%B4%D0%BE%D0%B4%D0%B0%D1%82%D0%BE%D0%BA%20%D1%80%D1%96%D1%88%D0%B5%D0%BD%D0%BD%D1%8F%20%E2%84%96%20219%20%D0%BF%D0%BB%D0%B0%D0%BD.pdf)

#### Roshen Yahotyn logistics center
- asset type: `logistics_hub`
- why:
  - exact finished-goods food logistics campus
  - much cleaner semantics than mixed industrial parks
  - direct civilian-supply relevance
- status: `added_to_non_demo_eval_as_exact_inland_food_anchor`
- coordinates:
  - Roshen public map marker:
    - `50.245008, 31.814647`
- notes:
  - exact public address:
    - `Filatova 112-B, Yahotyn, Kyiv Oblast`
  - Roshen's own site exposes an exact map marker for the logistics center
  - bounded local SimSat passes finally produced an honest event pair:
    - clean pre:
      - `2025-08-31T09:06:35Z` with `0.001755` cloud
    - clean post:
      - `2026-03-14T08:56:26Z` with `1.198145` cloud
  - earlier blockers are still useful context:
    - `2026-01-16T09:06:21Z` was clean but snow-dominated
    - `2025-11-14T08:56:33Z` still obscured too much of the parcel
  - earlier and later checks were mostly unusable:
    - `2026-02-07T08:56:18Z` with `99.993944` cloud
    - `2026-02-17T08:56:20Z` with `99.962109` cloud
    - `2026-03-04T08:56:24Z` with `95.539671` cloud
    - `2026-03-19T09:06:42Z` with `99.980569` cloud
    - `2026-04-03T08:56:24Z` with `87.620318` cloud
  - result:
    - parcel truth is strong
    - event semantics are strong
    - promoted into `non_demo_eval.jsonl` as a real inland food-distribution positive
- sources:
  - [Roshen logistics center page](https://www.roshen.com/ua/uk/kontakty/logistychnyy-kompleks)
  - [Mercor project page for the Roshen logistics center](https://mercor.com.ua/project/logistychnyj-czentr-roshen/)
  - [Ukrainska Pravda on the 2026-02-07 strike](https://www.pravda.com.ua/eng/news/2026/02/07/8019840/)
  - [Interfax-Ukraine follow-up](https://en.interfax.com.ua/news/general/1142921.html)

#### Gedaref Grain Silos
- asset type: `grain_storage_complex`
- why:
  - huge one-function inland grain-storage complex
  - better fixed-site food semantics than most mixed warehouse leads
  - strong control/search-seed value because parcel truth and archive coverage are both clean
- status: `added_to_non_demo_eval_as_exact_food_control`
- coordinates:
  - `14.026667, 35.365000`
- notes:
  - local SimSat archive is strong enough for a clean control pair:
    - baseline `2024-01-09T08:16:09Z` with `0` cloud
    - current `2024-06-07T08:16:19Z` with `0` cloud
  - promoted as an exact food no-event control row
  - no named civilian disruption event tied directly to the silo complex was found through `2026-04-19`
  - keep the older west-shifted public pin as a caution:
    - exact complex confidence is good enough for the control row
    - but not tight enough to claim a positive event without direct source lock
- sources:
  - [Wikimapia parcel clue](https://wikimapia.org/13505027/Gadarif-Grain-Silos-%D8%B5%D9%88%D9%85%D8%B9%D8%A9-%D8%A7%D9%84%D9%82%D8%B6%D8%A7%D8%B1%D9%81)
  - [Alternate older pin](https://wikimapia.org/13985184/Grain-silos)
  - [FEWS NET on Gedaref as largest silo/storage area](https://fews.net/east-africa/sudan/alert/february-2024)
  - [WFP on grain-storage importance in Gedaref](https://www.wfp.org/stories/grain-binds)

#### Manbij Grain Silo Complex
- asset type: `grain_storage_complex`
- why:
  - food function is explicit and fixed-site
  - six-silo compound reads more cleanly than alias-conflicted mill leads
  - clean April/June archive is usable enough for an honest no-event control
- status: `added_to_non_demo_eval_as_exact_control`
- coordinates:
  - `36.507778, 37.961389`
- notes:
  - exact public parcel clue and food-storage function held up
  - initial March return on the exact clue was too hazy to trust:
    - request `2024-03-12T08:00:00Z` -> returned `2024-03-10T08:29:51Z` with `37.791413` cloud
  - cleaner local pair on the same exact clue:
    - baseline request `2024-04-05T08:00:00Z` -> returned `2024-04-04T08:29:52Z` with `12.025507` cloud
    - current request `2024-06-13T08:00:00Z` -> returned `2024-06-10T08:20:05Z` with `0.003497` cloud
  - result:
    - no named civilian disruption event tied directly to the complex was found through `2026-04-19`
    - the exact six-silo compound reads materially stable in the cleaner April/June pair
    - this is now an exact conflict-adjacent food no-material-change control, not a positive row
- sources:
  - [Wikimapia parcel clue](https://wikimapia.org/31562913/Manbij-Grain-Silo-Complex)
  - [North Press on the complex and capacity](https://npasyria.com/en/60094/)

#### Vasyshcheve ATB distribution center / Promyslova corridor
- asset type: `logistics_hub`
- why:
  - stronger civilian-user story than another seaport: grocery distribution near Kharkiv population
  - source trail is food-specific, not a vague industrial hit
  - one of the better candidates for “something is wrong near my region” if the parcel match becomes exact
- status: `added_to_non_demo_eval_as_ambiguity_control`
- notes:
  - strongest exact parcel clue is now `АТБ-Маркет` distribution center, `Васищеве, вул. Промислова, 12`
  - exact parcel is now source-locked, not guessed:
    - official project / build records for the ATB distribution center at `Промислова, 12`
    - cadastral number `6325156400:02:001:0045`
  - source-backed function is clean: packaged food products, dry and cold warehouses, total footprint `30,946 m²`
  - clean exact-address pair now exists on the `Promyslova 12` seed:
    - baseline request `2025-07-10T08:00:00Z` -> returned `2025-07-09T08:46:17Z` with `0.560781` cloud
    - post request `2025-08-12T08:00:00Z` -> returned `2025-08-08T08:46:17Z` with `0.516654` cloud
  - result on the exact-address crop: still too soft for promotion; no single warehouse scar reads strongly enough at `1.0 km` or `0.5 km`
  - a nearby corridor crop around `49.849286, 36.326572` shows clearer roof darkening on a warehouse block:
    - baseline request `2025-07-10T08:00:00Z` -> returned `2025-07-09T08:46:17Z` with `0.560781` cloud
    - post request `2025-08-08T08:00:00Z` -> returned `2025-08-05T08:46:32Z` with `8.039406` cloud
  - but that clearer scar is not yet tied tightly enough to `Promyslova 12`, `Promyslova 11`, or another named food parcel in the strike cluster
  - result:
    - not honest enough for a positive row
    - honest enough for `non_demo_eval.jsonl` as a `food` ambiguity control
    - use it to teach the model and reviewers that nearby warehouse darkening is not enough when the named parcel itself does not resolve cleanly
- sources:
  - [RBC-Ukraine, 2025-07-30](https://newsukraine.rbc.ua/news/deadly-russian-missile-strike-destroys-food-1753896187.html)
  - [Novynarnia, 2025-07-30](https://novynarnia.com/2025/07/30/rosiyany-zavdaly-raketnogo-udaru-po-skladah-troh-korporaczij-u-vasyshhevomu-pid-harkovom-zagynuv-ohoronecz-sered-8-poranenyh-ryatuvalnyky/)
  - [Kharkiv ODA EIA notice, Promyslova 12](https://kharkivoda.gov.ua/oblasna-derzhavna-administratsiya/struktura-administratsiyi/strukturni-pidrozdili/486/2841/2842/3281/105012)
  - [E-construction record, cadastral parcel `6325156400:02:001:0045`](https://e-construction.gov.ua/document_detail/doc_id=2596737942282045406/optype=100)
  - [ATB tender, RC Kharkiv-24, Promyslova 12](https://www.atbmarket.com/tender/2447)
  - [Bezliudivka KTEB note, Promyslova 12](https://khbsr.gov.ua/wp-content/uploads/2025/06/misczeva-kteb-i-ns-%E2%84%96-4-vid-02.06.2025.pdf)

#### al-Khayrat Mill
- asset type: `flour_mill`
- why:
  - tighter food semantics than generic warehousing
  - explicit bread-chain impact: flour sacks prepared for bakeries in Hasakah and its countryside
  - one named civilian facility, one named owner, one named strike event
- status: `reject_exact_geocode_conflict`
- notes:
  - source trail is good enough to keep alive:
    - facility name `al-Khayrat Mill`
    - near `Sanjak Saadoun` / `Sanjak Khalil` in the Amuda countryside
    - struck by Turkish drone on `2024-01-14`
    - mill knocked out of service, workers injured
  - immediate January pair is not honest enough:
    - request `2024-01-05T10:00:00Z` -> returned `2024-01-04T08:09:53Z` with `96.378195` cloud
    - request `2024-01-20T10:00:00Z` -> returned `2024-01-19T08:09:44Z` with `75.847393` cloud
  - but the broader village seed stays alive because later windows clear:
    - baseline request `2023-12-28T10:00:00Z` -> returned `2023-12-25T08:09:54Z` with `12.489839` cloud
    - post request `2024-02-05T10:00:00Z` -> returned `2024-02-03T08:09:50Z` with `7.132044` cloud
    - later post request `2024-03-05T10:00:00Z` -> returned `2024-03-04T08:09:48Z` with `0.008427` cloud
  - hard alias pass failed:
    - North Press says near `Sanjak Saadoun`
    - Rojava TV and another North Press report say `Sanjak Khalil`
    - OSM only resolves `Sanjak Saadoun` to a village node at `37.0186198, 40.9357151`, currently labeled `راية غربي`
    - no defendable exact mill parcel emerged from public map/geocode clues
  - article photos confirm a real flour mill interior and roof damage, but do not anchor the parcel tightly enough for satellite labeling
  - result: food semantics are good and weather is no longer the blocker, but exact geocoding failed after one hard map pass
  - drop as an active eval candidate unless a direct map/address/parcel clue appears later
- sources:
  - [North Press, 2024-01-17](https://npasyria.com/en/110223/)
  - [North Press Arabic, 2024-01-17](https://npasyria.com/178716/)
  - [Rojava TV, 2024-01-21](https://rojavatv.net/ar/archives/23693)
  - [ASO Network, 2023-01-15](https://aso-network.com/en/archives/33270)

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

#### Al-Khafsa Water Treatment Plant
- asset type: `water_infrastructure`
- why:
  - one of Aleppo's main drinking-water sources
  - strongest city-serving pure-water lead tried so far
  - exact positive hunt mattered because this is the kind of user-value case Blackline should catch if Sentinel can honestly show it
- status: `hold_no_honest_macro_change`
- notes:
  - hard map pass found a large treatment-like compound south of Al-Khafsa town around `36.1839511, 38.0086273`
  - clue quality remains imperfect because the public map tag is only `man_made=wastewater_plant`, not a named plant polygon
  - clean `2.0 km` SimSat pair exists on that clue:
    - baseline request `2025-01-30T08:00:00Z` -> returned `2025-01-26T08:20:27Z` with `0.009107` cloud
    - current request `2025-03-15T08:00:00Z` -> returned `2025-03-12T08:20:01Z` with `0.006421` cloud
  - result:
    - no honest macro-visible damage on the compound in the clean pair
    - wider `5.0 km` crop suffered tile-edge / no-data artifacts
  - keep as ambiguity evidence, not a positive row
- sources:
  - [UNICEF on Al-Khafsa serving Aleppo](https://www.unicef.org/syria/stories/unicef-rehabilitates-conflict-damaged-sedimentation-tanks-enhance-production-treated-water)
  - [ICRC on Al-Khafsa water station role](https://www.icrcnewsroom.org/story/en/2058/syria-urgent-action-needed-to-address-humanitarian-needs)
  - [SNHR on `2025-02-23` damage to the station main building](https://news.snhr.org/2025/02/24/sdf-bomb-a-water-station-in-e-aleppo-february-23-2025/)

#### Maisat / Wazzani Water Project
- asset type: `water_infrastructure`
- why:
  - report-backed city-serving water lifeline
  - the strongest Lebanon water story we have found so far
  - useful to keep because it serves around `150,000` people in over `30` towns and villages
- status: `hold_border_sensitive_and_parcel_soft`
- coordinates:
  - `Maisat` village clue: `33.2626526, 35.6193188`
  - `Wazzani` locality clue: `33.26112, 35.62242`
- dates probed:
  - pre request `2024-01-25T08:00:00Z` -> returned `2024-01-20T08:30:58Z`
  - post request `2025-03-15T08:00:00Z` -> returned `2025-03-10T08:31:22Z`
- notes:
  - the VoiceEU / Insecurity Insight report explicitly names:
    - the `Maisat water pumping station`
    - the associated `Wazzani water intake centre`
  - first `1.5 km` sweeps around village / locality / guessed station / guessed intake proved the story is real, but not yet exact enough for a positive eval row
  - current-side cloud was moderate (`26.562682`) and the lane remains too close to the Lebanon border for the first clean Blackline water-positive case
  - keep as evidence only until:
    - one exact parcel anchor is locked
    - and the promoted row can be framed as civilian water lifeline monitoring, not border-adjacent infrastructure watching
- sources:
  - [VoiceEU report on Maisat and Wazzani damage](https://voiceeu.org/publications/when-bombs-turn-the-taps-off-the-impact-of-conflict-on-water-infrastructure-in-lebanon.pdf)
  - [Xinhua on destruction of the Wazzani pumping project](https://english.news.cn/20250309/cb1745da21c243569ba1aa796c5ba018/c.html)

#### Bahri Water Treatment Plant
- asset type: `water_infrastructure`
- why:
  - better product fit than the Lebanon border lane
  - exact city-serving plant
  - strong civilian-useful story for Khartoum North residents
- status: `added_to_non_demo_eval_as_exact_control`
- coordinates:
  - `15.6169, 32.5347`
- dates probed:
  - pre request `2023-12-01T08:00:00Z` -> returned `2023-11-28T08:25:46Z`
  - mid request `2024-12-01T08:00:00Z` -> returned `2024-11-27T08:25:47Z`
  - post request `2025-03-29T08:00:00Z` -> returned `2025-03-27T08:26:11Z`
- notes:
  - exact lead comes from `Khartoum State Water Corporation Bahri Station`
  - clean `3.0 km` and `1.5 km` sweeps are already available with near-zero cloud
  - a follow-up `0.8 km` parcel-tight `3x3` grid around the lead also failed to isolate one defendable plant-compound scar inside the dense urban fabric around the Nile-edge site
  - good source trail and perfect cloud were strong enough for an exact no-material-change control, but not for a positive row
  - landed in `non_demo_eval.jsonl` as `bahri_water_station_no_material_change`
  - only reopen if a stronger plant polygon or independent parcel anchor appears for a future positive row
- sources:
  - [Sudan Tribune on heavy damage to Bahri water station](https://sudantribune.com/archives/296726)
  - [Wikimapia lead for Khartoum State Water Corporation Bahri Station](https://wikimapia.org/891493/Khartoum-State-Water-Corporation-Bahri-Station)

#### Kosti New Water Treatment Plant (JICA)
- asset type: `water_infrastructure`
- why:
  - strong civilian-useful case
  - named pure drinking-water plant
  - attack-linked outage tied to cholera spread
- status: `hold_plausible_parcel_no_structural_signal`
- coordinates:
  - strongest current parcel clue: `13.1601864, 32.6865113`
- notes:
  - still one of the best water leads after `Bahri`, but no longer the active next pass
  - named locally as `محطة مياه كوستي الجديدة` / `محطة جايكا الجديدة`
  - JICA brochure confirms the real facility should read as a riverfront treatment campus with intake, sedimentation, filtration, and reservoir blocks
  - strongest current clue is a plausible riverfront utility compound, but the morphology still does not match that brochure cleanly enough
  - tight parcel pair on the clue:
    - baseline request `2025-01-20T08:00:00Z` -> returned `2025-01-16T08:26:31Z` with `40.911147` cloud
    - current request `2025-03-29T08:00:00Z` -> returned `2025-03-27T08:26:54Z` with `0.280961` cloud
  - result:
    - no defendable roof loss, basin breach, burn scar, or compound-wide debris field
    - change reads as weak parcel match plus weather / land-cover shift, not structural plant damage
  - keep as evidence only unless a better parcel lock or cleaner baseline appears
- sources:
  - [AP on the Kosti outage and cholera surge](https://apnews.com/article/47ac3f39c10eb549785c7fc24608551a)
  - [JICA project page for the Kosti treatment plant](https://www.jica.go.jp/english/our_work/social_environmental/id/africa/sudan/c8h0vm00009u5bwh.html)
  - [Sudan Events on Kosti's new drinking-water station / JICA](https://sudanevents.com/index.php/2024/08/16/resumption-of-operations-at-the-new-drinking-water-station-in-kosti/)

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
- status: `hold_river_corridor_still_soft`
- coordinates:
  - Babiri village seed: `36.1254475, 38.0005080`
- dates probed:
  - baseline request `2025-12-20T08:00:00Z` -> returned `2025-12-17T08:30:11Z`
  - current request `2026-01-10T08:00:00Z` -> returned `2026-01-06T08:20:12Z`
- notes:
  - current source trail now says the station lies on the Euphrates between `Qafsa / Khafsa` and `Maskana / Meskene`, east of Aleppo
  - keep as a geocode lane only until exact site identity, coordinates, and honest Sentinel-scale change are verified
  - do not label from outage claims alone
  - first current-side probe was heavily clouded (`80.994809`)
  - first `1.5 km` locator sweep around the Babiri village seed on `2025-01-30T08:00:00Z` did not isolate the station parcel
  - one bounded follow-up `0.8 km` `3x3` river-corridor sweep around the nearest dark riverbank utility band also failed to show a defendable `intake + basins + reservoir` footprint
  - likely risk:
    - service interruption matters to users
    - but the site may still lack a clean structural before/after signal at Sentinel scale
  - result:
    - strong service story
    - weak parcel story
  - next step only if a stronger parcel clue appears from independent mapping
- sources:
  - [SANA, 2026-01-10](https://sana.sy/en/syria/2289847/)
  - [A News, 2026-01-11](https://www.anews.com.tr/middle-east/2026/01/11/syria-restores-water-supply-to-aleppo-after-sdf-disruption)
  - [Levant24, 2026-01-24](https://levant24.com/news/2026/01/syria-boosts-water-security-through-major-infrastructure-projects/)
  - [Türkiye Today, 2026-01-11](https://www.turkiyetoday.com/region/sdf-uses-water-control-as-leverage-as-syrian-armys-operations-could-expand-north-3212792)

#### Southern Gaza Seawater Desalination Plant
- asset type: `water_infrastructure`
- why:
  - one of the strongest remaining user-value water leads
  - city-serving civilian desalination plant for central and southern Gaza
  - later reporting ties it directly to major water loss for hundreds of thousands of civilians
- status: `hold_sensitive_outage_story`
- notes:
  - facility identity is stronger than most remaining water leads
  - current strongest geography clues:
    - on the coastal road
    - south / southwest of Deir al-Balah
    - within the southwestern Deir al-Balah evacuation zone in July 2025 reporting
  - current blocker is still honesty, not relevance:
    - public evidence centers on power-line / cable damage and output collapse
    - not yet a proven plant-structure damage row
  - bounded coastal sweeps were enough to keep the corridor alive, but not enough to defend one exact plant parcel
  - exact-parcel hunting here risks turning an outage-led humanitarian story into utility-network / siege analysis
  - keep only as backlog evidence unless:
    - one exact public parcel or facility polygon is already disclosed in humanitarian / utility documentation
    - and visible plant / service-compound damage can be separated from cable / outage reporting
- sources:
  - [AP on the March 2025 electricity cutoff](https://apnews.com/article/ba90f0de3d4f64a1762d1a39f787817f)
  - [UNICEF on March 2026 cable damage and 80 per cent output drop](https://www.unicef.org/sop/stories/unicef-restores-water-access-tens-thousands-children-gaza)
  - [Sawa on the site being on the coastal road south of Deir al-Balah](https://palsawa.com/post/99981/%D8%A7%D9%84%D8%A7%D8%AD%D8%AA%D9%81%D8%A7%D9%84-%D8%A8%D8%A7%D9%81%D8%AA%D8%AA%D8%A7%D8%AD-%D9%85%D8%AD%D8%B7%D8%A9-%D8%AA%D8%AD%D9%84%D9%8A%D8%A9-%D9%85%D9%8A%D8%A7%D9%87-%D8%A7%D9%84%D8%A8%D8%AD%D8%B1)
  - [ieCRES 2023 on the plant being at the coastal road in front of Deir El-Balah](https://eftaa.iugaza.edu.ps/wp-content/uploads/sites/20/2023/07/ieCRES-2023_paper_4560.pdf)
  - [Al Mezan on the plant falling inside the southwestern Deir al-Balah evacuation zone](https://www.mezan.org/public/en/post/46743/Israel%E2%80%99s-New-Displacement-Order-Targets-Gaza%E2%80%99s-Largest-Desalination-Plant%2C-Escalating-Genocide-Through-Mass-Dehydration)

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
