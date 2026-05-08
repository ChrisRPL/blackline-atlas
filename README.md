# Blackline Atlas

**Source-led satellite triage for civilian disruption.**

Blackline Atlas turns live public conflict/disruption reports into a narrow
operator workflow: GDELT lead, selected coordinate, Sentinel current/baseline
evidence, Liquid VLM visual site brief, and deterministic civilian guardrails.

Built for the Liquid AI x DPhi Space hackathon.

## What It Is

Blackline Atlas is not a general chatbot or targeting system. It is a structured
alert component for macro-scale civilian disruption triage. The product is
optimized for one reliable live preview path: a public source lead becomes a bounded
satellite review, then the UI shows what the imagery can and cannot support.

## Run The App

Use Python `3.11+`.

### App-Only Preview

This starts the UI and API with local fallback data. It is the fastest way to
inspect the product shape.

```bash
git clone https://github.com/ChrisRPL/blackline-atlas.git
cd blackline-atlas
cp .env.example .env
python3 -m pip install -e ".[dev]"
make dev
```

Open `http://127.0.0.1:8000/ui`.

### Full Live Preview

This is the intended judge path: live SimSat/Sentinel, live Liquid planner,
and live Liquid VLM analyst.

1. Start SimSat:

```bash
git clone https://github.com/DPhi-Space/SimSat.git ~/Projects/oss/SimSat
cd ~/Projects/oss/SimSat
export MAPBOX_ACCESS_TOKEN=...
docker compose up -d
```

2. Start the Liquid planner with Ollama:

```bash
# If Ollama is not already running, leave this command open in its own terminal:
ollama serve

# In another terminal:
ollama pull hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF:latest
```

3. Start the Liquid VLM analyst:

```bash
cd /path/to/blackline-atlas
python3 -m pip install -e ".[dev,vlm]"
python3 training/scripts/serve_liquid_vl_openai.py \
  --port 8014 \
  --backend transformers \
  --model-id LiquidAI/LFM2.5-VL-450M \
  --adapter-ref ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter
```

4. In another terminal, start Blackline Atlas:

```bash
cd /path/to/blackline-atlas
cp .env.example .env
make dev
```

5. Check readiness and open the UI:

```bash
make preflight
```

Open `http://127.0.0.1:8000/ui`, click `Start live preview`, then use
`Refresh live leads` for current GDELT discovery.

Expected `make preflight` result: SimSat current, SimSat baseline, planner, and
analyst all show `ready/live_http`. SAM should be `not_configured`; it is not in
the judge path.

## Judge Path

1. Start the local services in [Runtime Services](#runtime-services).
2. Run `make preflight`.
3. Open `http://127.0.0.1:8000/ui`.
4. Click `Start live preview` for the stable evidence path, then use
   `Refresh live leads` for current GDELT discovery.
5. Review the source lead, Sentinel pair, optional exact-coordinate contact
   sheet, Liquid visual brief, decision, and metrics.

The important claim: **the source lead gives event context; the VLM only writes
a guarded visual brief over imagery.** Casualty/source facts are not visual
facts. Mapbox is orientation context only. SAM/SAM3 is not in the judge runtime
path because low-resolution Sentinel masks are not defensible enough for the
live preview claim.

If SimSat, GDELT, or Liquid is unavailable, the app should say so and degrade
cleanly. It should not present source-only reports, Mapbox context, or invalid
model output as evidence.

## Submission Snapshot

| Field | Answer |
|---|---|
| One-line pitch | Source-led satellite triage that turns live conflict reports into Sentinel-grounded Liquid VLM site briefs. |
| Problem | Civilian disruption reports are noisy, fast-moving, and hard to verify visually; operators need a safe way to connect public source leads with satellite-visible evidence. |
| Solution | Fetch live GDELT leads, show them on a globe, auto-select a reviewable source point, resolve SimSat/Sentinel current and baseline imagery, run a Liquid VLM visual brief with source context, and keep final triage under deterministic civilian guardrails. |
| Why space-based compute matters | The workflow depends on low-latency satellite retrieval and local/edge analysis near the imagery source, reducing movement of raw imagery and enabling faster disaster/conflict monitoring. |
| Fine-tuned model | [`ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter`](https://huggingface.co/ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter) |
| Dataset | [`ChrisRPL/blackline-atlas-training-corpus-v1`](https://huggingface.co/datasets/ChrisRPL/blackline-atlas-training-corpus-v1) |
| Training job | [`69f66f889d85bec4d76f0be0`](https://huggingface.co/jobs/ChrisRPL/69f66f889d85bec4d76f0be0) |
| DPhi endpoints | `/data/image/sentinel`, `/data/current/image/sentinel` |
| Hardest part | Being honest under low-resolution/cloudy Sentinel imagery: rejecting no-data tiles, avoiding source-only claims, removing unreliable SAM masks from the judge path, and withholding invalid VLM output. |

## Screenshots

![Blackline Atlas live preview](ui/assets/blackline-atlas-live-preview.png)

![Blackline Atlas app](ui/assets/blackline-atlas-app.png)

![Port Sudan Aid Hub comparison](ui/assets/blackline-portsudan-comparison.png)

## Current Status

| Area | Status |
|---|---|
| Backend | FastAPI, typed schemas, strict parser repair, health/debug endpoints |
| UI | Same-origin WebGL globe, live markers, chat, evidence tray |
| Live leads | GDELT Cloud first, public GDELT fallback, file-backed cache |
| Imagery | SimSat/Sentinel selected-point current and 3-year baseline lookup |
| Contact sheet | Exact-coordinate `3 km`, `5 km`, `8 km` orientation sheet when images resolve |
| Liquid planner | Local OpenAI-compatible Liquid LLM planner endpoint |
| Liquid VLM | Local bridge supports `LiquidAI/LFM2.5-VL-450M` plus PEFT adapter |
| Runtime authority | Source-led evidence, Liquid visual brief, deterministic guardrails |

## Design Principles

- Keep the workflow narrow: public lead, Sentinel pair, Liquid brief, guardrail.
- Treat source reports as context, not visual proof.
- Reject or caveat blank, cloudy, stale, and context-only imagery.
- Withhold malformed, tactical, or unsupported model output.
- Prefer machine-readable outputs at API boundaries.
- Keep civilian resilience and humanitarian transparency as the product frame.

## Model Evidence

Primary model:

- Base: [`LiquidAI/LFM2.5-VL-450M`](https://huggingface.co/LiquidAI/LFM2.5-VL-450M)
- Adapter: [`ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter`](https://huggingface.co/ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter)
- Corpus: [`ChrisRPL/blackline-atlas-training-corpus-v1`](https://huggingface.co/datasets/ChrisRPL/blackline-atlas-training-corpus-v1)
- HF job: [`69f66f889d85bec4d76f0be0`](https://huggingface.co/jobs/ChrisRPL/69f66f889d85bec4d76f0be0)

Training completed on `30,858` train rows and `3,421` eval rows. Eval loss
improved from `3.0021` to `0.3273`. On the corpus-native 22-case SimSat gold
eval, the adapter produced `22 / 22` valid JSON, `19 / 22` valid analyst-schema
reports, and `9 / 22` action matches. That supports guarded analyst narration,
not autonomous alert authority.

SAM/SAM3 status: kept as an optional future/high-resolution eval lane. The
judge path suppresses segmentation on low-resolution Sentinel pairs because
masks are too unstable to promote as evidence.

## Architecture

```text
operator chat / marker click
  -> Liquid-compatible planner
  -> search_live_leads | refresh_live_leads | site_compare | explain_alert
  -> GDELT-backed live lead registry
  -> globe camera intent + selected lead card
  -> SimSat/Sentinel current-baseline retrieval
  -> optional exact-coordinate contact sheet for orientation
  -> LiquidAI/LFM2.5-VL paired-image visual site brief
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

For a minimal local UI without live services, `make dev` starts the FastAPI app
with fixture/fallback behavior. For the hackathon path, configure the runtime
services below before judging or recording.

Strict live-preview readiness check:

```bash
make preflight
```

The preflight requires `/health` to report `mode=live_http` and `status=ready`
for SimSat current, SimSat baseline, the planner, and the Liquid VLM analyst.
SAM must remain disabled and outside the judge path.

Open:

- UI: `http://127.0.0.1:8000/ui`
- API docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`
- Model status: `http://127.0.0.1:8000/model/status`

## Runtime Services

The app is intentionally honest about external services. If a configured local
service is unreachable, `/health` reports `degraded` and the UI should not claim
live visual analysis.

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
PRODUCTION_DEMO_MODE=true
SIMSAT_REQUIRED=true
SIMSAT_CURRENT_ENDPOINT=http://localhost:9005/data/current/image/sentinel
SIMSAT_BASELINE_ENDPOINT=http://localhost:9005/data/image/sentinel
SIMSAT_CURRENT_HTTP_ENABLED=true
SIMSAT_BASELINE_HTTP_ENABLED=true
```

Selected-point AOI attempts use exact, nearby, then context windows. Mapbox
satellite tiles are orientation context only; they are not accepted as evidence
grade before/after imagery.

### Liquid Planner

Use a local OpenAI-compatible Liquid LLM endpoint:

```bash
AGENT_MODEL_VERSION=hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF:latest
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

## Failure Behavior

Expected fail-closed states:

- No live lead source: keep existing markers or fixture state; show degraded
  health.
- No dated Sentinel pair: keep the source lead selected and show why visual
  review did not run.
- Context-only imagery: label it as orientation, not evidence.
- Cloud-limited imagery: allow a cautious site brief, cap confidence, and avoid
  visual confirmation claims.
- Invalid Liquid output: show `visual brief withheld`.
- Source-only casualty claims: strip or withhold them from the visual brief.

## Live Lead Refresh

The UI `Refresh live leads` button calls `POST /leads/refresh` and uses GDELT
Cloud when `GDELT_API_KEY` or `GDELT_CLOUD_API_KEY` is configured. Public GDELT
Project export files are the fallback.

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

Targeted gate:

```bash
python3 -m pytest tests/test_stub_service.py tests/test_agent_api.py tests/test_liquid_analyst.py tests/test_ui_shell.py tests/test_agent_planner.py -q
```

Full local gate:

```bash
python3 -m ruff check app tests ui
python3 -m compileall -q app
node --check ui/shell.js
python3 -m pytest -q
git diff --check
```

Latest local gate before submission:

- `python3 -m ruff check app tests ui`
- `python3 -m compileall -q app`
- `node --check ui/shell.js`
- targeted pytest: `129 passed`
- full pytest: `414 passed`
- browser smoke on `/ui`

## Demo Script

90-120 seconds:

1. Open `/ui` and show health, live leads, inspectable sites, and metrics.
2. Click `Refresh live leads` or ask `What happened around Ukraine?`.
3. Let Atlas auto-select the newest reviewable lead.
4. Show the source card: this is the event context, not visual proof.
5. Show current and baseline Sentinel frames.
6. If present, show the exact-coordinate contact sheet as orientation only.
7. Read the Liquid VLM brief: visible scene, likely visual change, limits, and
   source-to-visual relationship.
8. Close with the boundary: civilian resilience and humanitarian transparency
   only; no tactical targeting, strike support, or real-time surveillance
   claims.

## Repo Layout

```text
app/                 FastAPI routes, schemas, services, agent/evidence logic
docs/                specs, judge brief, SAM notes, dataset research
training/replay_pack frozen eval rows, model/data notes
training/scripts     corpus builders, eval scripts, HF Jobs helpers
tests/               API, model, UI, and training regressions
ui/                  operational shell assets and screenshots
```

Bulk local artifacts are ignored: `work/`, `var/`, `training/eval_runs/`,
`training/corpus/`, local dataset folders, model weights, and scratch notes.

## Contributing

Good contributions improve live-preview stability, evidence honesty, or structured
runtime contracts.

Before opening a PR:

```bash
python3 -m ruff check app tests ui
python3 -m compileall -q app
node --check ui/shell.js
python3 -m pytest -q
git diff --check
```

Contribution rules:

- Keep modules small and typed.
- Add regression tests for behavior changes when practical.
- Do not add broad tactical/military functionality.
- Do not promote Mapbox/context imagery as evidence.
- Do not reintroduce SAM/SAM3 into the judge runtime path unless imagery
  resolution and eval metrics support the claim.
- Keep local artifacts, recordings, caches, and downloaded datasets out of git.

## Hugging Face Resources

- Final adapter:
  [`ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter`](https://huggingface.co/ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter)
- Final corpus:
  [`ChrisRPL/blackline-atlas-training-corpus-v1`](https://huggingface.co/datasets/ChrisRPL/blackline-atlas-training-corpus-v1)

Older adapters are retained only for reproducibility and marked deprecated.
Use the final adapter/corpus links above in submissions and READMEs.

## Deeper Docs

- [Judge brief](docs/JUDGE_BRIEF.md)
- [Technical specs](docs/SPECS.md)
- [Live preview recording scenario](docs/LIVE_PREVIEW_RECORDING_SCENARIO.md)
- [Live preview teleprompter](docs/HACKATHON_LIVE_PREVIEW_TELEPROMPTER.md)
- [Dataset research notes](docs/DATASET_RESEARCH.md)
- [Training blueprint](docs/TRAINING_BLUEPRINT.md)
- [HF Jobs plan](docs/HF_JOBS.md)
