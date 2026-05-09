# Liquid Benchmark Cohort — 2026-04-20

Purpose:

- run the first real cross-slice benchmark cohort
- keep external slices auxiliary
- test the frozen prompt contract before any model tuning story

Model:

- `LiquidAI/LFM2.5-VL-450M`
- local OpenAI-compatible MLX bridge
- model key: `liquid_lfm25_vl_450m_http`

Slices used:

- `internal_public_seed_v0`
- `xbd_public_seed_v0`
- `spacenet8_public_seed_v0`

Scorecard:

| slice | total | pass | action | schema | false_positive | predicted_downlink |
|---|---:|---:|---:|---:|---:|---:|
| `internal_public_seed_v0` | `1` | `0` | `0` | `1` | `0` | `0` |
| `xbd_public_seed_v0` | `4` | `0` | `0` | `0` | `0` | `0` |
| `spacenet8_public_seed_v0` | `4` | `0` | `0` | `0` | `0` | `0` |

What happened:

- internal public seed:
  - schema-valid
  - still collapsed to `discard / no_event`
  - emitted full-frame bbox
  - wrong rationale field
- `xBD` public seed:
  - outputs were malformed
  - typical failure: omitted `civilian_impact` and `why`
  - action still drifted to `discard`
- `SpaceNet 8` public seed:
  - outputs were malformed in a different way
  - code fences
  - invalid enum values
  - nested bbox shape

Read:

- benchmark lane is useful
- current Liquid bridge path is real
- prompt contract is not yet robust enough for external transfer
- core Blackline need is still better internal data, not benchmark breadth for its own sake

Implication:

1. keep external benchmark slices as auxiliary research and transfer evidence
2. do not treat them as substitutes for internal Blackline gold rows
3. next core move stays `Novus Logistics Center`
4. next benchmark move should be one comparator model on the same three slices, preferably on HF Jobs

Artifacts:

- local scorecard lives under untracked `training/eval_runs/model-benchmark-liquid-public-cohort/`
- committed slice manifests stay in:
  - `training/replay_pack/model_benchmark_manifest.json`
  - `training/internal_benchmarks/blackline_public_seed/`
