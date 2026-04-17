# Blackline Atlas

Blackline Atlas is an onboard civilian lifeline monitoring system.

It watches a small, curated set of public civilian chokepoints such as ports, grain terminals, bridges, logistics hubs, and aid-corridor bottlenecks, compares current satellite imagery against historical baselines, suppresses low-value frames locally, and emits compact structured alerts only when there is evidence of macro-scale visible disruption.

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

## Current scaffold

This repo now contains:
- a FastAPI backend skeleton
- typed schemas for assets, frames, replay, metrics, and alerts
- optional Mapbox inspection context on accepted alerts when a token is present
- a same-origin UI shell at `/ui`
- routes for the core product loop
- a tiny replay-pack exporter and offline eval harness
- a SimSat Sentinel capture-manifest exporter for freezing real current/baseline pairs
- tests for API and service behavior

## Repo layout

```text
app/        backend services, routes, schemas, policy spine
tests/      API and service regressions
training/   replay pack, eval harness, training helpers
ui/         same-origin dashboard shell
```

## Fast start

```bash
cp .env.example .env
python3 -m pip install -e ".[dev]"
make dev
```

Then open `http://127.0.0.1:8000/docs`.
The read-only UI shell lives at `http://127.0.0.1:8000/ui`.

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

This project can optionally use Hugging Face tooling for:
- dataset creation
- evaluation
- training on HF Jobs
- Hub artifact handling
