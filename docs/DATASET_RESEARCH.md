# Dataset Research Notes

## Read When

- planning Liquid planner/brief SFT data
- deciding whether to merge new Hugging Face datasets
- explaining why the runtime uses source-led evidence instead of a pure VLM detector

## Scope

These notes exclude sources Blackline already evaluated heavily: BRIGHT,
xBD/xView2 variants, SpaceNet 8, LEVIR/S2Looking-style generic urban change,
Sen12MS/SEN12MS-CR, and existing `ChrisRPL/*` datasets. Those remain merge
inputs only where useful, not discovery targets.

The planner model target is not raw damage detection. It should learn:

- interpret conflict/humanitarian source reports
- decide whether an event is satellite-observable
- create short SAM3 visual concept prompts
- choose UI/tool actions
- write a source-led visible-impact brief
- avoid tactical, casualty, attribution, and military-targeting claims

## Hub-Ready Candidates

| Dataset | Use | Fit |
|---|---|---|
| [`google/RSRCC`](https://hf.co/datasets/google/RSRCC) | Remote-sensing regional change comprehension, VQA, image-text-to-text | Best new VLM/evidence reasoning candidate. Strong for before/after semantic change questions. |
| [`BiliSakura/RSCC`](https://hf.co/datasets/BiliSakura/RSCC) | Remote-sensing disaster change captioning | Strong VLM evidence-caption candidate. Public HF repo plus Google Drive subset fallback from the paper repository. |
| [`Kingdrone-Junjue/DisasterM3`](https://hf.co/datasets/Kingdrone-Junjue/DisasterM3) | Multi-hazard, multi-sensor disaster VLM instructions | Large VLM auxiliary candidate with Ukraine conflict files, but license is non-commercial/academic and dataset is large. |
| [`BIFOLD-BigEarthNetv2-0/BigEarthNet.txt`](https://hf.co/datasets/BIFOLD-BigEarthNetv2-0/BigEarthNet.txt) | Sentinel-1/Sentinel-2 image-text instructions and VQA | Best permissive large-scale source for generic EO language, LULC, region relations, and hard negatives. |
| [`DarthReca/crisislandmark`](https://hf.co/datasets/DarthReca/crisislandmark) | 647k Sentinel-1/Sentinel-2 images with text/geospatial annotations for crisis-management retrieval | Strong source-to-AOI retrieval and planner grounding candidate; non-commercial. |
| [`AdaptLLM/remote-sensing-visual-instructions`](https://hf.co/datasets/AdaptLLM/remote-sensing-visual-instructions) | Remote-sensing visual instruction data synthesized from RSICD/RSITMD/NWPU-Captions | Useful for generic remote-sensing VLM language, not conflict-specific. License must be reviewed. |
| [`hjvsl/GeoZero_Train_Datasets`](https://hf.co/datasets/hjvsl/GeoZero_Train_Datasets) | SFT/RL geospatial VQA and image-to-text data | Useful for geospatial reasoning/tool-language patterns; non-commercial. |
| [`RogerFerrod/GroundSet`](https://hf.co/datasets/RogerFerrod/GroundSet) | High-resolution aerial imagery with cadastral vector grounding | Useful for spatial grounding and civilian structure language; not conflict damage. |
| [`jaychempan/LAE-1M`](https://hf.co/datasets/jaychempan/LAE-1M) | Large open-vocabulary remote-sensing object detection | Useful for SAM prompt vocabulary/object grounding, not planner prose. |
| [`hotosm/vhr-building-segmentation`](https://hf.co/datasets/hotosm/vhr-building-segmentation) | HOT/OAM building footprint segmentation | Useful for building/structure visual primitives and hard negatives. |
| [`kshitijrajsharma/hot-building-segmentation`](https://hf.co/datasets/kshitijrajsharma/hot-building-segmentation) | Same HOT building footprint family | Same as above; prefer one canonical source to avoid duplicates. |
| [`QCRI/CrisisBench-english`](https://hf.co/datasets/QCRI/CrisisBench-english) | Humanitarian crisis social-media text classification | Strong planner input for source triage, informativeness, affected-population framing. |
| [`QCRI/CrisisMMD`](https://hf.co/datasets/QCRI/CrisisMMD) | Multimodal crisis tweets/images | Useful for source relevance and image-vs-text consistency, mostly natural disaster. |
| [`electricsheepafrica/Nigeria-conflict-events-1997-2025`](https://hf.co/datasets/electricsheepafrica/Nigeria-conflict-events-1997-2025) | Cleaned ACLED-style conflict events | Strong planner source-event rows. License needs caution. |
| [`electricsheepafrica/africa-conflict-related-incidents-affecting-water-systems`](https://hf.co/datasets/electricsheepafrica/africa-conflict-related-incidents-affecting-water-systems) | Conflict incidents affecting water systems | Very strong civilian-lifeline fit. |
| [`electricsheepafrica/africa-sdn-views-conflict-forecasts`](https://hf.co/datasets/electricsheepafrica/africa-sdn-views-conflict-forecasts) | VIEWS Sudan conflict forecasts | Useful for regional risk/background, not event evidence. |
| [`baobabtech/water-conflict-source-data`](https://hf.co/datasets/baobabtech/water-conflict-source-data) | Water-conflict headline classifier with hard negatives | Strong small text classifier/SFT input for water-lifeline source routing. |
| [`ShreelekhaR/MONITRS`](https://hf.co/datasets/ShreelekhaR/MONITRS) | FEMA events with Sentinel-2 imagery, captions, geotags, QA | Useful pattern source for event/image/caption QA, mostly non-conflict. |
| [`weihao1115/dvl_suite`](https://hf.co/datasets/weihao1115/dvl_suite) | Dynamic city/long-term urban change benchmark | Useful for non-conflict hard negatives and change-language calibration. |
| [`rahuldshetty/satellite-multitask-omni`](https://hf.co/datasets/rahuldshetty/satellite-multitask-omni) | ChatML satellite/aerial multi-task dataset, 34,894 rows | Useful schema/style donor for VLM instruction format if license/source quality passes. |
| [`Mercyiris/remote-sensing-change-detection`](https://hf.co/datasets/Mercyiris/remote-sensing-change-detection) | Small aligned optical/SAR change-detection package | Useful as tiny pair-format smoke data, not enough as a core source. |
| [`nlp-thedeep/humset`](https://hf.co/datasets/nlp-thedeep/humset) | Humanitarian analyst text entries and labels | Strong planner-brief source for humanitarian framing and source classification; not image data. |
| [`QCRI/MEDIC`](https://hf.co/datasets/QCRI/MEDIC) | Disaster image classification | Useful only for broad crisis-image recognition and hard negatives; not satellite and not conflict-specific. |
| [`DMIR01/DisastIR`](https://hf.co/datasets/DMIR01/DisastIR) | Disaster-management text retrieval benchmark | Useful for planner/source retrieval training and eval; not imagery. |

## Paper Leads

These papers are useful as method anchors. Some now have directly usable Hub
datasets; others only expose GitHub/project download flows.

| Paper | Link | Use |
|---|---|---|
| DisasterM3 | <https://hf.co/papers/2505.21089> | Confirms multi-task disaster VLM training works when dataset has bi-temporal, multi-sensor, reasoning labels. Hub dataset exists and is a large auxiliary candidate. |
| RSRCC | <https://hf.co/papers/2604.20623> | Best match for regional change QA; Hub dataset exists and should be prioritized. |
| DeltaVLM / ChangeChat-105k | <https://hf.co/papers/2507.22346> | Strong architecture pattern for instruction-guided difference perception; use GitHub downloader because no standalone HF dataset was found. |
| RSCC disaster change captions | <https://hf.co/papers/2509.01907> | Strong pre/post disaster change-caption source; Hub dataset exists and GitHub provides a manual Google Drive fallback. |
| SECOND-CC / MModalCC | <https://hf.co/papers/2501.10075> | Useful for change captioning methodology and metrics; not conflict-specific. |
| ChatEarthNet | <https://hf.co/papers/2402.11325> | Large image-text EO corpus for generic geospatial language. |
| Falcon RS VLM | <https://hf.co/papers/2503.11070> | Strong multi-task remote-sensing VLM recipe; useful for training design. |
| OSM-based domain adaptation for RS VLMs | <https://hf.co/papers/2603.11804> | Useful method for generating local captions from OSM without paid teacher models. |
| BigEarthNet.txt | <https://hf.co/papers/2603.29630> | Large image-text EO benchmark; useful for generic land-cover/hard-negative language. |
| HumSet | <https://hf.co/papers/2210.04573> | Humanitarian crisis information extraction/classification pattern; direct Hub dataset exists. |
| DisastIR | <https://hf.co/papers/2505.15856> | Disaster-management retrieval benchmark pattern for source lookup tasks. |

## Acquisition Links And Instructions

Use this section as the operational download plan. Keep large/raw files under
`work/external/` or another ignored path. Do not commit downloaded datasets.

| Source | Direct Links | Download / Access | Action |
|---|---|---|---|
| RSRCC | Paper: <https://hf.co/papers/2604.20623>; dataset: <https://hf.co/datasets/google/RSRCC>; upstream repo: <https://github.com/google-research/remote-sensing/> | Direct HF download. Roughly 126k image+text rows with 512px before/after images. | Start with metadata/sample, then full subset if storage allows: `hf download google/RSRCC --repo-type dataset --local-dir work/external/rsrcc`. |
| RSCC | Paper: <https://hf.co/papers/2509.01907>; project: <https://bili-sakura.github.io/RSCC/>; GitHub: <https://github.com/Bili-Sakura/RSCC>; dataset: <https://hf.co/datasets/BiliSakura/RSCC> | Direct HF repo exists. GitHub README also provides a Google Drive fallback for the research subset because some users hit access issues. xBD license restrictions apply. | Preferred: `hf download BiliSakura/RSCC --repo-type dataset --local-dir work/external/rscc`. If HF fails, user downloads the Google Drive subset linked from the GitHub README and drops it into `work/external/rscc_manual/`. |
| DisasterM3 | Paper: <https://hf.co/papers/2505.21089>; GitHub: <https://github.com/Junjue-Wang/DisasterM3>; canonical HF mirror: <https://hf.co/datasets/Kingdrone-Junjue/DisasterM3> | Direct HF repo exists and is large. GitHub also links Google Forms for instruct/benchmark access. Non-commercial/academic-only terms. | Preferred sample/instruct pull: `hf download Kingdrone-Junjue/DisasterM3 DisasterM3_Instruct.zip --repo-type dataset --local-dir work/external/disasterm3`. If HF transfer is slow, user can request/download through the linked Google Forms and place zip files in `work/external/disasterm3_manual/`. |
| DeltaVLM / ChangeChat-105k | Paper: <https://hf.co/papers/2507.22346>; GitHub: <https://github.com/hanlinwu/DeltaVLM>; model: <https://hf.co/hanlinwu/DeltaVLM> | No obvious standalone HF dataset found. GitHub exposes `python data/download_changechat.py --output_dir ./data/changechat` and reports 87,935 train plus 17,172 test instruction rows. | Clone into ignored OSS cache and run its downloader, or ask user to run if it needs external credentials: `git clone https://github.com/hanlinwu/DeltaVLM.git work/external/DeltaVLM` then `cd work/external/DeltaVLM && python data/download_changechat.py --output_dir ./data/changechat`. |
| ChangeChat | Paper/repo: <https://github.com/hanlinwu/ChangeChat> | Older interactive bitemporal RS change-analysis repo. Dataset weights are not clearly direct-downloadable from the README; useful mostly as method/schema reference. | Do not block on it. Inspect only if DeltaVLM downloader fails or if we need prompt/schema examples. |
| BigEarthNet.txt | Paper: <https://hf.co/papers/2603.29630>; project: <https://txt.bigearth.net/>; dataset: <https://hf.co/datasets/BIFOLD-BigEarthNetv2-0/BigEarthNet.txt>; parent: <https://bigearth.net/> | Direct HF table repo with 9.55M rows under CDLA-Permissive-1.0. It references Sentinel-1/Sentinel-2 image names/patches; image bytes may require BigEarthNet v2.0 acquisition. | Pull parquet/table first: `hf download BIFOLD-BigEarthNetv2-0/BigEarthNet.txt --repo-type dataset --local-dir work/external/bigearthnet_txt`. If image archives are needed, user follows BigEarthNet v2.0 site instructions and provides local archive paths. |
| Falcon / Falcon_SFT | Paper: <https://hf.co/papers/2503.11070>; GitHub: <https://github.com/TianHuiLab/Falcon> | Repo says Falcon_SFT is the training dataset and provides training/eval scripts, but current README points to repo setup rather than one clean dataset archive. Dataset is huge, around tens of millions of samples. | Treat as method reference unless a public archive is found. If user wants it, clone repo and inspect issues/releases/model links; likely manual download or author-specific hosting. |
| ChatEarthNet | Paper: <https://hf.co/papers/2402.11325>; GitHub: <https://github.com/zhu-xlab/ChatEarthNet>; Zenodo: <https://doi.org/10.5281/zenodo.11003436> | Direct Zenodo DOI. Global Sentinel-2 image-text pairs under CC-BY-4.0 per repo. | Download from Zenodo manually or by DOI tooling into `work/external/chatearthnet/`. Use for EO captioning and hard negatives, not conflict evidence. |
| HumSet | Paper: <https://hf.co/papers/2210.04573>; project: <https://blog.thedeep.io/humset/>; GitHub: <https://github.com/the-deep/humset>; dataset: <https://hf.co/datasets/nlp-thedeep/humset> | Direct HF dataset, Apache-2.0, about 149k-154k rows depending config. | Use for planner/source-brief SFT: `hf download nlp-thedeep/humset --repo-type dataset --local-dir work/external/humset`. |
| DisastIR | Paper: <https://hf.co/papers/2505.15856>; GitHub: <https://github.com/kaiyin97/disaster_ir>; dataset: <https://hf.co/datasets/DMIR01/DisastIR> | Direct HF dataset, CC-BY-4.0, text retrieval benchmark with corpus/query/qrels splits. | Use for planner retrieval/source-routing: `hf download DMIR01/DisastIR --repo-type dataset --local-dir work/external/disastir`. |
| MEDIC | Paper: <https://hf.co/papers/2108.12828>; GitHub: <https://github.com/firojalam/medic>; project: <https://crisisnlp.qcri.org/medic/>; dataset: <https://hf.co/datasets/QCRI/MEDIC> | Direct HF dataset exists; project also exposes `https://crisisnlp.qcri.org/data/medic/MEDIC.tar.gz`. CC-BY-NC-SA terms. | Prefer HF for metadata; use direct tarball only if needed: `hf download QCRI/MEDIC --repo-type dataset --local-dir work/external/medic`. Not core satellite evidence. |
| Crisis water/security datasets | HF examples: <https://hf.co/datasets/electricsheepafrica/africa-conflict-related-incidents-affecting-water-systems>, <https://hf.co/datasets/baobabtech/water-conflict-source-data> | Direct HF table datasets. Good civilian lifeline/planner rows. License varies by source. | Pull only metadata/text for planner SFT; keep per-row `license` and `source_dataset`. |
| Gated RS SFT sets | Example: <https://hf.co/datasets/Qingyun/remote-sensing-sft-data> | HF access request required. | User must request access in browser. After access is granted, run `hf download Qingyun/remote-sensing-sft-data --repo-type dataset --local-dir work/external/remote_sensing_sft_data`. |

## Manual Download Queue

These require user action if automated HF download fails or access is gated:

- RSCC Google Drive subset: open <https://github.com/Bili-Sakura/RSCC>, use the Google Drive link in the README, place downloaded files in `work/external/rscc_manual/`.
- DisasterM3 Google Forms: open <https://github.com/Junjue-Wang/DisasterM3>, request the instruct/benchmark set if HF transfer is impractical, place zips in `work/external/disasterm3_manual/`.
- ChatEarthNet Zenodo: open <https://doi.org/10.5281/zenodo.11003436>, download archives, place them in `work/external/chatearthnet/`.
- BigEarthNet v2.0 imagery: open <https://bigearth.net/> if table-only `BigEarthNet.txt` is insufficient, download required Sentinel archives, place them in `work/external/bigearthnet_v2/`.
- Qingyun remote-sensing SFT: request access on HF; after approval we can download through `hf`.

## Do Not Re-Discover Unless Needed

These were already evaluated enough for current planning:

- BRIGHT
- xBD/xView2 variants
- SpaceNet 8
- LEVIR-CD/LEVIR-CC/S2Looking-style generic urban change
- SEN12MS/SEN12MS-CR
- Existing `ChrisRPL/*` datasets

Use them only as merge inputs, baselines, or compatibility checks. New research
time should go to the acquisition queue above and to license-safe merge scripts.

## Merge Strategy

Build two merged products, not one overloaded file.

`blackline-atlas-planner-brief-sft-v1`:

- text/SFT only
- target size: 50k-150k rows
- sources: live GDELT lead logs, CrisisBench, Nigeria conflict events, water-system incidents, water-conflict headlines, HDX/VIEWS regional risk rows, Blackline accepted/rejected operator flows
- targets: tool plan, satellite relevance, SAM3 prompt plan, UI action, concise visible-impact brief, safety refusal/constraint fields

`blackline-atlas-vlm-evidence-sft-v1`:

- image+text/VLM rows
- target size: 20k-80k rows if licensing permits
- sources: RSRCC, CrisisLandmark, GeoZero, AdaptLLM RS instructions, HOT buildings, LAE-1M, current Blackline gold/eval images
- targets: image description, before/after change summary, visible evidence tags, quality warning, not direct alert action unless labels are strong

Do not merge all licenses blindly. Keep license/source fields per row and build
training configs that can filter out non-commercial or unknown-license rows.

## Immediate Next Merge Inputs

Priority order:

1. `google/RSRCC` for remote-sensing before/after change reasoning.
2. `BiliSakura/RSCC` for disaster change captions and pre/post evidence language.
3. `BIFOLD-BigEarthNetv2-0/BigEarthNet.txt` for permissive Sentinel text/VQA pretraining and hard negatives.
4. `QCRI/CrisisBench-english`, `nlp-thedeep/humset`, `DMIR01/DisastIR`, and `electricsheepafrica/*conflict*` for source-led planner decisions.
5. `Kingdrone-Junjue/DisasterM3` only after confirming storage, license fit, and whether Ukraine/man-made examples improve our conflict scope enough.
6. Existing Blackline datasets for schema alignment and held-out eval only.

Do not train the planner to hallucinate detections. Train it to choose tools,
frame the source report, ask SAM3 for concrete visual concepts, and state when
imagery cannot support a claim.

## Hugging Face Storage Policy

Hugging Face storage is treated as constrained. Do not keep multiple large,
obsolete dataset versions online after a newer repo has been verified and all
training/eval jobs have moved to it.

Current canonical training corpus:

- `ChrisRPL/blackline-atlas-training-corpus-v1`
- status: private, uploaded, HF-ready, chunked
- purpose: merged planner SFT plus VLM evidence SFT shards
- local staging path: deleted after upload verification; rebuild with scripts under
  `training/scripts/`

Uploaded corpus chunks:

- root corpus v1: 60,000 planner SFT rows, 6,000 VLM evidence rows, 45,000
  source-audit rows
- `vlm_evidence_sft_bigearthnet_s2_chunk_01`: 2,000 derived Sentinel-2 RGB
  images and 19,993 VLM hard-negative / land-cover visual-literacy rows
- `vlm_evidence_sft_chatearthnet_chunk_02`: 8,000 Sentinel-2 RGB images and
  8,000 structured context-caption rows, excluding the `4v_train` rows already
  used in the root corpus
- `vlm_evidence_sft_simsat_gold_v1`: 55 manually curated SimSat/Sentinel
  before/after pairs, 110 images, with source-led action/bbox/rationale labels

Protected until final submission is locked:

- `ChrisRPL/blackline-atlas-training-corpus-v1`
- `ChrisRPL/blackline-atlas-training-bundles`
- latest SAM3 real eval dataset
- latest public judge-facing benchmark/eval dataset

Deletion candidates after dependency check:

- older `satellite-disruption-triage-*` repos superseded by later aux/corpus
  versions
- private SAM3 eval v1 if v2 fully replaces it
- incomplete or metadata-only repos that are not referenced by docs, model
  cards, training jobs, or demo scripts

Before deleting a HF repo:

1. Confirm no model card, adapter README, job manifest, or project README links
   to it as the active source.
2. Confirm the successor repo has a rendered dataset card, row counts, and
   downloadable files.
3. Record the deletion candidate list in the thread and get explicit approval.

Local cleanup uses the same rule. After each chunk upload is verified, raw
staging under `work/external/` can be moved to Trash to recover disk space. Do
not delete user-provided originals in `~/Downloads` unless explicitly approved.

## BigEarthNet-S2 Chunk 01

Built with `training/scripts/build_bigearthnet_s2_chunk.py` from:

- `work/external/hf/bigearthnet_txt/BigEarthNet.txt.parquet`
- `/Users/krzysztof/Downloads/BigEarthNet-S2.tar.zst`

HF destination:

- `ChrisRPL/blackline-atlas-training-corpus-v1/vlm_evidence_sft_bigearthnet_s2_chunk_01`
- upload commit: `e614785ac93625ecff3723383b5d7df492e27421`

Counts:

- images: 2,000
- train rows: 17,994
- eval rows: 1,999
- total rows: 19,993

Purpose:

- improve Sentinel-2 visual literacy
- add non-conflict hard negatives
- teach the VLM/planner stack not to infer conflict from ordinary land cover
- support safe `discard` behavior when no source-led conflict evidence exists

License note: this chunk is private. Text rows originate from BigEarthNet.txt;
derived RGB PNGs come from the user-provided BigEarthNet-S2 archive. Verify
upstream imagery redistribution terms before public release.

## ChatEarthNet Chunk 02

Built with `training/scripts/build_chatearthnet_chunk.py` from:

- `/Users/krzysztof/Downloads/11003436.zip`

HF destination:

- `ChrisRPL/blackline-atlas-training-corpus-v1/vlm_evidence_sft_chatearthnet_chunk_02`
- upload commit: `f4671b11198d4b28922f232e9a8035c21eae11a1`

Counts:

- images: 8,000
- train rows: 7,200
- eval rows: 800
- total rows: 8,000

Purpose:

- add more Sentinel-2 visual context rows without duplicating the initial
  `ChatEarthNet_caps_4v_train` shard
- improve scene description, visibility limitation language, and safe
  non-conflict calibration
- teach the model not to treat single-image context as direct before/after
  conflict evidence

License note: ChatEarthNet is documented by its project as CC-BY-4.0. This
chunk is kept in the private corpus and should be reviewed before any public
redistribution.

## SimSat Gold v1

Built with `training/scripts/build_simsat_gold_chunk.py` from:

- `training/replay_pack/train_01.jsonl`
- `training/replay_pack/non_demo_eval.jsonl`
- `training/corpus/lfm25-vl-train-01/capture/simsat_capture_manifest.json`
- `training/eval_runs/sam3_real_capture/simsat_capture_manifest.json`

HF destination:

- `ChrisRPL/blackline-atlas-training-corpus-v1/vlm_evidence_sft_simsat_gold_v1`
- upload commit: `f01aef7dfc92b3192943ad705f1ff19919dfba95`

Counts:

- train rows: 33
- eval rows: 22
- total rows: 55
- image files: 110
- action distribution: 36 `downlink_now`, 19 `discard`

Purpose:

- high-signal Blackline-specific gold calibration
- source-led visible-impact reasoning
- strict JSON evidence fields with `triage_action` last
- manual coarse bboxes for macro-visible civilian disruption
- hard negatives for no-material-change and weather/ambiguity cases

Use this shard for calibration, overfit/schema smoke, and held-out acceptance
gates. Do not treat it as bulk pretraining data. It is much smaller than the
public auxiliary chunks, but more important for product behavior because it
matches the actual SimSat/Sentinel runtime flow.
