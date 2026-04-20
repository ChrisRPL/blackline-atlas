# External Dataset + Benchmark Research — 2026-04-19

Purpose:

- find public datasets that can help Blackline Atlas
- separate augmentation, transfer, and benchmark uses
- define a fair pre-train / post-train / cross-model evaluation plan

## Current repo truth

- internal non-demo eval rows: `14`
- internal positives: `6`
- internal controls / stress: `8`
- planner eval rows: `30`

Implication:

- internal benchmark exists
- internal benchmark is still too small to stand alone as the only story
- external benchmarks should support, not replace, Blackline-specific eval

Current ready external slices:

- `xbd_public_seed_v0`
- `spacenet8_public_seed_v0`

Rule:

- use these for frozen baseline, cross-model comparison, and transfer research
- do not treat them as replacements for Blackline lifeline labels

## What we should benchmark

Three layers:

1. internal Blackline benchmark
   - primary decision metric
   - exact `AlertCandidate` JSON
   - exact `discard | defer | downlink_now`
2. external task-fit benchmark
   - disaster / change / lifeline transfer
   - proves we did not overfit only to our tiny pack
3. broad RS-VLM sanity benchmark
   - optional
   - useful for hackathon storytelling
   - not the main shipping metric

## Best external datasets

### Tier A — direct task-fit

#### xBD / xView2

- best direct external fit for pre/post disruption
- official SEI xView2 page says xBD contains before/after disaster imagery, building outlines, damage levels, and fire / water / smoke context
- good for:
  - disaster damage transfer
  - building-scale disruption eval
  - pre-train / fine-tune warm start for macro damage cues
- caution:
  - building-damage schema does not equal Blackline lifeline schema
  - use as transfer data, not as-is target labels

Sources:

- [SEI xView2 overview](https://www.sei.cmu.edu/projects/xview-2-challenge/)
- [SEI xBD fact sheet](https://www.sei.cmu.edu/library/creating-xbd-a-dataset-for-assessing-building-damage-from-satellite-imagery-a/)

#### SpaceNet 8

- best external fit for flood-driven civilian disruption
- official challenge page centers flooded roads and buildings, multiclass segmentation, and disaster response
- good for:
  - mobility disruption
  - flood / water-impact transfer
  - lifeline obstruction eval
- caution:
  - flood-specific
  - segmentation-heavy, so convert carefully into alert labels

Sources:

- [SpaceNet 8 challenge](https://spacenet.ai/sn8-challenge/)
- [SpaceNet 8 paper](https://openaccess.thecvf.com/content/CVPR2022W/EarthVision/papers/Hansch_SpaceNet_8_-_The_Detection_of_Flooded_Roads_and_Buildings_CVPRW_2022_paper.pdf)

#### SpaceNet 5

- best mobility / road-network transfer set
- official challenge focuses on road extraction and route travel time
- good for:
  - mobility category
  - routing / obstruction context
  - bridge / road / access-lane priors
- caution:
  - no direct damage labels
  - better for transfer and auxiliary eval than direct alert scoring

Source:

- [SpaceNet 5 challenge](https://spacenet.ai/sn5-challenge/)

### Tier B — change-detection transfer

#### LEVIR-CD

- official site: bitemporal building change dataset from 20 Texas regions
- strong canonical change-detection benchmark
- good for:
  - no-change vs change discipline
  - temporal robustness
  - localization transfer
- caution:
  - academic-only use
  - building growth / decline, not humanitarian disruption

Source:

- [LEVIR-CD official site](https://justchenhao.github.io/LEVIR/)

#### S2Looking

- off-nadir / rural building change benchmark
- good for:
  - harder geometry
  - robustness to viewing angle
  - rural facility-change transfer
- caution:
  - not disruption-specific
  - reuse terms should be checked before mixing into training

Sources:

- [S2Looking paper](https://www.mdpi.com/2072-4292/13/24/5094)
- [S2Looking project](https://github.com/S2Looking)

#### SpaceNet 7

- official challenge: 24 monthly frames across ~100 geographies, 4 m imagery
- good for:
  - temporal persistence
  - long-gap change robustness
  - coarse urban change
- caution:
  - too coarse for many of our exact disruption cases

Source:

- [SpaceNet 7 challenge](https://spacenet.ai/sn7-challenge/)

### Tier C — asset prior / all-weather transfer

#### fMoW

- official SpaceNet host page presents it as a foundational overhead functional-map dataset
- good for:
  - facility-type prior
  - land-use / asset semantics
- caution:
  - not a disruption dataset
  - use for pretraining / transfer only

Sources:

- [fMoW SpaceNet page](https://spacenet.ai/iarpa-functional-map-of-the-world-fmow/)
- [fMoW paper](https://arxiv.org/abs/1711.07846)

#### SpaceNet 6

- official challenge mixes SAR + EO for all-weather building extraction
- good for:
  - cloud / smoke robustness research
  - future optical + SAR fusion path
- caution:
  - not direct disruption labels

Source:

- [SpaceNet 6 challenge](https://spacenet.ai/sn6-challenge/)

## Broad RS-VLM benchmark sets

These are useful for hackathon storytelling and cross-model sanity, not for product sign-off.

### VRSBench

- remote-sensing VLM benchmark with captioning, grounding, and QA
- useful to show whether a model is generally competent on RS multimodal tasks

Source:

- [VRSBench paper](https://proceedings.neurips.cc/paper_files/paper/2024/file/05b7f821234f66b78f99e7803fffa78a-Paper-Datasets_and_Benchmarks_Track.pdf)

### GEOBench-VLM

- broad Hugging Face geospatial VLM benchmark dataset
- useful as a broad external comparison layer

Source:

- [GEOBench-VLM dataset](https://huggingface.co/datasets/aialliance/GEOBench-VLM)

## How to use these datasets

Do not dump all external data into one train mix.

Use by role:

### For augmentation / transfer

- `xBD`
- `SpaceNet 8`
- `SpaceNet 5`
- `LEVIR-CD`
- `S2Looking`

### For all-weather or asset prior

- `SpaceNet 6`
- `fMoW`

### For benchmark-only or benchmark-mostly

- `VRSBench`
- `GEOBench-VLM`

## Recommended benchmark cohort

### Core cohort

1. `LiquidAI/LFM2.5-VL-450M`
   - our main model
   - official hackathon path
2. `HuggingFaceTB/SmolVLM2-500M-Video-Instruct`
   - best small-size apples-to-apples comparator
3. `Qwen/Qwen2.5-VL-3B-Instruct`
   - strongest practical open mid-tier comparator
4. `OpenGVLab/InternVL2_5-4B`
   - stronger open deployable comparator

### Optional additions

5. `Qwen/Qwen2-VL-2B-Instruct`
   - lower-size Qwen reference
6. `google/paligemma-3b-mix-448`
   - transfer-style VLM baseline
7. `openbmb/MiniCPM-V-2_6`
   - upper-ceiling open model

Why this cohort:

- deployable
- open or openly accessible
- local or OpenAI-compatible serving paths exist
- covers small to upper-mid range without drifting into giant-model theater

Sources:

- [Liquid satellite fine-tuning example](https://docs.liquid.ai/examples/customize-models/satellite-vlm)
- [SmolVLM2 model card](https://huggingface.co/HuggingFaceTB/SmolVLM2-500M-Video-Instruct)
- [Qwen2.5-VL-3B model card](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct)
- [Qwen2.5-VL docs](https://huggingface.co/docs/transformers/en/model_doc/qwen2_5_vl)
- [InternVL2_5-4B model card](https://huggingface.co/OpenGVLab/InternVL2_5-4B)
- [PaliGemma model card](https://huggingface.co/google/paligemma-3b-mix-448/blob/main/README.md)
- [Gemma 3 overview](https://deepmind.google/models/gemma/gemma-3/)

## Recommended evaluation protocol

### Pass 1 — frozen baseline

Run the same held-out pack on:

- `LiquidAI/LFM2.5-VL-450M`
- `SmolVLM2-500M`
- `Qwen2.5-VL-3B`
- `InternVL2_5-4B`

Use:

- same prompt contract
- same image materialization
- same parser / repair layer
- same action schema

Primary score:

- action accuracy
- macro recall on true disruptions
- false-positive rate on no-change / controls
- schema-valid rate
- bbox-valid rate
- `defer` calibration

### Pass 2 — after adaptation

Only after our internal gold set is no longer tiny:

- fine-tune or adapt `LFM2.5-VL-450M`
- rerun on the exact same held-out internal and external slices
- compare deltas, not raw scores alone

### Benchmark slices

Internal:

- Blackline internal gold set

External:

- `xBD` slice
- `SpaceNet 8` slice
- `LEVIR-CD` or `S2Looking` slice
- optional `VRSBench` or `GEOBench-VLM` slice

## What we still need for the dataset

For the VLM:

- second exact water positive
- second inland aid positive
- more exact positive anchors
- first real train split after the internal gold set grows

For the planner model:

- no fine-tune dataset yet
- expand eval from `30` rows toward `60-120`
- keep it plan-only

If planner fine-tuning is ever needed later:

- row shape should be:
  - watchlist context
  - selected asset context
  - user query
  - expected `AtlasAgentPlan` JSON
- not image pairs
- not alert candidates
- not final prose

## Best next moves

1. build a small external benchmark bundle
   - `xBD`
   - `SpaceNet 8`
   - `LEVIR-CD` or `S2Looking`
2. normalize them into Blackline-compatible eval slices
3. run frozen `LFM2.5-VL-450M` against:
   - internal gold set
   - external slices
4. run the same against:
   - `SmolVLM2-500M`
   - `Qwen2.5-VL-3B`
   - `InternVL2_5-4B`
5. only then decide whether Liquid adapter work is winning enough to keep pushing
