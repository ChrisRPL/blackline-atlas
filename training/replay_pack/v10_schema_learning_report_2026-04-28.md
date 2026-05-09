# v10 Schema-Learning Report

Date: 2026-04-28

## Purpose

Run a fast sanity check after v9 published successfully but produced zero
schema-valid outputs on eval-gold smoke. v10 used the same v2.2 real-image
calibration bundle with stronger schema-learning settings.

## Training Setup

- Config: `training/configs/lfm25_vl_sft_train_hf_aux_v10.yaml`
- Bundle: `ChrisRPL/blackline-atlas-training-bundles:bundles/lfm25_vl_sft_train_hf_aux_v10.tar.gz`
- Job: `https://huggingface.co/jobs/ChrisRPL/69f0ac8bd70108f37ace0f4d`
- Adapter: `ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v10-adapter`
- Train rows: 93
- Eval rows: 51
- Epochs: 10
- Steps: 105
- LoRA: `r=16`, `alpha=32`, `dropout=0.05`
- LR: `5e-5`

## Trainer Result

- Status: completed
- Adapter published: yes
- Eval loss: `~2.9309 -> 1.2123`
- Assessment: the model learned the training distribution better than v9, but
  the held-out generation behavior still failed the required schema.

## Eval-Gold Smoke

Local 3-case smoke on `eval_gold_sft.jsonl`:

| Model | JSON valid | Evidence schema valid | Action match |
| --- | ---: | ---: | ---: |
| Base `LiquidAI/LFM2.5-VL-450M` | 3/3 | 0/3 | 0/3 |
| v9 adapter | 3/3 | 0/3 | 0/3 |
| v10 adapter | 3/3 | 0/3 | 0/3 |

v10 output pattern:

```json
{"visual_evidence": "None", "triage_action": "No evidence of disruption or explosion."}
```

This is closer to structured JSON than v9, but still invalid for
`EvidenceFirstCandidate` and misses all three positive `downlink_now` cases.

## Conclusion

Do not spend more training time only increasing epochs on the current setup.
The issue is likely target-format/task wiring: the adapter is not reliably learning
the exact assistant object despite lower trainer loss.

Recommended next move:

1. Keep v10 as a published artifact, not the demo-critical path.
2. Add deterministic schema repair/defaulting around model outputs for demo safety.
3. If training continues, simplify the target to a much smaller JSON contract first:
   `{"triage_action": "...", "visual_evidence_tags": [...], "bbox_norm": null}`.
4. Run a tiny overfit test on 8 rows before any larger HF job; require 8/8
   schema-valid generations before using more data or GPU time.
