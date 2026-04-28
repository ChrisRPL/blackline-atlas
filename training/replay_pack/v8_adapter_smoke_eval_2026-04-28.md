# v8 Adapter Smoke Eval

Date: 2026-04-28

## Scope

This is a small local product smoke, not the authoritative 22-case frozen gold gate.

Datasets:

- `training/internal_benchmarks/blackline_public_seed/blackline_candidate_eval.jsonl`
- `training/external_benchmarks/xbd_public_seed/blackline_candidate_eval.jsonl`

Adapter:

- `ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v8-adapter`

Training job:

- `69efd6e8d2c8bd8662bd13bf`
- diagnostic eval loss: `2.7993 -> 1.2974`

## Result

After safe-discard JSON repair:

| Model | Cases | Action Match | Schema Valid | Downlink Recall | False Positives |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base `LiquidAI/LFM2.5-VL-450M` | 5 | 1 | 5 | 0 / 3 | 0 |
| v8 adapter | 5 | 1 | 5 | 0 / 3 | 0 |

## Decision

Do not promote v8 to demo-critical runtime.

Reason:

- v8 trains and publishes correctly.
- v8 does not beat the base model on product smoke.
- both base and v8 miss positive disruption examples in this smoke.
- v8 predicts zero `downlink_now` rows on a positive smoke set.
- full frozen 22-case gold eval is still required before any adapter promotion claim.

Runtime stays:

- deterministic replay for demo
- strict JSON repair
- adapter as research artifact / optional scorer only
