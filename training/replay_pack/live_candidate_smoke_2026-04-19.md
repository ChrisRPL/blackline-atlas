# Live Candidate Smoke 2026-04-19

Goal:
- exercise the real candidate HTTP lane against actual SimSat image bytes
- separate transport/runtime bugs from model recall issues

Setup:
- local Apple Silicon bridge:
  - `training/scripts/serve_liquid_vl_openai.py`
  - model: `LiquidAI/LFM2.5-VL-450M-MLX-4bit`
- provider:
  - `openai_chat_completions_http`
- source:
  - live SimSat historical Sentinel captures

Cases run:

| case_id | expected_action | live result | notes |
| --- | --- | --- | --- |
| `beirut_port_blast` | `downlink_now` | `discard / no_event` | catastrophic positive collapsed |
| `port_sudan_aid_hub_strikes` | `downlink_now` | `discard / no_event` | catastrophic positive collapsed |
| `silpo_kvitneve_distribution_center_strike` | `downlink_now` | malformed `no_event` JSON | missing `civilian_impact` and `why` |
| `ras_abu_jarjur_no_material_change` | `discard` | `discard / no_event` | direction correct, formatting sloppy |

Raw outputs:
- saved under `/tmp/blackline-candidate-smoke/`

What this proves:
- local candidate transport is real
- OpenAI-compatible payload shaping is real
- SimSat capture-backed image inputs are real
- parser/telemetry path is real
- main remaining problem is model recall and output discipline, not infra

Observed failure pattern:
1. catastrophic positives collapse to `no_event`
2. `no_event` often defaults to:
   - `severity=medium`
   - `confidence=0.75-0.85`
   - full-frame bbox
3. `no_event` sometimes uses the wrong `civilian_impact`
4. one inland-food positive dropped required keys entirely

Immediate correction:
- tighten prompt toward:
  - catastrophic facility-loss anchors
  - `defer` over `no_event` when a large facility looks damaged but imperfectly
  - explicit `no_event -> no_material_impact`
  - explicit `never omit required keys`

Rerun after prompt tightening:
- `beirut_port_blast`: still `discard / no_event`
- `silpo_kvitneve_distribution_center_strike`: still malformed `no_event`
- `ras_abu_jarjur_no_material_change`: still correct direction, wrong `civilian_impact`

Takeaway:
- prompt tightening alone did not materially improve recall
- next gains should come from better positive coverage and eval pressure, not more prompt churn

What this does not justify yet:
- adapter training
- inference framework rewrite
- more backend seams

Best next move after this memo:
- expand gold positives in `water` and `aid`
- add one more inland food positive/control pair
- rerun the live smoke set after dataset growth
- only then revisit fine-tune / adapter decisions
