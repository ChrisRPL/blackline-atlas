# Aid Tranche 01

Purpose:

- fill the next highest-value coverage gap after soft water churn
- move `aid_02` from one small Lebanon lead into a real inland exact-site board
- prefer named humanitarian compounds over generic logistics

## Current aid truth

- promoted aid rows: `1`
  - `Port Sudan Aid Hub`
- inland aid positives: `0`
- exact aid / medical-aid controls:
  - `UNHCR Baghdad Warehouse`
  - `Mosul Medical City Hospital`
- strongest current positive repo lead:
  - `WFP El Obeid logistics base / Agricultural Bank of Sudan warehouse complex`

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
  - `hold_exact_complex_not_yet_pinned`
- next action:
  - first public-map pass pinned `El Obeid Airport` at `13.1500332, 30.2317358`, but did not isolate the ABS warehouse complex itself
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

## Immediate next work order

1. keep `aid_01` `El Obeid` on hold unless the ABS complex itself becomes publicly mappable
2. keep `aid_02` `Lankien` as evidence only unless a larger hospital-support warehouse campus is publicly pinned
3. keep `Tyre` only if scale permits
4. `UNHCR Baghdad` and `Mosul Medical City` are now the exact aid / medical-aid control anchors
5. if no inland aid positive survives, reopen inland `food` before adding more aid notes

## Stop rules

- one hard map/geocode pass only per candidate before downgrade
- do not promote any aid node whose value depends on route, convoy, or corridor analysis
- if no inland parcel-tight aid lead survives, stop and reopen inland food before adding more aid notes
