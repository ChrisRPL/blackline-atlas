# Blackline Atlas

Blackline Atlas is an onboard civilian lifeline monitoring system.

It watches a small, curated set of public civilian chokepoints such as ports, grain terminals, bridges, logistics hubs, and aid-corridor bottlenecks, compares current satellite imagery against historical baselines, suppresses low-value frames locally, and emits compact structured alerts only when there is evidence of macro-scale visible disruption.

## Why this exists

Most satellites still downlink raw pixels.
Blackline Atlas downlinks operator-ready disruption alerts.

This repo is optimized for:
- a narrow, credible civilian monitoring scope
- one unforgettable end-to-end demo
- structured outputs over chatty text
- deterministic replay and cached fallback paths

## What this is not

Do not turn this into:
- tactical targeting
- strike support
- military asset ranking
- precise battle-damage claims
- tiny-object surveillance

## Current scaffold

This repo now contains:
- a FastAPI backend skeleton
- typed schemas for assets, frames, replay, metrics, and alerts
- stub routes for the core product loop
- placeholder training scripts
- smoke tests for API startup
- local support docs and wiki notes stay untracked by design

## Repo layout

```text
app/        backend services, routes, schemas, policy spine
tests/      API smoke tests
training/   dataset, eval, and training placeholders
ui/         dashboard placeholder
```

## Fast start

```bash
cp .env.example .env
python3 -m pip install -e ".[dev]"
make dev
```

Then open `http://127.0.0.1:8000/docs`.

## Core API routes

- `GET /health`
- `GET /assets`
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

This project can lean on Hugging Face skills for:
- dataset creation
- evaluation
- training on HF Jobs
- Hub artifact handling

In this Codex environment, Hugging Face skills are already available to invoke when needed.
If you want a local checkout of [`huggingface/skills`](https://github.com/huggingface/skills), keep it in `vendor/huggingface-skills/`; that path is gitignored on purpose.
