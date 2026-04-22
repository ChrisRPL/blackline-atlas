# 2026 Conflict AOI Triage

Use this to convert broad current-conflict location reporting into Blackline-shaped AOI ideas.

Rules:
- no country-only entries
- no whole-city monitoring
- AOI must be a specific civilian facility or tightly cropped civilian sub-area
- prefer `food`, then `water`, then `aid`, then `mobility`
- reject anything that answers route-open, convoy-flow, or military-sustainment questions faster than civilian-impact questions

## Probe next

### Izmail Danube port rail infrastructure
- raw reporting:
  - Izmail / Odesa region
- likely asset type:
  - `container_port` or future `rail_logistics` sub-AOI
- why a civilian nearby would care:
  - export and supply disruption in the Danube corridor
  - downstream effect on nearby jobs, cargo access, and food trade
- what Sentinel could honestly show:
  - berth-yard burn scars
  - damaged storage footprint
  - macro disruption in rail-adjacent logistics area
- why not promoted yet:
  - still port-shaped
  - needs strict civilian crop and lower tactical drift
- sources:
  - [Reuters pickup, Apr 15 2026](https://wsau.com/2026/04/15/russia-launches-more-than-300-drones-missiles-at-ukraine-overnight/)
  - [Ukrainska Pravda, Apr 14 2026](https://www.pravda.com.ua/eng/news/2026/04/14/8030045/)
- status:
  - `probe`

### Tyre Red Cross center
- raw reporting:
  - Tyre
- likely asset type:
  - future `aid_hub` or `medical_aid_node`
- why a civilian nearby would care:
  - direct hit on emergency medical response capacity
  - obvious humanitarian value
- what Sentinel could honestly show:
  - only if damage is large enough at compound scale
  - likely too small for Sentinel; may need to stay as a policy example, not a model row
- why not promoted yet:
  - size may be too small for an honest Sentinel bbox
  - may be better as a scope boundary example than an eval row
- sources:
  - [Reuters Connect photo record, Apr 13 2026](https://www.reutersconnect.com/item/lebanese-red-cross-offices-hit-by-strike-in-tyre-south-lebanon/dGFnOnJldXRlcnMuY29tLDIwMjY6bmV3c21sX1JDMkNPS0FQWE9XSw)
  - [Reuters pickup, Apr 13 2026](https://wsau.com/2026/04/13/red-cross-calls-consecutive-strikes-in-lebanon-gravely-concerning/)
- status:
  - `probe`

### Nasser Medical Complex
- raw reporting:
  - Khan Younis
- likely asset type:
  - `medical_aid_node`
- why a civilian nearby would care:
  - major referral hospital
  - surgery, ICU, dialysis, transfusion, and cancer-care loss
- exact public clue:
  - fixed hospital campus
  - exact coords: `31.3471, 34.2930`
- what Sentinel could honestly show:
  - compound-scale roof loss
  - burn scar
  - destroyed triage / service yard area
- why not promoted yet:
  - bounded exact-site probe found clean windows
  - current read still looks more like access / operations pressure than a defendable parcel-scale structural scar
  - keep behind `Al-Ahli` for the next promotion pass
- sources:
  - [WHO, 2025-06-05](https://www.who.int/news/item/05-06-2025-who-calls-for-urgent-protection-of-nasser-medical-complex-and-al-amal-hospital-in-the-gaza-strip)
  - [Nasser Hospital coordinates reference](https://en.wikipedia.org/wiki/Nasser_Hospital)
- status:
  - `probe_exact_windows_soft`

### Al-Ahli Arab Hospital
- raw reporting:
  - Gaza City
- likely asset type:
  - `medical_aid_node`
- why a civilian nearby would care:
  - one of the last functioning hospitals in Gaza City
  - repeated attacks degrade northern access to care
- exact public clue:
  - fixed hospital campus
  - exact coords: `31.504889, 34.461639`
- what Sentinel could honestly show:
  - compound roof damage
  - triage-yard / warehouse burn scar
  - destroyed service-vehicle yard
- why not promoted yet:
  - bounded exact-site probe found clean windows and this is now the stronger Gaza hospital candidate
  - still needs one honest parcel-scale Sentinel read before promotion
- sources:
  - [WHO, 2025-05-22](https://www.who.int/news/item/22-05-2025-health-system-at-breaking-point-as-hostilities-further-intensify--who-warns)
  - [Al-Ahli Arab Hospital coordinates reference](https://commons.wikimedia.org/wiki/Category:Al-Ahli_Arab_Hospital)
- status:
  - `probe_exact_windows_rank_1`

## Needs narrowing

These are real conflict signals, but still too broad for Blackline until narrowed to one civilian lifeline facility.

### Ukraine city and region hits
- raw reporting:
  - Kyiv
  - Odesa
  - Dnipro / Dnipropetrovsk region
  - Zaporizhzhia
  - Cherkasy
  - Kharkiv
  - Kryvyi Rih
  - Chernihiv
  - Donetsk region
- why not ready:
  - cities and regions are not AOIs
  - each must be reduced to one named civilian facility or tight sub-area
- useful reframing:
  - grain terminal
  - warehouse cluster
  - water plant
  - bridge only if clearly civilian and non-tactical
- sources:
  - [AP, Apr 16 2026](https://apnews.com/article/russia-ukraine-war-drone-missile-attack-kyiv-10627c3e68677cad65fadd5f2a9f8388)
  - [Reuters pickup, Apr 15 2026](https://wsau.com/2026/04/15/russia-launches-more-than-300-drones-missiles-at-ukraine-overnight/)
- status:
  - `needs_narrowing`

### Lebanon broad return and access areas
- raw reporting:
  - southern suburbs of Beirut
  - villages south of the Litani River
  - Nabatieh
  - Bint Jbeil
- why not ready:
  - city districts and towns are too broad
  - Bint Jbeil in current coverage is mostly a ground-assault / town-control story, not a clean fixed civilian lifeline AOI
- useful reframing:
  - named water station
  - named bakery / food depot
  - named humanitarian compound
  - bridge only with extra caution
- sources:
  - [AP, Apr 17 2026](https://apnews.com/article/e0412bb734d09aef492051c1730b5821)
  - [AP, Apr 16 2026](https://apnews.com/article/297a8d2bb94add26e503a4ef3a5d1151)
  - [AP, Apr 13 2026](https://apnews.com/article/db8b021cfbfd06056016678bbde618c5)
- status:
  - `needs_narrowing`

### Iran March-phase strike geography
- raw reporting:
  - Tehran
  - Alborz province
  - Bandar Abbas
  - Shiraz airbase
- why not ready:
  - latest Apr 16-17 coverage is mostly blockade / ceasefire / talks
  - named places are broad geography from the March phase, not current Blackline-ready civilian AOIs
- useful reframing:
  - only a pure civilian water facility, and only if exact site identity and macro-visible change are clear
- sources:
  - [AP, Apr 12 2026](https://apnews.com/article/a8a0d22918fc3fb30bc3abf1cd5c5a13)
  - [AP, Apr 12 2026](https://apnews.com/article/ca007ac1ba9f247cb3a59f9b97b06314)
- status:
  - `needs_narrowing`

### Other conflict-zone place names
- raw reporting:
  - Gaza City
  - Jabalia
  - Beach refugee camp
  - Bureij camp
  - Beit Lahiya
  - al-Fashir
  - Um Baru
  - Kernoi
  - North Darfur
  - South Kordofan
  - Damascus area
  - Bafwakoa village near Niania
  - Goma
- why not ready:
  - these are locality names, not facilities
  - many point to residential violence or town-wide harm rather than one macro-visible civilian lifeline
- useful reframing:
  - named hospital
  - named grain silo
  - named water plant
  - named aid warehouse cluster
- sources:
  - [Al Jazeera on Bafwakoa, Apr 2 2026](https://www.aljazeera.com/news/2026/4/2/at-least-43-people-killed-in-adf-attack-in-northeast-dr-congo-army-says)
  - [Radio Okapi on Bafwakoa, Apr 2 2026](https://www.radiookapi.net/2026/04/02/actualite/securite/une-attaque-des-adf-fait-au-moins-32-morts-mambasa)
- status:
  - `needs_narrowing`

## Reject for Blackline

### Tuapse
- raw reporting:
  - Tuapse on the Black Sea coast
- why reject:
  - oil terminal / port energy story
  - strategic export infrastructure
  - high tactical and economic-warfare value, weak civilian-lifeline framing
- sources:
  - [Reuters pickup, Apr 16 2026](https://www.marketscreener.com/news/drone-debris-falls-at-port-in-russia-s-tuapse-official-says-ce7e50dddb8bff26)
- status:
  - `reject`

### Crimea oil infrastructure
- raw reporting:
  - Crimea oil terminal / oil infrastructure
- why reject:
  - direct military sustainment and energy-war target class
  - outside Blackline civilian scope
- sources:
  - [ISW summary of Apr 8 reporting](https://www.criticalthreats.org/analysis/russian-offensive-campaign-assessment-april-8-2026)
- status:
  - `reject`

### Lgov petrol station
- raw reporting:
  - Lgov in Kursk region
- why reject:
  - petrol station is too small and too tactical to be a useful Blackline AOI
  - no durable macro-scale civilian lifeline signal at Sentinel scale
- sources:
  - [Reuters pickup, Apr 11 2026](https://whtc.com/2026/04/11/three-injured-in-ukrainian-drone-attack-in-russias-kursk-region-governor-says/)
- status:
  - `reject`

### Shiraz airbase
- raw reporting:
  - Shiraz airbase
- why reject:
  - explicitly military
- status:
  - `reject`

## Net

From this raw list, the only entries worth further Blackline work are:
- `Izmail` as a tightly cropped civilian port/rail sub-AOI
- `Tyre Red Cross center` as a humanitarian facility example, only if scale permits

Everything else needs:
- a specific civilian facility
- exact coordinates
- exact event dates
- an honest Sentinel-visible macro change

Until then, they stay geography signals, not product AOIs.
