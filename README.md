# Blackline Atlas

**Civilian lifeline disruption triage from satellite imagery.**

Blackline Atlas watches a small, curated set of public civilian chokepoints and turns current-versus-baseline satellite imagery into compact, structured alerts. The goal is not to monitor everything. The goal is to surface a few defensible, macro-scale disruptions that matter for humanitarian logistics, food security, water access, and public mobility.

Built for the Liquid AI x DPhi Space hackathon.

## Demo In 20 Seconds

1. Open the operational globe.
2. See current disruption leads as markers.
3. Click a marker or ask the agent about an area.
4. Review the current frame, baseline frame, alert card, confidence, and metrics.
5. The system emits one of three machine-readable actions: `discard`, `defer`, or `downlink_now`.

The demo path is deterministic and replay-safe. The fine-tuned adapter is evaluated as an optional model component, not a hard dependency for the live presentation.

## Screenshots

### Operational Shell

![Blackline Atlas app](ui/assets/blackline-atlas-app.png)

### Evidence Pair

![Port Sudan Aid Hub comparison](ui/assets/blackline-portsudan-comparison.png)

## What It Does

- Maintains a lead registry for current conflict and disruption locations.
- Uses a globe/map-first workflow instead of a dashboard-first workflow.
- Retrieves or replays current and historical satellite frames for selected sites.
- Compares paired imagery against a strict civilian-disruption schema.
- Produces structured alerts that are safe for downstream automation.
- Keeps cached replay and deterministic fallback paths for demo reliability.

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
| UI | Same-origin operational shell with globe/map-first interaction |
| Lead registry | File-backed seed registry for current disruption markers |
| Replay | Stable cached fallback path for demo reliability |
| Gold eval | 22 frozen non-demo Blackline cases |
| Internal train | 33 exact-site train rows |
| Auxiliary train | 2,417 public auxiliary rows |
| Current train pool | 2,450 LEAP-exportable rows |
| Latest adapter | `ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v7-adapter` |
| Adapter promotion | Rejected for demo-critical use until calibration improves |

The latest adapter is useful research evidence: it improved JSON/schema reliability on the frozen gold set, but it over-fired on controls and failed the acceptance gate. The demo should therefore use deterministic replay and cached/prompted behavior unless a later adapter beats the base model on the frozen gold set.

## Model And Dataset Work

Primary VLM target:

- Base model: [`LiquidAI/LFM2.5-VL-450M`](https://huggingface.co/LiquidAI/LFM2.5-VL-450M)
- Adapter: [`ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v7-adapter`](https://huggingface.co/ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v7-adapter)
- Main auxiliary dataset: [`ChrisRPL/satellite-disruption-triage-aux-v1-3`](https://huggingface.co/datasets/ChrisRPL/satellite-disruption-triage-aux-v1-3)

Latest local gold-eval result:

| Model | Action Match | Schema Valid | Downlink Recall | False Positives | Decision |
|---|---:|---:|---:|---:|---|
| Prompted base | 8 / 22 | 12 / 22 | 0 / 12 | 0 | Baseline only |
| `aux_v7` adapter | 5 / 22 | 20 / 22 | 5 / 12 | 4 | Reject for demo-critical use |

Why this matters:

- The adapter learned formatting and became much more schema-stable.
- It also became too eager to emit `defer` or `downlink_now`.
- We keep the model work honest by requiring improvement on frozen Blackline cases, not only training loss.

## Architecture

```text
lead registry
  -> globe markers
  -> selected site / chat intent
  -> current Sentinel frame
  -> historical Sentinel baseline
  -> frame filters
  -> VLM / replay-safe candidate generation
  -> strict JSON repair and validation
  -> alert card + evidence tray + metrics
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
- `POST /agent/query`
- `GET /alerts`
- `GET /metrics`

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
  --adapter-ref ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v7-adapter
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
  --config training/configs/lfm25_vl_sft_train_hf_aux_v7.yaml \
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
- `pytest -q`: 276 passed

## Key Docs

- [Product blueprint](docs/BLUEPRINT.md)
- [Technical specs](docs/SPECS.md)
- [Training blueprint](docs/TRAINING_BLUEPRINT.md)
- [HF Jobs plan](docs/HF_JOBS.md)
- [Model data strategy](training/replay_pack/model_data_strategy_2026-04-19.md)
- [Current bottleneck plan](training/replay_pack/bottleneck_plan_2026-04-25.md)

## What Still Needs Work

- More exact-site internal train rows, especially calibrated `defer` cases.
- More frozen internal gold eval rows before making strong model claims.
- Better action calibration for the adapter so it does not over-fire on controls.
- Stronger judge-facing demo polish around first-click evidence review.
- More current conflict/disruption leads in the registry, refreshed safely and explainably.
