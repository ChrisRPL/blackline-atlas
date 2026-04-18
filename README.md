# Blackline Atlas

Blackline Atlas is a map-first civilian lifeline disruption triage system.

Built during the Liquid AI x DPhi Space hackathon.

It watches a small, curated set of public civilian lifelines such as food hubs, water infrastructure, aid access nodes, and a narrow set of clearly civilian mobility chokepoints, compares current satellite imagery against historical baselines, suppresses low-value frames locally, and emits compact structured alerts only when there is evidence of macro-scale visible disruption.

## At a glance

- Sentinel-first current-vs-baseline disruption checks
- structured machine-readable alerts, not chatty summaries
- map-first operator UI with an agent command dock
- deterministic replay and cached fallback paths
- strict civilian, non-tactical scope

## Screens

Map-first shell:

![Blackline Atlas app](ui/assets/blackline-atlas-app.png)

Real analyzed case, Port Sudan Aid Hub before/after:

![Port Sudan Aid Hub comparison](ui/assets/blackline-portsudan-comparison.png)

## Why this exists

Most satellites still downlink raw pixels.
Blackline Atlas downlinks operator-ready disruption alerts.

This repo is optimized for:
- a narrow, credible civilian monitoring scope
- one clear end-to-end demonstration path
- structured outputs over chatty text
- deterministic replay and cached fallback paths

## What this is not

Do not turn this into:
- tactical targeting
- strike support
- military asset ranking
- precise battle-damage claims
- tiny-object surveillance

## Current status

This repo is in a strong prototype state, not a finished product:

- end-to-end product loop works
- map-first shell and deterministic agent contract are live
- replay-safe and cached fallback paths are in place
- real eval/data lane exists, but the gold set is still small
- model fine-tuning is not the critical path yet

## What works today

This repo contains:
- a FastAPI backend skeleton
- typed schemas for assets, frames, replay, metrics, and alerts
- optional Mapbox inspection context on accepted alerts when a token is present
- a same-origin UI shell at `/ui`
- routes for the core product loop
- a tiny replay-pack exporter and offline eval harness
- a SimSat Sentinel capture-manifest exporter for freezing real current/baseline pairs
- a Liquid-compatible corpus freezer that joins SimSat captures with replay labels
- tests for API and service behavior

## Repo layout

```text
app/        backend services, routes, schemas, policy spine
tests/      API and service regressions
training/   replay pack, eval harness, training helpers
ui/         same-origin dashboard shell
```

## Where community help matters most

Useful OSS contributions now:

- better civilian-lifeline eval cases with exact public evidence
- more negative/control cases, not just hero positives
- UI polish for map readability, mobile behavior, and operator flow
- tighter replay/demo reliability
- dataset tooling for freezing and reviewing real Sentinel pairs

## Fast start

```bash
cp .env.example .env
python3 -m pip install -e ".[dev]"
make dev
```

Then open `http://127.0.0.1:8000/docs`.
The read-only UI shell lives at `http://127.0.0.1:8000/ui`.

## Local SimSat lane

Verified local bring-up for the official hackathon data source:

- dashboard: `http://localhost:8000`
- historical Sentinel: `http://localhost:9005/data/image/sentinel`
- current Sentinel: `http://localhost:9005/data/current/image/sentinel`

```bash
git clone https://github.com/DPhi-Space/SimSat.git ~/Projects/oss/SimSat
cd ~/Projects/oss/SimSat
export MAPBOX_ACCESS_TOKEN=...
docker compose up -d
curl http://localhost:9005/
```

Note:
- the current SimSat stack requires a non-empty `MAPBOX_ACCESS_TOKEN` at boot, even for Sentinel-only smoke tests

Freeze one real capture pack, then build and score the held-out corpus:

```bash
python3 training/scripts/capture_simsat_manifest.py \
  --historical-endpoint http://localhost:9005/data/image/sentinel \
  --output-dir /tmp/blackline-simsat-capture

python3 training/scripts/build_lfm25_vl_corpus.py \
  --capture-manifest /tmp/blackline-simsat-capture/simsat_capture_manifest.json \
  --output-dir /tmp/blackline-lfm25-vl-v1

python3 training/scripts/eval_structured_outputs.py \
  --dataset /tmp/blackline-lfm25-vl-v1/blackline_candidate_eval.jsonl
```

First real non-demo annotations live in:

- `training/replay_pack/non_demo_eval.jsonl`
- sourced next-case backlog: `training/replay_pack/civilian_aoi_backlog.md`
- broad 2026 conflict-location triage memo: `training/replay_pack/conflict_aoi_triage_2026-04-17.md`
- gold-set acquisition matrix: `training/replay_pack/gold_eval_acquisition_matrix.md`
- first acquisition batch plan: `training/replay_pack/gold_eval_tranche_01.md`
- first water acquisition memo: `training/replay_pack/water_tranche_01.md`

Prompted Liquid eval path:

```bash
python3 -m pip install -e ".[dev,vlm]"
cat training/replay_pack/hero_eval.jsonl training/replay_pack/non_demo_eval.jsonl > /tmp/phase3_eval.jsonl

python3 training/scripts/capture_simsat_manifest.py \
  --historical-endpoint http://localhost:9005/data/image/sentinel \
  --cases-dataset /tmp/phase3_eval.jsonl \
  --output-dir /tmp/phase3_simsat_capture

python3 training/scripts/build_lfm25_vl_corpus.py \
  --capture-manifest /tmp/phase3_simsat_capture/simsat_capture_manifest.json \
  --replay-dataset /tmp/phase3_eval.jsonl \
  --output-dir /tmp/phase3_corpus

python3 training/scripts/run_lfm25_vl_prompted_eval.py \
  --dataset /tmp/phase3_corpus/blackline_candidate_eval.jsonl \
  --output-dir /tmp/phase3_run_full
```

Candidate selection rule:

- prefer lifelines a civilian near a country or city would actually care about:
  food first, then water, then aid, then mobility
- prefer assets serving nearby population centers over globally famous infrastructure
- keep ports as one lane, not the whole product
- keep major bridges and ports on a shorter leash than food, water, and aid
- reject cases where Sentinel cannot show an honest macro change
- avoid mixed-use military ports, fuel depots, and frontline route intel

## Core API routes

- `GET /health`
- `GET /assets`
- `GET /agent/tools`
- `POST /agent/query`
- `POST /replay/start`
- `POST /replay/stop`
- `GET /replay/status`
- `GET /frames/current`
- `GET /frames/baseline`
- `GET /alerts`
- `GET /metrics`

## v0 priorities

1. Stable end-to-end flow
2. Deterministic replay
3. Cached current/baseline frame retrieval
4. Structured alert schema
5. One-page UI
6. Eval harness before training

## Hugging Face workflows

This project can optionally use Hugging Face tooling for:
- dataset creation
- evaluation
- training on HF Jobs
- Hub artifact handling

## Agent control plane

The `/agent/query` contract is now deterministic-first:

- text planner chooses a tool and filters
- deterministic backend tools execute:
  - `latest_alerts`
  - `biggest_disruptions`
  - `site_compare`
  - `explain_alert`
- trust, ranking, replay/live truth, and alert evidence remain backend-owned

Optional text-planner envs:

```bash
AGENT_MODEL_VERSION=lfm2.5-1.2b-instruct
AGENT_ENDPOINT=
AGENT_HTTP_ENABLED=
AGENT_API_KEY=
AGENT_PROVIDER=atlas_json_http
```

For Liquid-served `LFM2.5-1.2B-Instruct`, the smallest honest live path is an
OpenAI-compatible chat-completions endpoint:

```bash
AGENT_MODEL_VERSION=LiquidAI/LFM2.5-1.2B-Instruct
AGENT_ENDPOINT=https://your-liquid-host/v1/chat/completions
AGENT_HTTP_ENABLED=true
AGENT_PROVIDER=openai_chat_completions_http
```

For a local endpoint, Liquid’s Ollama docs work with the same provider contract:

```bash
ollama serve
ollama pull hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF

AGENT_MODEL_VERSION=hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF
AGENT_ENDPOINT=http://127.0.0.1:11434/v1/chat/completions
AGENT_HTTP_ENABLED=true
AGENT_PROVIDER=openai_chat_completions_http
```

This app now sends `response_format={"type":"json_object"}` on the planner
chat-completions path to improve strict JSON routing.

To score the first frozen command flows against a running app:

```bash
python3 -m training.scripts.run_agent_command_eval --base-url http://127.0.0.1:8000
```

`/health` now exposes both `model_backend` and `agent_backend`, plus machine-readable
planner config flags, so the UI can tell fixture planner vs live planner without
parsing prose.
