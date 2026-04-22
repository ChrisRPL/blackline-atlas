# Data Acquisition Speedup — 2026-04-22

Purpose:

- make the real data bottleneck explicit
- stop confusing `current conflict geography` with `promotable VLM rows`
- document the fastest honest collection path for hackathon time

## Blunt answer

We did **not** stall because the web had too few conflicts.

We stalled because the hard part is:

1. exact named civilian facility
2. exact parcel center
3. clean pre/post Sentinel pair
4. non-leaky gold/train split
5. defendable macro-visible scar

Broad current reporting is easy.
Honest Blackline rows are not.

## The right split

Keep two lanes separate:

### Lane A: current-source lead intake

Use web / humanitarian reporting to create:

- `lead_only` facilities
- source-linked exact hospitals / warehouses / water plants / bridges
- daily or manual refresh

Use for:

- globe points
- operator awareness
- future SimSat probing

Do **not** feed these directly into:

- `non_demo_eval.jsonl`
- `train_01.jsonl`

### Lane B: VLM row promotion

Promote only after:

- parcel lock
- bounded SimSat probe
- honest visual review
- split leakage check

Use for:

- frozen gold eval
- train tranche
- before/after model eval

## What the web is good for right now

Best current exact-facility use:

- `Nasser Medical Complex`
- `Al-Ahli Arab Hospital`
- `European Gaza Hospital`
- `Saudi Maternal Teaching Hospital`
- `Qasmiyeh Bridge`
- `Khartoum Bahri Water Station`

These are good because they are:

- fixed civilian facilities
- publicly named
- source-linked
- probeable with Sentinel / SimSat

They are **not** automatically good train rows.

## What external datasets are worth using

### Direct row-promotion candidates

#### `xBD / xView2`

- best current public fit for before/after civilian damage
- strongest direct source for disaster-scale disruption rows
- use for:
  - benchmark
  - auxiliary train rows
  - weak transfer checks
- friction:
  - registration / account gate
  - public but not zero-friction
- source:
  - [SEI xBD overview](https://www.sei.cmu.edu/library/creating-xbd-a-dataset-for-assessing-building-damage-from-satellite-imagery/)

#### `SpaceNet 8`

- best public fit for flooded roads and buildings
- strongest mobility / flood-disruption auxiliary source
- use for:
  - benchmark
  - direct auxiliary promotion
- source:
  - [SpaceNet 8 challenge](https://spacenet.ai/sn8-challenge/)
  - [CVPR paper](https://openaccess.thecvf.com/content/CVPR2022W/EarthVision/papers/Hansch_SpaceNet_8_-_The_Detection_of_Flooded_Roads_and_Buildings_CVPRW_2022_paper.pdf)

### Weak-supervision / context sources

#### `Sen1Floods11`

- strong flood supervision
- useful for water / inundation priors
- not a drop-in Blackline row set
- source:
  - [GitHub](https://github.com/cloudtostreet/Sen1Floods11)

#### `WorldCereal`

- strong crop / irrigation / cropland context
- useful for food / water context, not direct disruption labels
- source:
  - [WorldCereal paper](https://essd.copernicus.org/articles/15/5491/2023/)

### Benchmark-only

#### `LEVIR-CD`

- good generic building change benchmark
- weak Blackline fit for conflict / civilian lifeline disruption
- academic-only use
- source:
  - [LEVIR-CD](https://justchenhao.github.io/LEVIR/)

#### `S2Looking`

- harder off-nadir change benchmark
- good robustness check
- still benchmark-first, not direct Blackline row source
- source:
  - [S2Looking paper](https://www.mdpi.com/2072-4292/13/24/5094)

#### `SpaceNet 5`

- useful road-network prior
- not disruption-aware by itself
- source:
  - [SpaceNet 5 challenge](https://spacenet.ai/sn5-challenge/)

## Current recommendation

Do this, in order:

1. keep current-source lead intake alive through `lead_registry`
2. probe exact public facility leads, not whole cities
3. widen train by family depth first
4. use `xBD` and `SpaceNet 8` as auxiliary train / benchmark inputs
5. keep `LEVIR-CD` and `S2Looking` benchmark-only

## Immediate next work

1. `Bahri` stays exact control after the 2025 exact-site probe; stop treating it like a likely positive reopening
2. rank `Al-Ahli` ahead of `Nasser` for the next hospital-scale bounded review
3. keep widening under-depth positive families in `train_01`
4. materialize an auxiliary-train slice from checked-in `xBD` and `SpaceNet 8` seeds
5. use current-source ingest to feed the lead board, not the train file

## Do I need help from Krzysztof?

Not for generic web search.

Helpful if available:

- an approved `ReliefWeb` app name
- a short list of exact civilian facilities you already trust
- any private or semi-public source that already resolves parcel identity

But the main bottleneck is on my side:

- exact parcel gating
- bounded SimSat probing
- split hygiene
