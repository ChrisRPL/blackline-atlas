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

After switching the smoke to the runtime evidence-first prompt and adding narrow
alias normalization for common model outputs:

| Model | Cases | Action Match | Schema Valid | Downlink Recall | False Positives |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base `LiquidAI/LFM2.5-VL-450M` | 5 | 0 | 1 | 0 / 3 | 0 |
| v8 adapter | 5 | 1 | 2 | 0 / 3 | 0 |

Acceptance check on the 4-case xBD smoke:

- `training/eval_runs/runtime-evidence-v8-xbd-seed/acceptance.json`
- rejected because downlink recall is still `0 / 2`
- rejected because v8 predicts zero `downlink_now` rows on a positive gold set

## Decision

Do not promote v8 to demo-critical runtime.

Reason:

- v8 trains and publishes correctly.
- v8 improves structured-output survival slightly on this tiny smoke.
- v8 still does not solve the product-critical behavior.
- both base and v8 miss positive disruption examples in this smoke.
- v8 predicts zero `downlink_now` rows on a positive smoke set.
- full frozen 22-case gold eval is still required before any adapter promotion claim.

Runtime stays:

- deterministic replay for demo
- strict JSON repair
- adapter as research artifact / optional scorer only
