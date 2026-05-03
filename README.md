# Blackline Atlas

**Civilian lifeline disruption triage from satellite imagery.**

Blackline Atlas watches a small, curated set of public civilian chokepoints and turns current-versus-baseline satellite imagery into compact, structured alerts. The goal is not to monitor everything. The goal is to surface a few defensible, macro-scale disruptions that matter for humanitarian logistics, food security, water access, and public mobility.

Built for the Liquid AI x DPhi Space hackathon.

## Judge Demo In 20 Seconds

1. Open `http://127.0.0.1:8000/ui`.
2. Run the local SAM3 bridge before inspection: `uvicorn app.sam3_bridge:app --host 127.0.0.1 --port 8787`.
3. Check the topbar: live SimSat means live imagery; local SAM3 means selected-site masks can run.
4. Click `Refresh live leads`, or ask Atlas `refresh live leads`.
5. Ask `What happened recently in Iran?` or click a live marker.
6. Ask `Compare current and baseline evidence` for the selected point.
7. Show the right tray: source report, current image, baseline image, decision, and metrics.

The primary runtime path is live and tool-based when services are configured: GDELT Cloud-backed lead ingestion with GDELT Project fallback, selected-point SimSat/Sentinel current-baseline compare, SAM3-compatible evidence support, optional Liquid paired-image analyst summary, rule-based evidence scoring, and structured alerts. Replay/reference fixtures remain fallback and regression coverage only; natural operator chat defaults to live source leads, not fixture alerts.

## Judge Review Path

Start with `/ui`, click a live lead or ask Atlas about a region, then watch the globe focus and the evidence tray populate. The key claim is the agentic workflow: chat answer, camera intent, source summary, selected-point evidence request, decision, and metrics in one operator surface. Model training is documented, but the product does not depend on an unaccepted adapter.

## Screenshots

### Operational Shell

![Blackline Atlas app](ui/assets/blackline-atlas-app.png)

### Evidence Pair

![Port Sudan Aid Hub comparison](ui/assets/blackline-portsudan-comparison.png)

## What It Does

- Maintains a live-refreshable lead registry for current conflict and disruption locations.
- Uses a globe/map-first workflow instead of a dashboard-first workflow.
- Retrieves current and historical satellite frames for selected points when SimSat/Sentinel is available.
- Lets chat commands drive globe focus, point selection, evidence requests, and summaries.
- Compares paired imagery against a strict civilian-disruption schema.
- Requires the local SAM3-compatible HTTP bridge for live selected-point
  segmentation masks. Offline fixture segmentation is test/eval-only.
- Produces structured alerts that are safe for downstream automation.
- Keeps cached replay/reference paths for verification; open-ended chat routing is planner-first.

## Evidence Modes

Blackline Atlas separates close satellite context from evidence-grade before/after analysis.

- `exact_aoi`, `nearby_aoi`, and `regional_aoi` are dated SimSat/Sentinel attempts. These can feed the VLM/SAM evidence lane when both current and baseline frames resolve.
- `satellite_context_only` is Mapbox satellite basemap context. It is useful for operator orientation and is requested at close inspection zoom, but it is not time-aware and is not scored by the VLM/SAM lane.
- Selected live markers use SimSat/Sentinel coordinate-time lookup for both the current event date and the historical baseline date. The simulator-current satellite endpoint is health-checked, but not trusted as selected-point evidence because it follows the simulator orbit rather than the clicked lead coordinate.
- Each selected-point bundle carries an `attempts` list showing the AOI sizes, windows, current/baseline status, and cloud-cover metadata tried before success or fallback.
- Evidence bundles also expose `quality_warnings` such as `baseline_cloud_81pct`, `nearby_offset_3.0km`, or `mapbox_context_not_time_aware`. These flags are displayed in the UI so weak imagery is visible to the operator.
- SimSat Sentinel coordinate lookup can take tens of seconds because it queries STAC and loads Sentinel tiles. The app therefore gives selected-point evidence a longer local timeout, but stops after a bounded close-AOI sweep before loading Mapbox context.
- The app intentionally withholds analyst output when only context imagery is available. This avoids pretending that a static basemap tile proves disruption.
- For live selected points, fixture SAM3 outputs are withheld. Live image
  analysis requires the local SAM3 HTTP endpoint; missing SAM3 is a degraded
  runtime state, not an acceptable demo mode.
- Future VLM training should use close-up paired AOI crops with hard negatives and labels for visual primitives: intact structures, destroyed structures, missing roofs, debris fields, road blockage, burn scars, craters, and low-visibility ambiguity.

## Civilian Scope

Blackline Atlas is intentionally narrow.

In scope:

- Food infrastructure, grain storage, markets, and distribution centers.
- Water infrastructure, dams, filtration, desalination, and pumping sites.
- Aid hubs, shelters, hospitals, and medical/relief logistics nodes.
- Clearly civilian ports, bridges, and mobility chokepoints.

Out of scope:

- Tactical targeting.
- Strike support.
- Military asset ranking.
- Troop, convoy, weapon, or base analysis.
- Tiny-object surveillance.
- Route-open or convoy-flow intelligence.

## Current Status

| Area | Status |
|---|---|
| Backend | FastAPI app, typed schemas, deterministic service layer |
| UI | Same-origin operational shell with a WebGL globe, live lead labels, chat, evidence tray, and cinematic ops styling |
| Lead registry | File-backed seed registry plus live GDELT Cloud / GDELT Project refresh cache for conflict/disruption markers |
| Live imagery | Selected live leads can request SimSat/Sentinel current and 3-year baseline frames |
| Replay | Stable cached fallback path plus single `/replay/snapshot` payload |
| SAM3 evidence lane | Local HTTP bridge added; fixture eval: 22 / 22 pass; real SAM3 v2 smoke rejected as decision scorer |
| Liquid analyst lane | Optional paired-image VLM summary endpoint; not alert authority unless promoted |
| Gold eval | v2.2 held-out evidence set: 51 eval rows, with 3-case schema smoke gate |
| Train bundle | v2.2 LEAP bundle: 93 train rows / 51 eval rows |
| Auxiliary dataset | `ChrisRPL/satellite-disruption-triage-aux-v2` |
| Latest adapter | `ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v10-adapter` |
| Adapter promotion | Rejected for production-critical use; live tool chain remains runtime |

The latest adapter is useful research evidence, not the product runtime. v10 completed and trainer eval loss improved strongly, but generation smoke still produced zero valid evidence-schema outputs and zero `downlink_now` matches. The runtime therefore uses live tool routing plus strict parser guardrails, with replay kept as fallback evidence.

## Model And Dataset Work

Primary VLM target:

- Base model: [`LiquidAI/LFM2.5-VL-450M`](https://huggingface.co/LiquidAI/LFM2.5-VL-450M)
- Latest adapter: [`ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v10-adapter`](https://huggingface.co/ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v10-adapter)
- Auxiliary dataset: [`ChrisRPL/satellite-disruption-triage-aux-v2`](https://huggingface.co/datasets/ChrisRPL/satellite-disruption-triage-aux-v2)
- Calibration/gold dataset: [`ChrisRPL/satellite-disruption-triage-aux-v2-2`](https://huggingface.co/datasets/ChrisRPL/satellite-disruption-triage-aux-v2-2)

Latest training result:

- HF Job: [`69f0ac8bd70108f37ace0f4d`](https://huggingface.co/jobs/ChrisRPL/69f0ac8bd70108f37ace0f4d)
- Steps: `105`
- Epochs: `10`
- Diagnostic eval loss: `2.9309 -> 1.2123`
- Published adapter: `ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v10-adapter`

Latest local schema smoke on 3 held-out positive eval-gold rows:

| Model | JSON Valid | Evidence Schema Valid | Action Match | Decision |
|---|---:|---:|---:|---|
| Prompted base | 3 / 3 | 0 / 3 | 0 / 3 | Baseline only |
| `aux_v9` adapter | 3 / 3 | 0 / 3 | 0 / 3 | Superseded / rejected |
| `aux_v10` adapter | 3 / 3 | 0 / 3 | 0 / 3 | Published / rejected |

Why this matters:

- The adapter trains and publishes correctly, so the HF/LEAP path is working.
- Lower trainer loss did not translate into valid runtime JSON or correct positive actions.
- The bottleneck is target-format/task wiring, not simply dataset size or more epochs.
- We keep the model work honest by requiring improvement on frozen Blackline cases, not only training loss.
- Runtime now repairs common model-output mess safely and defaults malformed or weak outputs away from alerts.

SAM3 evidence status:

- Local fixture eval pack: `training/replay_pack/sam3_eval_pack.jsonl`
- Fixture inference/eval: `22 / 22` pass, `0` false positives
- Real-image eval dataset: [`ChrisRPL/blackline-atlas-sam3-real-eval-v2`](https://huggingface.co/datasets/ChrisRPL/blackline-atlas-sam3-real-eval-v2)
- Official current-only smoke: [`69f12e9dd2c8bd8662bd25fd`](https://huggingface.co/jobs/ChrisRPL/69f12e9dd2c8bd8662bd25fd), `1 / 2` action match, `0` false positives
- Official temporal smoke: [`69f12f40d70108f37ace1300`](https://huggingface.co/jobs/ChrisRPL/69f12f40d70108f37ace1300), `1 / 2` action match, `0` false positives
- Decision: require real SAM3 as a selected-site overlay/evidence seam; do not
  promote it as the alert decision scorer yet.
- Real `facebook/sam3` inference path: `training/scripts/run_sam3_inference.py --backend transformers`
- Real `facebook/sam3` official inference path: `training/scripts/run_sam3_inference.py --backend official`
- HF Jobs official smoke runner source: `training/scripts/run_sam3_official_hf_smoke.py`
- `facebook/sam3.1` is a follow-up multiplex/video integration, not the current still-image gate
- HF SAM3 runtime must include `setuptools<81`, `einops`, `pycocotools`, and `psutil`; the official package imports them indirectly.
- Official SAM3 inference must wrap `set_image` / `set_text_prompt` in CUDA BF16 autocast while keeping weights FP32.
- Fine-tuning is intentionally gated until real mask labels exist; action-only rows or bboxes are not enough for SAM3 training.

## Architecture

```text
operator chat / marker click
  -> Liquid-compatible agent planner
  -> tool choice: search_live_leads | refresh_live_leads | site_compare | explain_alert
  -> live lead registry from GDELT Cloud / GDELT fallback
  -> WebGL globe camera intent + selected lead card
  -> linked civilian site when available
  -> current Sentinel/SimSat frame
  -> historical Sentinel/SimSat baseline
  -> frame filters and evidence-state checks
  -> SAM3 concept segmentation seam
  -> LiquidAI/LFM2.5-VL paired-image analyst summary
  -> deterministic civilian-disruption scorer
  -> strict JSON repair and validation
  -> alert card + evidence tray + metrics + machine-readable action
```

Key principles:

- Globe first, chat second, evidence third.
- Leads are not alerts until reviewed.
- Outputs are structured, not free-form prose.
- Frozen gold eval is separate from train data.
- Adapter promotion requires objective acceptance, not vibes.

## Repo Layout

```text
blackline-atlas/
├── app/                     FastAPI routes, services, schemas
├── docs/                    product and training docs
├── training/
│   ├── replay_pack/         frozen eval rows, train rows, strategy notes
│   ├── external_benchmarks/ public benchmark seed slices
│   ├── internal_benchmarks/ checked-in internal benchmark seeds
│   └── scripts/             capture, corpus, eval, HF Jobs helpers
├── tests/                   API, runtime, eval, and UI regressions
└── ui/                      same-origin operational shell and screenshots
```

## Quick Start

```bash
cp .env.example .env
python3 -m pip install -e ".[dev]"
make dev
```

Open:

- API docs: `http://127.0.0.1:8000/docs`
- UI shell: `http://127.0.0.1:8000/ui`

Useful API surfaces:

- `GET /model/status`
- `GET /assets`
- `GET /leads`
- `POST /leads/refresh`
- `POST /agent/query`
- `GET /replay/snapshot`
- `GET /evidence/current`
- `GET /evidence/assets/{asset_id}`
- `GET /analyst/assets/{asset_id}`
- `GET /alerts`
- `GET /metrics`

Lead registry refresh:

```bash
python3 -m app.services.lead_registry_refresh --dry-run
```

The command probes curated public-source URLs and prints a machine-readable
summary without changing the checked-in registry. Omit `--dry-run` only when
intentionally refreshing `app/services/lead_registry.seed.json`.

Live ACLED cache refresh:

```bash
export ACLED_USERNAME="you@example.com"
export ACLED_PASSWORD="..."
python3 -m app.services.lead_registry_refresh \
  --source-mode acled \
  --output-path var/live_leads.json \
  --acled-days 14 \
  --acled-limit 80
```

GDELT Cloud is the preferred live conflict provider when `GDELT_API_KEY` or
`GDELT_CLOUD_API_KEY` is configured. The app-level `POST /leads/refresh`
endpoint uses `source_mode=auto`: GDELT Cloud first, then public GDELT Project
fallback. ACLED remains disabled unless `ACLED_LEAD_ENABLED=true` and API data
access is confirmed.

Live GDELT Cloud cache refresh:

```bash
python3 -m app.services.lead_registry_refresh \
  --source-mode gdelt_cloud \
  --output-path var/live_leads.json \
  --gdelt-cloud-days 30 \
  --gdelt-cloud-limit 500 \
  --gdelt-cloud-confidence-profile loose \
  --gdelt-cloud-countries all
```

By default this uses one global conflict-event query. Add
`--gdelt-cloud-countries Ukraine,Lebanon,Mexico` only when a targeted shortlist
is needed.

Live GDELT Project fallback cache refresh:

```bash
python3 -m app.services.lead_registry_refresh \
  --source-mode gdelt \
  --output-path var/live_leads.json \
  --gdelt-hours 72 \
  --gdelt-max-files 288 \
  --gdelt-limit 500
```

Set `LEAD_REGISTRY_PATH=var/live_leads.json` to make `/leads` and the agent
planner use the refreshed live markers. `var/` is ignored so generated lead
caches and SimSat captures do not enter git.

The UI also exposes a `Refresh live leads` control backed by `POST /leads/refresh`.
It uses the same GDELT Cloud-first auto mode and preserves the existing
in-memory markers if the live fetch returns no usable events, so the operator
surface does not blank out during network/API failures.

## SimSat Data Lane

Primary local data source:

- Historical Sentinel: `http://localhost:9005/data/image/sentinel`
- Current Sentinel: `http://localhost:9005/data/current/image/sentinel`

Bring up SimSat:

```bash
git clone https://github.com/DPhi-Space/SimSat.git ~/Projects/oss/SimSat
cd ~/Projects/oss/SimSat
export MAPBOX_ACCESS_TOKEN=...
docker compose up -d
curl http://localhost:9005/
```

Configure Blackline Atlas to require live SimSat instead of quietly using cached
frames:

```bash
SIMSAT_REQUIRED=true
SIMSAT_CURRENT_ENDPOINT=http://localhost:9005/data/current/image/sentinel
SIMSAT_BASELINE_ENDPOINT=http://localhost:9005/data/image/sentinel
SIMSAT_CURRENT_HTTP_ENABLED=true
SIMSAT_BASELINE_HTTP_ENABLED=true
```

When `SIMSAT_REQUIRED=true`, `/health` and the UI mark SimSat as offline if
`localhost:9005` is not reachable. Cached/reference imagery can still keep the
interface usable, but it is no longer presented as live SimSat evidence.

## Local Liquid VLM Analyst

The paired-image analyst is opt-in. Without `ANALYST_HTTP_ENABLED=true`, live
selected SimSat pairs show the loaded current/baseline imagery and the evidence
quality flags, but they do not show a fake Liquid VLM judgement.

On Apple Silicon with MLX/Metal available, start the local bridge:

```bash
python3 training/scripts/serve_liquid_vl_openai.py \
  --port 8014 \
  --model-id LiquidAI/LFM2.5-VL-450M-MLX-4bit
```

Then configure the app:

```bash
ANALYST_MODEL_VERSION=LiquidAI/LFM2.5-VL-450M-MLX-4bit
ANALYST_ENDPOINT=http://127.0.0.1:8014/v1/chat/completions
ANALYST_HTTP_ENABLED=true
ANALYST_PROVIDER=openai_chat_completions_http
```

Freeze the 22-case non-demo gold pack:

```bash
python3 training/scripts/capture_simsat_manifest.py \
  --historical-endpoint http://localhost:9005/data/image/sentinel \
  --cases-dataset training/replay_pack/non_demo_eval.jsonl \
  --capture-overrides training/replay_pack/non_demo_capture_overrides.json \
  --output-dir /tmp/non_demo_simsat_capture
```

Build the VLM eval corpus:

```bash
python3 training/scripts/build_lfm25_vl_corpus.py \
  --capture-manifest /tmp/non_demo_simsat_capture/simsat_capture_manifest.json \
  --replay-dataset training/replay_pack/non_demo_eval.jsonl \
  --output-dir /tmp/non_demo_corpus
```

## Adapter Acceptance Gate

Run base model eval:

```bash
python3 training/scripts/run_lfm25_vl_prompted_eval.py \
  --dataset /tmp/non_demo_corpus/blackline_candidate_eval.jsonl \
  --output-dir /tmp/non_demo_eval_base_full
```

Run adapter eval:

```bash
python3 training/scripts/run_lfm25_vl_prompted_eval.py \
  --dataset /tmp/non_demo_corpus/blackline_candidate_eval.jsonl \
  --output-dir /tmp/non_demo_eval_adapter_full \
  --adapter-ref ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v10-adapter
```

Apply the promotion policy:

```bash
python3 training/scripts/check_adapter_acceptance.py \
  --base-summary /tmp/non_demo_eval_base_full/summary.json \
  --adapter-summary /tmp/non_demo_eval_adapter_full/summary.json
```

Promotion requires:

- Same frozen case count and expected-action mix.
- Schema validity not worse than base.
- Action-match count strictly better than base.
- `downlink_now` recall strictly better than base.
- False positives not worse than base.

## Training Path

Current conflict-focused training config:

```bash
python3 training/scripts/submit_train_backend_hf_job.py \
  --config training/configs/lfm25_vl_sft_train_hf_aux_v10.yaml \
  --submit
```

The remote training path uses Hugging Face Jobs and a LEAP-compatible SFT bundle. Local macOS is used for data prep, corpus export, smoke checks, and orchestration. Actual LEAP training runs remotely because the training backend requires CUDA.

## Verification

Full local gate:

```bash
ruff check app tests training
black --check app tests training
pytest -q
```

Recent local gate:

- `ruff check app tests training`: pass
- `black --check app tests training`: pass
- `pytest -q`: 352 passed

## Key Docs

- [Product blueprint](docs/BLUEPRINT.md)
- [Technical specs](docs/SPECS.md)
- [Judge brief](docs/JUDGE_BRIEF.md)
- [SAM3 evidence lane](docs/SAM3_EVIDENCE.md)
- [Dataset research notes](docs/DATASET_RESEARCH.md)
- [Training blueprint](docs/TRAINING_BLUEPRINT.md)
- [HF Jobs plan](docs/HF_JOBS.md)
- [Model data strategy](training/replay_pack/model_data_strategy_2026-04-19.md)
- [Current bottleneck plan](training/replay_pack/bottleneck_plan_2026-04-25.md)

## What Still Needs Work

- More exact-site internal train rows, especially calibrated `defer` cases.
- More frozen internal gold eval rows before making strong model claims.
- Better target-format wiring for the adapter before spending more GPU on larger runs.
- Stronger judge-facing runtime polish around first-click evidence review.
- More current conflict/disruption leads in the registry, refreshed safely and explainably.
