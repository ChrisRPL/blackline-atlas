# SAM3 Evidence Lane

## Role

SAM3 is the selected-site visual evidence tool, not the world-discovery system.

Blackline uses it after the lead registry and planner have already selected one
civilian site or source lead. Source intelligence answers "what was reported";
SAM3 and the Liquid VLM answer "what visible civilian impact can the imagery
help explain." They do not validate whether a conflict exists.

Runtime states:

- `source_only`: a credible source lead exists, but the event is not
  satellite-observable enough for before/after inspection, such as casualties,
  arrests, actor movement, or a close-range clash without described physical
  damage.
- `satellite_review_ready`: the source lead includes visible-impact language or
  infrastructure context, so Atlas can load current/baseline imagery and run
  image-pair analysis.
- `visible_impact_brief`: Atlas fuses source context, imagery quality, SAM3
  masks, and Liquid VLM before/after reasoning into an operator-facing brief.

The job is narrow:

- convert source context into short visual concept prompts
- return masks, boxes, and scores
- convert those into Blackline evidence tags
- derive `discard`, `defer`, or `downlink_now` for visible civilian impact,
  not for source-truth validation

## Model Choice

Use two runtime paths:

- `facebook/sam3` through Hugging Face Transformers for the local HTTP bridge and quick local checks.
- `facebook/sam3` through Meta's official `facebookresearch/sam3` package for CUDA still-image evidence checks when that runtime is available.

Do not run `facebook/sam3.1` through the current still-image evidence runner.
The public SAM3.1 release is the newer object-multiplex/video-style checkpoint,
so it needs a separate multiplex predictor path before it becomes our default.

References:

- https://huggingface.co/docs/transformers/model_doc/sam3
- https://github.com/facebookresearch/sam3
- https://github.com/facebookresearch/sam3/blob/main/README_TRAIN.md

## Prompt Strategy

SAM3 text prompts are concept prompts, not reasoning prompts. Hugging Face's
SAM3 documentation describes Promptable Concept Segmentation as using text
and/or exemplars, including short noun phrases, to predict masks for matching
objects. Keep model input short and visual, then do source-context reasoning and
before/after interpretation in Blackline.

Use:

- object nouns: `warehouse`, `container yard`, `bridge span`, `water tank`
- direct damage concepts: `rubble pile`, `debris field`, `collapsed building`, `burn scar`, `crater`
- asset-specific prompt banks selected by the lead registry
- source-context prompt expansion, for example a report mentioning damaged
  shops and apartment buildings should add `commercial building`,
  `apartment block`, `rubble pile`, `debris field`, and `crater`

Avoid:

- policy labels: `downlink_now`, `disruption`, `humanitarian risk`
- causal claims: `bombed building`, `war damage`, `conflict disruption`
- broad facility phrases that over-fire on intact sites: `flooded or breached water works`
- full sentence prompts with context that should live in the planner/scorer

Scoring rule:

- SAM3 masks are supporting evidence only.
- A SAM3 mask cannot promote a source-only event into `downlink_now`.
- For real inference, run the same concrete prompts on baseline and current
  frames and score change from mask appearance, disappearance, area shift, and
  IoU rather than trusting a single current-frame mask.
- Whole-frame masks are suppressed by default because they usually represent
  water, cloud, SAR speckle, or scene-level texture rather than actionable
  civilian infrastructure evidence.

## Source-Led Visible Impact Flow

The runtime flow is:

```text
GDELT / source lead
  -> source relevance gate
  -> dynamic visual prompt plan
  -> SimSat/Sentinel current + baseline frames
  -> SAM3 promptable concept segmentation
  -> Liquid VLM before/after explanation
  -> final visible-impact brief
```

The prompt planner must separate source facts from image tasks:

```json
{
  "source_event": "Reported strike in a residential district.",
  "satellite_relevance": "high",
  "target_prompts": [
    "apartment block",
    "commercial building",
    "rubble pile",
    "debris field",
    "crater"
  ],
  "ignore_terms": [
    "casualties",
    "soldiers",
    "political claims"
  ],
  "reason": "Source mentions damaged shops, a pharmacy, and apartment buildings."
}
```

Liquid VLM output should enrich the source lead:

- describe visible changes in the loaded before/after pair
- state when imagery quality prevents a defensible read
- explicitly say casualties, responsibility, troop movement, and intent are not
  satellite-verifiable
- recommend an action only for visible civilian infrastructure impact

## Local Fixture Gate

The fixture gate proves our app-side schema, prompt taxonomy, bbox IoU scoring,
and false-positive accounting before any GPU work.

```bash
python3 training/scripts/build_sam3_eval_pack.py

python3 training/scripts/run_sam3_inference.py \
  --backend fixture \
  --model-id facebook/sam3 \
  --output training/eval_runs/sam3_eval/reports.jsonl

python3 training/scripts/eval_sam3_reports.py \
  --reports training/eval_runs/sam3_eval/reports.jsonl \
  --summary-json training/eval_runs/sam3_eval/summary.json
```

Current local fixture gate:

- eval pack: `training/replay_pack/sam3_eval_pack.jsonl`
- cases: `22`
- positives: `12`
- hard negatives / no-evidence cases: `10`
- pass rate: `22 / 22`
- false positives: `0`

Generated run outputs stay under `training/eval_runs/` and should remain ignored.

## Real-Image Package

The real-image package is built from a SimSat capture manifest:

```bash
python3 training/scripts/capture_simsat_manifest.py \
  --historical-endpoint http://localhost:9005/data/image/sentinel \
  --cases-dataset training/replay_pack/non_demo_eval.jsonl \
  --capture-overrides training/replay_pack/non_demo_capture_overrides.json \
  --output-dir training/eval_runs/sam3_real_capture \
  --timeout-seconds 60

python3 training/scripts/build_sam3_eval_pack.py \
  --capture-manifest training/eval_runs/sam3_real_capture/simsat_capture_manifest.json \
  --output-dir training/eval_runs/sam3_real_eval_pack_v2 \
  --require-images

python3 training/scripts/package_sam3_eval_hf_dataset.py \
  --input-dataset training/eval_runs/sam3_real_eval_pack_v2/sam3_eval_pack.jsonl \
  --input-manifest training/eval_runs/sam3_real_eval_pack_v2/sam3_eval_manifest.json \
  --output-dir training/eval_runs/sam3_hf_dataset_v2 \
  --dataset-version sam3-real-eval-v2
```

Current Hub package:

- dataset: `ChrisRPL/blackline-atlas-sam3-real-eval-v2`
- cases: `22`
- images: `44`
- layout: `images/<source_case_id>/{current,baseline}.png`
- prompt bank: short visual concepts (`warehouse`, `pier`, `rubble pile`,
  `water tank`) instead of policy/causal phrases

## Local HTTP Bridge

Live inspection must talk to the local bridge, not a remote Space. The bridge
shares the same filesystem as the app, so it can read the SimSat/Sentinel frame
paths emitted by selected-point evidence.

Install the local bridge runtime:

```bash
uv sync --extra sam3
```

Run the bridge:

```bash
SAM3_BRIDGE_BACKEND=transformers \
SAM3_MODEL_VERSION=facebook/sam3 \
uvicorn app.sam3_bridge:app --host 127.0.0.1 --port 8787
```

Attach the main app:

```bash
SAM3_HTTP_ENABLED=true \
SAM3_REQUIRED=true \
SAM3_ENDPOINT=http://127.0.0.1:8787/sam3 \
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use `SAM3_BRIDGE_BACKEND=official` only when Meta's official SAM3 package and
CUDA are available. The official path is stricter and remains the CUDA evidence
check path; the Transformers path is the practical local bridge default.

## Real Inference

Use the real backends only after `current_frame.frame.image_ref` points at local
image files, not `pending://...` placeholders.

Transformers SAM3 path:

```bash
uv run training/scripts/run_sam3_inference.py \
  --backend transformers \
  --model-id facebook/sam3 \
  --image-root /path/to/captured/images \
  --output training/eval_runs/sam3_eval/reports.jsonl
```

Official SAM3 path:

```bash
uv run training/scripts/run_sam3_inference.py \
  --backend official \
  --model-id facebook/sam3 \
  --image-root /path/to/captured/images \
  --output training/eval_runs/sam3_eval/reports.jsonl
```

Operational notes:

- run the demo bridge locally; use HF Jobs only for larger offline sweeps
- request access to the gated Meta SAM checkpoint before launch
- HF Jobs `uv` environments may not have `python -m pip`; use
  `uv pip install --python "$PYTHON"` for runtime installs inside job scripts
- install `setuptools<81`, `einops>=0.8.0`, `pycocotools>=2.0.8`,
  and `psutil>=5.9.0`
  with the official SAM3 package
- keep SAM3 weights in FP32 and wrap `set_image` / `set_text_prompt` in CUDA
  BF16 autocast; otherwise the official runner can hit BF16/FP32 dtype mismatch
- persist remote smoke outputs with a Hub PR (`create_pr=True`) or at least print
  the JSON summary; direct commit from HF Jobs can be blocked on private repos
- use Python `3.12` for the official SAM3 repo path
- treat SAM3.1 as a follow-up multiplex/video integration, not the current still-image eval path
- keep threshold tuning outside the model weights until zero-shot behavior is measured

## Fine-Tuning Gate

Do not fine-tune SAM3/SAM3.1 just because the VLM adapter underperformed.

Fine-tune only if all are true:

- real zero-shot SAM3/SAM3.1 has been scored on frozen Blackline cases
- false positives or missed masks are the actual bottleneck
- we have image-level mask supervision, not only bbox or action labels
- train/eval locations are disjoint
- a small overfit run proves the training config can learn the mask task

Minimum useful SAM3 fine-tune dataset shape:

- `image`
- binary `mask`
- text `prompt` or bbox/point prompt
- source event/location metadata
- hard-negative prompts with empty masks

For the hackathon demo, the best path is:

1. keep SAM3 zero-shot or fixture-backed in runtime
2. tune deterministic thresholds and prompt sets
3. show the VLM adapter as research evidence, not accepted runtime
4. fine-tune SAM3 later only if mask labels exist
