# Blackline Atlas

**Source-led conflict disruption triage with satellite evidence.**

Blackline Atlas turns live public conflict leads into an operator workflow:
find the place, focus the globe, retrieve current-versus-baseline satellite
imagery, run context-prompted SAM3 segmentation, and ask a guarded Liquid VLM
analyst to explain what the imagery can and cannot support.

Built for the Liquid AI x DPhi Space hackathon.

## Judge Path

1. Start the local services listed in [Runtime Services](#runtime-services).
2. Open `http://127.0.0.1:8000/ui`.
3. Click `Refresh live leads`, or ask `What happened recently in Iran?`.
4. Select a live marker and request current versus baseline evidence.
5. Review the source lead, imagery pair, SAM3 evidence, Liquid analyst note,
   decision, and metrics in the right tray.

The important claim: **the source/API lead is the truth input, not the VLM**.
The planner uses lead context to choose SAM3 prompts. SAM3 segments those
requested concepts on the selected imagery. The Liquid VLM receives the source
context, image pair, and SAM3 report, then writes a civilian-scope analysis.
Alert authority remains source-led and guardrail-scored.

## Screenshots

![Blackline Atlas app](ui/assets/blackline-atlas-app.png)

![Port Sudan Aid Hub comparison](ui/assets/blackline-portsudan-comparison.png)

## Current Status

| Area | Status |
|---|---|
| Backend | FastAPI, typed schemas, strict parser repair, health/debug endpoints |
| UI | Same-origin WebGL globe, live markers, chat, evidence tray |
| Live leads | GDELT Cloud first, public GDELT fallback, file-backed cache |
| Imagery | SimSat/Sentinel selected-point current and 3-year baseline lookup |
| SAM3 | Required local HTTP bridge for live selected-site masks |
| Liquid planner | Local OpenAI-compatible Liquid LLM planner endpoint |
| Liquid VLM | Local bridge supports `LiquidAI/LFM2.5-VL-450M` plus PEFT adapter |
| Latest adapter | `ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter` |
| Runtime authority | Source-led SAM3 + Liquid analyst, guarded by deterministic rules |

## Model Evidence

Primary model:

- Base: [`LiquidAI/LFM2.5-VL-450M`](https://huggingface.co/LiquidAI/LFM2.5-VL-450M)
- Adapter: [`ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter`](https://huggingface.co/ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter)
- Corpus: [`ChrisRPL/blackline-atlas-training-corpus-v1`](https://huggingface.co/datasets/ChrisRPL/blackline-atlas-training-corpus-v1)
- HF job: [`69f66f889d85bec4d76f0be0`](https://huggingface.co/jobs/ChrisRPL/69f66f889d85bec4d76f0be0)

Training completed on `30,858` train rows and `3,421` eval rows. Eval loss
improved from `3.0021` to `0.3273`. On the corpus-native 22-case SimSat gold
eval, the adapter produced `22 / 22` valid JSON, `19 / 22` valid analyst-schema
reports, and `9 / 22` action matches. That is useful for guarded analyst
narration, but not strong enough for autonomous alert decisions.

SAM3 status:

- Frozen fixture eval pack: `training/replay_pack/sam3_eval_pack.jsonl`
- Fixture inference/eval: `22 / 22` pass, `0` false positives
- Real-image eval dataset: [`ChrisRPL/blackline-atlas-sam3-real-eval-v2`](https://huggingface.co/datasets/ChrisRPL/blackline-atlas-sam3-real-eval-v2)
- Decision: use real SAM3 as selected-site evidence, not as final scorer

## Architecture

```text
operator chat / marker click
  -> Liquid-compatible planner
  -> search_live_leads | refresh_live_leads | site_compare | explain_alert
  -> GDELT-backed live lead registry
  -> globe camera intent + selected lead card
  -> SimSat/Sentinel current-baseline retrieval
  -> source-context-derived SAM3 prompts
  -> SAM3 segmentation report
  -> LiquidAI/LFM2.5-VL paired-image analyst summary
  -> schema repair for recoverable low-confidence analyst JSON
  -> deterministic civilian-disruption guardrails
  -> alert card + evidence tray + metrics
```

Civilian scope only: lifeline infrastructure, aid logistics, water, food,
medical nodes, ports, bridges, and mobility chokepoints. Out of scope:
tactical targeting, strike support, weapons, troop movement, route intelligence,
or military asset ranking.

## Quick Start

```bash
cp .env.example .env
python3 -m pip install -e ".[dev]"
make dev
```

Open:

- UI: `http://127.0.0.1:8000/ui`
- API docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`
- Model status: `http://127.0.0.1:8000/model/status`

## Runtime Services

The app is intentionally honest about external services. If a configured local
service is unreachable, `/health` reports `degraded` and the UI should not claim
live analysis.

### SimSat / Sentinel

```bash
git clone https://github.com/DPhi-Space/SimSat.git ~/Projects/oss/SimSat
cd ~/Projects/oss/SimSat
export MAPBOX_ACCESS_TOKEN=...
docker compose up -d
curl http://localhost:9005/
```

Required app env:

```bash
SIMSAT_REQUIRED=true
SIMSAT_CURRENT_ENDPOINT=http://localhost:9005/data/current/image/sentinel
SIMSAT_BASELINE_ENDPOINT=http://localhost:9005/data/image/sentinel
SIMSAT_CURRENT_HTTP_ENABLED=true
SIMSAT_BASELINE_HTTP_ENABLED=true
```

Selected-point AOI attempts use `3km -> 5km -> 1.5km`, then nearby `3km`, then
regional context. Mapbox satellite tiles are orientation context only; they are
not accepted as evidence-grade before/after imagery.

### SAM3 Bridge

```bash
uvicorn app.sam3_bridge:app --host 127.0.0.1 --port 8787
```

Required app env:

```bash
SAM3_ENDPOINT=http://127.0.0.1:8787/sam3
SAM3_HTTP_ENABLED=true
SAM3_REQUIRED=true
```

### Liquid Planner

Use a local OpenAI-compatible Liquid LLM endpoint, for example llama.cpp or an
equivalent local server:

```bash
AGENT_MODEL_VERSION=LiquidAI/LFM2.5-1.2B-Instruct-GGUF
AGENT_ENDPOINT=http://127.0.0.1:11434/v1/chat/completions
AGENT_HTTP_ENABLED=true
AGENT_PROVIDER=openai_chat_completions_http
```

### Liquid VLM Analyst

```bash
python3 training/scripts/serve_liquid_vl_openai.py \
  --port 8014 \
  --backend transformers \
  --model-id LiquidAI/LFM2.5-VL-450M \
  --adapter-ref ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter
```

Required app env:

```bash
ANALYST_MODEL_VERSION=LiquidAI/LFM2.5-VL-450M
ANALYST_ADAPTER_REF=ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter
ANALYST_ENDPOINT=http://127.0.0.1:8014/v1/chat/completions
ANALYST_HTTP_ENABLED=true
ANALYST_PROVIDER=openai_chat_completions_http
```

## Live Lead Refresh

The UI `Refresh live leads` button calls `POST /leads/refresh` and uses
GDELT Cloud when `GDELT_API_KEY` or `GDELT_CLOUD_API_KEY` is configured. Public
GDELT Project export files are the fallback.

Manual cache refresh:

```bash
python3 -m app.services.lead_registry_refresh \
  --source-mode gdelt_cloud \
  --output-path var/live_leads.json \
  --gdelt-cloud-days 30 \
  --gdelt-cloud-limit 500 \
  --gdelt-cloud-confidence-profile loose \
  --gdelt-cloud-countries all
```

Set `LEAD_REGISTRY_PATH=var/live_leads.json` to make `/leads` and the planner
consume the refreshed cache. `var/` is ignored.

## Verification

Recent local gate:

```bash
python3 -m ruff check app tests training/scripts/serve_liquid_vl_openai.py training/scripts/eval_structured_outputs.py
python3 -m pytest -q
```

Result: `409 passed`; ruff clean.

## Repo Layout

```text
app/                 FastAPI routes, schemas, services, agent/evidence logic
docs/                specs, judge brief, SAM3 notes, dataset research
training/replay_pack frozen eval rows, SAM3 eval pack, model/data notes
training/scripts     corpus builders, eval scripts, HF Jobs helpers
tests/               API, model, SAM3, UI, and training regressions
ui/                  operational shell assets and screenshots
```

Bulk local artifacts are ignored: `work/`, `var/`, `training/eval_runs/`,
`training/corpus/`, local dataset folders, model weights, and scratch notes.

## Deeper Docs

- [Judge brief](docs/JUDGE_BRIEF.md)
- [Technical specs](docs/SPECS.md)
- [SAM3 evidence lane](docs/SAM3_EVIDENCE.md)
- [Dataset research notes](docs/DATASET_RESEARCH.md)
- [Training blueprint](docs/TRAINING_BLUEPRINT.md)
- [HF Jobs plan](docs/HF_JOBS.md)
