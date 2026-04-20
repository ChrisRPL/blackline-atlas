# Aid Tranche 01

Purpose:

- fill the next highest-value coverage gap after soft water churn
- move `aid_02` from one small Lebanon lead into a real inland exact-site board
- prefer named humanitarian compounds over generic logistics

## Current aid truth

- promoted aid rows: `2`
  - `Port Sudan Aid Hub`
  - `Okhmatdyt Children's Hospital`
- inland aid positives: `1`
- exact aid / medical-aid controls:
  - `UNHCR Baghdad Warehouse`
  - `Mosul Medical City Hospital`
- strongest current inland repo lead:
  - `Saudi Teaching Maternal Hospital`, `El Fasher`
  - exact parcel locked
  - still not promotion-ready

Rule:
- aid next should be:
  - inland or clearly non-border-adjacent
  - named operator
  - warehouse-led or medical-aid storage-led
  - parcel-tight enough for a defendable bbox

## Candidate rules

Keep:

- `WFP / UN / UNHCR / ICRC / Red Cross / Red Crescent / MSF` compounds
- warehouse clusters
- medical-aid storage nodes
- relief-supply depots serving a city, camp belt, or humanitarian region

Reject:

- border warehouses
- convoy staging yards
- route chokepoint depots
- multi-tenant logistics parks
- port-adjacent aid compounds
- airport-adjacent aid compounds
- anything where the interesting question becomes `how does aid move?` instead of `did this civilian aid node get disrupted?`

## Promotion candidates

### `aid_01` WFP El Obeid logistics base / Agricultural Bank of Sudan warehouse complex

- country:
  - `Sudan`
- type:
  - `aid_warehouse_cluster`
- why:
  - strongest inland humanitarian logistics lead from current docs
  - WFP describes `El Obeid` as one of its largest logistics bases in Africa
  - useful civilian story without defaulting to ports
- parcel state:
  - exact complex name is public:
    - `Agricultural Bank of Sudan Warehouse Complex`
  - Logistics Cluster describes:
    - `5` concrete warehouses
    - `3` rented by WFP
    - `5 km` outside town
    - `10 km` from airport
- status:
  - `hard_hold_exact_complex_not_yet_pinned`
- next action:
  - first public-map pass pinned `El Obeid Airport` at `13.1500332, 30.2317358`, but did not isolate the ABS warehouse complex itself
  - second bounded review still did not produce a direct parcel clue for the ABS complex
  - do not probe until one public map clue or polygon names the warehouse complex directly
  - keep only if the compound can be isolated as a humanitarian warehouse campus, not a corridor/logistics-routing story
- sources:
  - [WFP on looting of warehouses in El Obeid](https://www.wfp.org/news/statement-looting-humanitarian-warehouses-sudan)
  - [Logistics Cluster on Potential HUB - El Obeid](https://logcluster.org/en/documents/potential-hub-el-obeid)
  - [WFP Special Operation noting main logistics hub in El Obeid](https://one.wfp.org/operations/current_operations/project_docs/200497.pdf)

### `aid_02` MSF Lankien hospital main warehouse

- country:
  - `South Sudan`
- type:
  - `medical_aid_node`
- why:
  - exact named humanitarian medical compound
  - attack explicitly destroyed the hospital's main warehouse
  - better civilian-use story than vague regional warehouse talk
- parcel state:
  - exact locality is public:
    - `Lankien`, `Jonglei State`
  - strongest current parcel clue:
    - Nominatim resolves `Medicines Sans Frontieres Lankien` to `8.5267054, 32.0611465`
- status:
  - `hold_too_small_soft_for_sentinel`
- next action:
  - bounded Sentinel verification found a real built cluster at the resolved coordinates
  - but the cluster is too small and too embedded in village texture to defend as a compound-scale humanitarian warehouse node
  - one pre/post pair around the exact clue did not show honest macro-visible warehouse or campus damage
  - keep only as evidence unless a larger hospital-support campus or explicit warehouse polygon appears
- sources:
  - [MSF on Lankien hospital bombardment and warehouse destruction](https://www.msf.org/msf-hospital-bombarded-government-forces-south-sudan)
  - [MSF on Lankien facility evacuation after airstrikes](https://www.msf.org/south-sudan-msf-evacuates-staff-lankien-healthcare-facility-following-airstrikes)

### `aid_03` Tyre Red Cross center

- country:
  - `Lebanon`
- type:
  - `medical_aid_node`
- why:
  - named civilian emergency-response facility
  - direct humanitarian role obvious to civilians
  - current-conflict relevance is strong
- parcel state:
  - facility identity is public
  - parcel scale still uncertain
- status:
  - `hold_scale_risk`
- next action:
  - keep only if compound scale looks warehouse-yard sized, not office/clinic sized
  - one bounded Sentinel pair on the exact Tyre clue still read too small / too weather-limited for a defendable aid row
  - otherwise drop in favor of a larger inland aid depot
- sources:
  - [Reuters pickup on strike at Tyre Red Cross center](https://wsau.com/2026/04/13/red-cross-calls-consecutive-strikes-in-lebanon-gravely-concerning/)
  - [Reuters Connect aftermath record](https://www.reutersconnect.com/item/refile-aftermath-of-an-israeli-strike-on-a-lebanese-red-cross-centre-in-tyre/dGFnOnJldXRlcnMuY29tLDIwMjY6bmV3c21sX1ZBMjE0MDEzMDQyMDI2UlAx)

### `aid_04` UNHCR warehouse in Al Shaljia, Iraqi Railway complex area

- country:
  - `Iraq`
- type:
  - `aid_warehouse_cluster`
- why:
  - exact official warehouse lead from UNHCR procurement docs
  - good inland benchmark candidate if current-conflict leads stay soft
  - useful as a future control or benchmark even if not promoted as a conflict-positive row
- parcel state:
  - official document gives:
    - `UNHCR Warehouse in Al Shaljia, Iraqi Railway complex area, Baghdad, Iraq`
    - GPS `33.34150243963263, 44.36504131109288`
- status:
  - `promoted_to_non_demo_eval_as_benchmark_control`
- next action:
  - exact official GPS was usable:
    - `33.34150243963263, 44.36504131109288`
  - bounded SimSat pass returned a clean stable pair on the exact parcel:
    - baseline request `2024-08-05T08:00:00Z` -> returned `2024-08-05T07:50:48Z` with `0.024484` cloud
    - current request `2024-10-01T08:00:00Z` -> returned `2024-09-29T07:50:48Z` with `0.015073` cloud
  - result:
    - no defendable roof loss
    - no burn scar
    - no yard disruption
    - honest exact aid benchmark / control row
- sources:
  - [UNHCR Iraq corrigendum for Baghdad warehouse works](https://www.unhcr.org/iq/wp-content/uploads/sites/165/2024/07/Corrigendum-No.1-RFQ-076-s-1.pdf)

### `aid_05` WFP Al-Ghafari warehouse

- country:
  - `Gaza`
- type:
  - `aid_warehouse_cluster`
- why:
  - exact named WFP warehouse
  - strong humanitarian relevance
- parcel state:
  - warehouse identity is public:
    - `Al-Ghafari warehouse`
    - `Deir Al-Balah`
- status:
  - `hold_sensitive_route_story`
- next action:
  - keep as evidence only
  - do not make this the active next parcel hunt because hunger/blockade/routing questions overwhelm parcel-level aid-node monitoring
- sources:
  - [WFP statement on incident at Al-Ghafari warehouse](https://www.wfp.org/news/statement-incident-wfp-warehouse-gaza)

### `aid_06` Mosul Medical City Hospital

- country:
  - `Iraq`
- type:
  - `medical_aid_node`
- why:
  - exact inland medical campus with obvious civilian-use framing
  - large enough to matter on the watchlist
  - useful as a strict ambiguity control for broader urban battle damage
- parcel state:
  - exact Airwars coordinates:
    - `36.3570248, 43.116703`
- status:
  - `promoted_to_non_demo_eval_as_ambiguity_control`
- next action:
  - clean pair exists:
    - baseline request `2017-02-15T10:00:00Z` -> returned `2017-02-11T07:55:46Z` with `30.921766` cloud
    - current request `2017-02-25T10:00:00Z` -> returned `2017-02-21T07:58:34Z` with `2.300551` cloud
  - result:
    - visible large-area damage surrounds the medical campus
    - but the exact hospital parcel cannot be separated defensibly from broader city destruction in Sentinel
    - useful exact inland medical-aid ambiguity control, not a positive row
- sources:
  - [Airwars on Mosul Medical City Hospital strike](https://airwars.org/civilian-casualties/ci463-february-17-2017/)

### `aid_07` MSF Mother and Child Hospital, Taiz

- country:
  - `Yemen`
- type:
  - `medical_aid_node`
- why:
  - exact named humanitarian medical facility
  - direct civilian-health framing
  - useful retrospective medical-aid benchmark if archive truth exists
- parcel state:
  - exact incident documentation publishes facility location
  - current working coordinates:
    - `13.609017, 44.096997`
- status:
  - `hold_archive_not_available`
- next action:
  - bounded local SimSat pass on the exact parcel across `2015-11` to `2016-01` returned no usable historical images
  - keep only if archive coverage broadens; do not spend more time on parcel-hunting
- sources:
  - [MSF Taiz incident report](https://www.msf.org/sites/default/files/taiz_airstrike_clinic.pdf)
  - [MSF on the Taiz clinic attack](https://www.msf.org/yemen-nine-wounded-saudi-led-coalition-airstrike-msf-clinic-taiz)

### `aid_08` MSF Kunduz Trauma Centre

- country:
  - `Afghanistan`
- type:
  - `medical_aid_node`
- why:
  - exact iconic destroyed hospital
  - useful retrospective medical-aid benchmark if archive truth exists
- parcel state:
  - exact MSF-published coordinates:
    - `36.71803, 68.86221`
- status:
  - `hold_archive_not_available`
- next action:
  - bounded local SimSat pass across `2015-09` to `2016-01` returned no usable historical images
  - keep only if archive coverage broadens; do not spend more time on this lead now
- sources:
  - [MSF published Kunduz coordinates](https://www.msf.org/kunduz-afghanistan-36%C2%B043%E2%80%99491%E2%80%99%E2%80%99n-68%C2%B051%E2%80%994396%E2%80%99%E2%80%99)
  - [MSF on the Kunduz hospital attack](https://www.msf.org/kunduz-hospital-attack)

### `aid_09` Saudi Teaching Maternal Hospital, El Fasher

- country:
  - `Sudan`
- type:
  - `medical_aid_node`
- why:
  - exact named civilian hospital
  - MSF-supported during the siege of El Fasher
  - one of the clearest inland current-conflict medical-aid leads in the repo lane
- parcel state:
  - exact OSM hospital polygon exists
  - current parcel anchor:
    - `13.6299070, 25.3298850`
- status:
  - `hold_exact_parcel_signal_too_mixed`
- next action:
  - bounded local SimSat pass returned a usable pre/post pair on the exact parcel:
    - baseline request `2024-07-15T08:00:00Z` -> returned `2024-07-14T08:56:32Z` with `17.404674` cloud
    - current request `2024-08-20T08:00:00Z` -> returned `2024-08-18T08:56:29Z` with `9.6509` cloud
  - bounded bbox review failed the honesty bar:
    - parcel-level mean change stayed lower than the surrounding ring
    - visible disruption reads broader urban/front-line context, not hospital-compound-specific damage
  - exact parcel truth is stronger than `El Obeid`, but the Sentinel signal is still too mixed for promotion
  - caution:
    - AP reports the hospital sits just north of El Fasher airport and near the front lines
    - that proximity increases the risk of reading generalized siege damage as hospital-specific disruption
- sources:
  - [MSF on repeated attacks on Saudi hospital in El Fasher](https://www.msf.org.za/news-and-resources/latest-news/hospitals-are-damaged-and-closed-el-fasher-fighting-rages)
  - [MSF on shelling that damaged the hospital pharmacy](https://www.msf-me.org/media-centre/news-and-stories/sudan-fighting-el-fasher-remains-incessant-despite-unsc-resolution)
  - [AP on the January 2025 Saudi hospital attack](https://apnews.com/article/sudan-war-hospital-attack-fasher-53f41de57ca442ed5dd3a8a1312f4052)
  - [OpenStreetMap / Nominatim parcel anchor](https://nominatim.openstreetmap.org/ui/details.html?osmtype=W&osmid=1447266861)

### `aid_10` Urum al-Kubra SARC / UN aid warehouse compound

- country:
  - `Syria`
- type:
  - `aid_warehouse_cluster`
- why:
  - exact humanitarian warehouse compound
  - strongest exact inland warehouse lead discovered in this search pass
  - low tactical drift in source framing
- parcel state:
  - exact geolocated compound:
    - `36.151583, 36.967750`
- status:
  - `hold_archive_not_available`
- next action:
  - local SimSat pass across `2016-09` to `2016-10` returned no usable historical images
  - keep as the best retrospective aid-warehouse lead if archive coverage broadens
- sources:
  - [Bellingcat geolocation of the Urum al-Kubra warehouse compound](https://www.bellingcat.com/news/middle-east/2016/09/21/aleppo-un-aid-analysis/)
  - [UN Board of Inquiry summary](https://digitallibrary.un.org/record/853646/files/S_2016_1093-EN.pdf)
  - [Human Rights Watch on the convoy/warehouse attack](https://www.hrw.org/news/2016/09/20/syria-investigate-attack-un-aid-convoy)

### `aid_11` MSF-supported Abs hospital

- country:
  - `Yemen`
- type:
  - `medical_aid_node`
- why:
  - exact named MSF-supported hospital compound
  - strong civilian caseload and protected-status documentation
- parcel state:
  - exact public map anchor:
    - `16.0034, 43.19697`
- status:
  - `hold_archive_not_available`
- next action:
  - local SimSat pass across `2016-08` to `2016-09` returned no usable historical images
  - keep only as a retrospective medical-aid lead
  - extra caution:
    - map context places it roughly `2.5 km` from Abbs airport, so keep the read hospital-only if this ever reopens
- sources:
  - [MSF investigation of the Abs hospital attack](https://www.msf.org/sites/default/files/2018-05/yemen_abs_investigation.pdf)
  - [MSF attack statement](https://www.msf.org/yemen-eleven-people-dead-and-least-19-injured-after-airstrike-hits-abs-hospital-hajjah)
  - [Mapcarta / OSM place anchor](https://mapcarta.com/27241474)

### `aid_12` Okhmatdyt Children's Hospital, Kyiv

- country:
  - `Ukraine`
- type:
  - `medical_aid_node`
- why:
  - best new inland aid lead found after the current board stalled
  - exact named civilian hospital campus
  - very strong humanitarian fit and public-source identity
- parcel state:
  - official address:
    - `V. Chornovola St. 28/1, Kyiv, 01135`
  - exact OSM campus relation exists
  - current centroid anchor:
    - `50.451172, 30.479935`
- status:
  - `added_to_non_demo_eval_as_reference_event`
- next action:
  - bounded local SimSat pass on the campus anchor:
    - pre request `2024-07-01T08:00:00Z` -> returned `2024-06-30T09:06:31Z` with `7.950252` cloud
    - strike-day request `2024-07-08T12:00:00Z` -> returned `2024-07-08T09:16:27Z` with `86.164784` cloud
    - first post request `2024-07-12T08:00:00Z` -> returned `2024-07-10T09:06:29Z` with `20.704573` cloud
    - cleaner post request `2024-07-15T08:00:00Z` -> returned `2024-07-13T09:16:26Z` with `0.132813` cloud
  - result:
    - exact campus is strong enough to keep
    - cleaner post-event frame clears the weather blocker
    - tighter campus review is now strong enough for a real inland medical-aid event row
- sources:
  - [Okhmatdyt official site](https://ohmatdyt.com.ua/en/)
  - [HRW on the July 8, 2024 attack](https://www.hrw.org/news/2024/07/11/russias-july-8-attack-childrens-hospital-ukraine)
  - [OpenStreetMap relation](https://www.openstreetmap.org/relation/4202052)

### `aid_13` Bashtanka Multiprofile Hospital

- country:
  - `Ukraine`
- type:
  - `medical_aid_node`
- why:
  - exact inland hospital campus
  - clean civilian-health framing
  - strong public reporting on the `2022-04-19` strike and outpatient-building destruction
- parcel state:
  - current campus anchor:
    - `47.4109499, 32.4217905`
  - public address clue:
    - `3 Yuvileina St, Bashtanka`
- status:
  - `hold_weather_blocked`
- next action:
  - first bounded local SimSat pass found the immediate event window too clouded:
    - `2022-04-04T08:57:08Z` with `75.286746` cloud
    - `2022-04-19T08:57:02Z` with `97.595614` cloud
    - `2022-05-19T08:57:07Z` with `43.381408` cloud
    - `2022-06-23T08:57:19Z` with `96.213681` cloud
  - keep only as a backup exact inland medical campus unless a later clear post-event window appears
- sources:
  - [PHR on Russia’s assault on Ukraine’s health-care system](https://phr.org/our-work/resources/russias-assault-on-ukraines-health-care-system/)

## Immediate next work order

1. keep `aid_09` `Saudi Teaching Maternal Hospital` as evidence-only unless a tighter hospital-only read emerges
2. keep `aid_01` `El Obeid` frozen until the ABS complex itself becomes publicly mappable
3. keep `aid_02` `Lankien` and `aid_03` `Tyre` as evidence-only, not active parcel hunts
4. keep `aid_07` `Taiz`, `aid_08` `Kunduz`, `aid_10` `Urum`, and `aid_11` `Abs` as archive-blocked retrospective leads only
5. `UNHCR Baghdad` and `Mosul Medical City` are now the exact aid / medical-aid control anchors
6. `aid_12` `Okhmatdyt` now fills the missing inland medical-aid positive slot
7. `aid_13` `Bashtanka` is the cleanest new inland medical backup, but it is weather-blocked today
8. next aid move should be a second exact inland aid positive only if it beats `Okhmatdyt` on parcel truth and readability

## Stop rules

- one hard map/geocode pass only per candidate before downgrade
- do not promote any aid node whose value depends on route, convoy, or corridor analysis
- do not keep retrying archive-blocked retrospective sites unless the archive source changes
- if no inland parcel-tight aid lead survives, stop and reopen inland food before adding more aid notes
